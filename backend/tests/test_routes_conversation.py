"""POST /api/conversation against a real Postgres with a fake agent (no LLM)."""

import uuid
from contextlib import contextmanager

import psycopg
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from psycopg.rows import dict_row

from app.agent.agent import AgentError
from app.api import deps
from app.api.errors import install_error_handlers
from app.api.routes_conversation import router, to_history
from app.db import sessions_repo
from app.domain.conversation import AgentResult, StoredMessage
from app.domain.models import Product, ToolTrace
from tests.conftest import get_test_db_url

URL = get_test_db_url("series76_test")
PRODUCT = Product(
    part_number="761C",
    enclosure="weatherproof",
    voltage="110V",
    service="on_off",
    has_data=True,
    fields={"onoff_torque_nm": 50.0},
)
TRACE = ToolTrace(tool="get_actuator", params={"part_number": "761C"}, result={"found": True})


class FakeAgent:
    def __init__(self) -> None:
        self.calls: list[tuple] = []
        self.error: Exception | None = None

    def __call__(self, query, history, *, conn_factory):
        self.calls.append((query, history, conn_factory))
        if self.error:
            raise self.error
        return AgentResult(answer=f"re: {query}", products=[PRODUCT], trace=[TRACE])


@pytest.fixture
def env(pg):  # pg: schema applied + tables truncated
    conn = psycopg.connect(URL, autocommit=True, row_factory=dict_row)  # type: ignore[arg-type]

    @contextmanager
    def factory():
        c = psycopg.connect(URL, autocommit=True, row_factory=dict_row)  # type: ignore[arg-type]
        try:
            yield c
        finally:
            c.close()

    agent = FakeAgent()
    app = FastAPI()
    app.include_router(router, prefix="/api")
    install_error_handlers(app)
    app.dependency_overrides[deps.get_conn] = lambda: conn
    app.dependency_overrides[deps.get_conn_factory] = lambda: factory
    app.dependency_overrides[deps.get_agent] = lambda: agent
    yield TestClient(app, raise_server_exceptions=False), agent, conn, factory
    conn.close()


def _count(conn, table):
    return conn.execute(f"SELECT count(*) AS n FROM {table}").fetchone()["n"]


def test_new_session_stores_both_messages(env):
    client, agent, conn, factory = env
    query = "x" * 80
    r = client.post("/api/conversation", json={"query": query})
    assert r.status_code == 200
    body = r.json()
    assert body["answer"] == f"re: {query}"
    assert body["products"][0]["part_number"] == "761C"
    assert body["debug"][0]["tool"] == "get_actuator"
    sid = uuid.UUID(body["session_id"])
    session = sessions_repo.get_session(conn, sid)
    assert session and len(session.title) <= 50
    msgs = sessions_repo.list_messages(conn, sid)
    assert [m.role for m in msgs] == ["user", "assistant"]
    assert msgs[0].content == query and msgs[0].products == []
    assert msgs[1].products[0].part_number == "761C" and msgs[1].trace[0].tool == "get_actuator"
    assert agent.calls[0][1] == [] and agent.calls[0][2] is factory


def test_existing_session_passes_prior_history_only(env):
    client, agent, conn, _ = env
    sid = client.post("/api/conversation", json={"query": "first"}).json()["session_id"]
    r = client.post("/api/conversation", json={"session_id": sid, "query": "second"})
    assert r.status_code == 200 and r.json()["session_id"] == sid
    history = agent.calls[1][1]
    assert [(t.role, t.content, t.part_numbers) for t in history] == [
        ("user", "first", []),
        ("assistant", "re: first", ["761C"]),
    ]
    assert _count(conn, "sessions") == 1 and _count(conn, "messages") == 4


def test_three_turns_history_grows(env):
    client, agent, _, _ = env
    sid = client.post("/api/conversation", json={"query": "a"}).json()["session_id"]
    for q in ("b", "c"):
        client.post("/api/conversation", json={"session_id": sid, "query": q})
    assert [len(c[1]) for c in agent.calls] == [0, 2, 4]
    assert [t.content for t in agent.calls[2][1]] == ["a", "re: a", "b", "re: b"]


def test_unknown_session_404_writes_nothing(env):
    client, agent, conn, _ = env
    r = client.post("/api/conversation", json={"session_id": str(uuid.uuid4()), "query": "hi"})
    assert r.status_code == 404 and r.json()["error"] == "session_not_found"
    assert agent.calls == [] and _count(conn, "sessions") == 0 and _count(conn, "messages") == 0


@pytest.mark.parametrize(
    "payload",
    [
        {"query": ""},
        {"query": "   "},
        {"query": "x" * 2001},
        {"query": "hi", "session_id": "nope"},
        {},
    ],
)
def test_invalid_body_422_writes_nothing(env, payload):
    client, agent, conn, _ = env
    r = client.post("/api/conversation", json=payload)
    assert r.status_code == 422 and r.json()["error"] == "validation_error"
    assert agent.calls == [] and _count(conn, "sessions") == 0 and _count(conn, "messages") == 0


def test_agent_error_503_keeps_user_message(env):
    client, agent, conn, _ = env
    agent.error = AgentError("boom")
    r = client.post("/api/conversation", json={"query": "hello"})
    assert r.status_code == 503 and r.json()["error"] == "llm_unavailable"
    rows = conn.execute("SELECT role, content FROM messages").fetchall()
    assert rows == [{"role": "user", "content": "hello"}]


def test_to_history():
    from datetime import datetime

    def msg(i, role, products):
        return StoredMessage(
            id=i,
            session_id=uuid.uuid4(),
            role=role,
            content=f"m{i}",
            products=products,
            created_at=datetime.now(),
        )

    turns = to_history([msg(1, "user", []), msg(2, "assistant", [PRODUCT, PRODUCT])])
    assert [(t.role, t.content, t.part_numbers) for t in turns] == [
        ("user", "m1", []),
        ("assistant", "m2", ["761C", "761C"]),
    ]


def test_503_carries_session_id_and_retry_reuses_session(env):
    client, agent, conn, _ = env
    agent.error = AgentError("boom")
    r = client.post("/api/conversation", json={"query": "hello"})
    assert r.status_code == 503 and set(r.json()) == {"error", "detail"}
    sid = r.headers["X-Session-Id"]
    assert _count(conn, "sessions") == 1
    assert str(conn.execute("SELECT id FROM sessions").fetchone()["id"]) == sid
    agent.error = None
    r2 = client.post("/api/conversation", json={"session_id": sid, "query": "hello"})
    assert r2.status_code == 200 and r2.headers["X-Session-Id"] == sid
    assert r2.json()["session_id"] == sid and _count(conn, "sessions") == 1


def test_success_header_matches_body_and_errors_before_session_have_none(env):
    client, _, _, _ = env
    r = client.post("/api/conversation", json={"query": "hi"})
    assert r.headers["X-Session-Id"] == r.json()["session_id"]
    r404 = client.post("/api/conversation", json={"session_id": str(uuid.uuid4()), "query": "x"})
    r422 = client.post("/api/conversation", json={"query": ""})
    assert "X-Session-Id" not in r404.headers and "X-Session-Id" not in r422.headers


def _lock(factory, sid):
    with factory() as c:
        return sessions_repo.try_lock_session(c, uuid.UUID(sid))


def _busy_since(conn):
    return conn.execute("SELECT busy_since FROM sessions").fetchone()["busy_since"]


def test_concurrent_turn_409_writes_nothing(env):
    client, agent, conn, factory = env
    sid = client.post("/api/conversation", json={"query": "first"}).json()["session_id"]
    assert _lock(factory, sid)
    r = client.post("/api/conversation", json={"session_id": sid, "query": "second"})
    assert r.status_code == 409 and r.json()["error"] == "turn_in_progress"
    assert r.headers["X-Session-Id"] == sid
    assert len(agent.calls) == 1 and _count(conn, "messages") == 2
    assert _busy_since(conn) is not None  # the other turn's lock is untouched


def test_lock_released_after_success_and_agent_failure(env):
    client, agent, conn, _ = env
    sid = client.post("/api/conversation", json={"query": "a"}).json()["session_id"]
    assert _busy_since(conn) is None
    agent.error = AgentError("boom")
    assert (
        client.post("/api/conversation", json={"session_id": sid, "query": "b"}).status_code == 503
    )
    assert _busy_since(conn) is None
    agent.error = None
    assert (
        client.post("/api/conversation", json={"session_id": sid, "query": "c"}).status_code == 200
    )


def test_assistant_write_retried_once(env, monkeypatch):
    client, _, conn, _ = env
    real = sessions_repo.add_message
    state = {"failed": False}

    def flaky(c, sid, role, *a, **kw):
        if role == "assistant" and not state["failed"]:
            state["failed"] = True
            raise psycopg.OperationalError("dropped")
        return real(c, sid, role, *a, **kw)

    monkeypatch.setattr(sessions_repo, "add_message", flaky)
    r = client.post("/api/conversation", json={"query": "hi"})
    assert r.status_code == 200 and state["failed"]
    assert [
        m["role"] for m in conn.execute("SELECT role FROM messages ORDER BY id").fetchall()
    ] == [
        "user",
        "assistant",
    ]
    assert _busy_since(conn) is None


def test_assistant_write_fails_twice_503_user_kept_lock_released(env, monkeypatch):
    client, _, conn, _ = env
    real = sessions_repo.add_message

    def broken(c, sid, role, *a, **kw):
        if role == "assistant":
            raise psycopg.OperationalError("down")
        return real(c, sid, role, *a, **kw)

    monkeypatch.setattr(sessions_repo, "add_message", broken)
    r = client.post("/api/conversation", json={"query": "hi"})
    assert r.status_code == 503 and r.json()["error"] == "database_unavailable"
    assert conn.execute("SELECT role FROM messages").fetchall() == [{"role": "user"}]
    assert _busy_since(conn) is None
