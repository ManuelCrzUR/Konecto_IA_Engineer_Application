"""HTTP API black-box contract tests (Sprint 4).

Only ``deps.get_agent`` is faked; the DB, repos, routes and error handlers are real.
Run with TEST_DATABASE_URL pointing at a throwaway DB.
"""

import uuid

import psycopg
import pytest
from fastapi.testclient import TestClient

from app.agent.agent import AgentError
from app.api import deps
from app.api.main import create_app
from app.auth.repo import upsert_user
from app.domain.conversation import AgentResult
from app.domain.models import Actuator, Product, ToolTrace
from app.llm import LLMConfigError
from tests.conftest import act_as, get_test_db_url

DB_URL = get_test_db_url("series76_t_api_d")

PRODUCT_KEYS = {
    "part_number", "enclosure", "voltage", "phase", "service",
    "csa_certified", "has_data", "fields", "notes",
}  # fmt: skip
SESSION_KEYS = {"id", "user_id", "title", "created_at", "updated_at", "match"}
MESSAGE_KEYS = {"id", "session_id", "role", "content", "products", "trace", "created_at"}
TRACE_KEYS = {"tool", "params", "result", "duration_ms"}


class FakeAgent:
    def __init__(self) -> None:
        self.calls: list[tuple[str, list, dict]] = []
        self.next: AgentResult | Exception | None = None

    def __call__(self, query, history=None, **kwargs):
        self.calls.append((query, list(history or []), kwargs))
        if isinstance(self.next, Exception):
            raise self.next
        if self.next is not None:
            return self.next
        return make_result(f"answer to {query}")


def make_result(answer: str, row_index: int = 0) -> AgentResult:
    import json

    from tests.conftest import PROCESSED_JSON

    row = json.loads(PROCESSED_JSON.read_text())["rows"][row_index]
    product = Product.from_actuator(Actuator.model_validate(row), notes=["a note"])
    trace = ToolTrace(
        tool="get_actuator",
        params={"part_number": product.part_number},
        result={"found": True},
        duration_ms=1.5,
    )
    return AgentResult(answer=answer, products=[product], trace=[trace])


@pytest.fixture(scope="module")
def app():
    try:
        psycopg.connect(DB_URL, connect_timeout=3).close()
    except psycopg.OperationalError as exc:
        pytest.skip(f"Postgres unreachable: {exc}")
    return create_app(DB_URL, bootstrap=True)


@pytest.fixture
def agent(app):
    fake = FakeAgent()
    app.dependency_overrides[deps.get_agent] = lambda: fake
    yield fake
    app.dependency_overrides.clear()


@pytest.fixture(scope="module")
def _live(app):
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


@pytest.fixture
def client(app, _live, agent):
    with psycopg.connect(DB_URL, autocommit=True) as conn:
        conn.execute("TRUNCATE messages, sessions RESTART IDENTITY CASCADE")
        act_as(app, upsert_user(conn, "dev@konecto.test", "dev-series76", "developer"))
    return _live


def ask(client, query="hello", session_id=None):
    body = {"query": query}
    if session_id:
        body["session_id"] = session_id
    return client.post("/api/conversation", json=body)


def assert_error(resp, status, code):
    assert resp.status_code == status, resp.text
    body = resp.json()
    assert set(body) == {"error", "detail"}
    assert body["error"] == code
    return body


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok", "actuators": 68}


def test_response_snapshot(client):
    resp = ask(client, "what is 711A?")
    assert resp.status_code == 200
    body = resp.json()
    assert set(body) == {"session_id", "answer", "products", "debug"}
    uuid.UUID(body["session_id"])
    assert body["answer"] == "answer to what is 711A?"
    assert len(body["products"]) == 1
    assert set(body["products"][0]) == PRODUCT_KEYS
    assert len(body["debug"]) == 1
    assert set(body["debug"][0]) == TRACE_KEYS
    assert body["debug"][0]["duration_ms"] == 1.5


def test_new_session_listed_with_title(client):
    long_q = "x" * 120
    sid = ask(client, long_q).json()["session_id"]
    sessions = client.get("/api/sessions").json()
    assert len(sessions) == 1
    assert set(sessions[0]) == SESSION_KEYS
    assert sessions[0]["id"] == sid
    assert 0 < len(sessions[0]["title"]) <= 50
    assert long_q.startswith(sessions[0]["title"].rstrip(".…"))

    sid2 = ask(client, "short question").json()["session_id"]
    titles = {s["id"]: s["title"] for s in client.get("/api/sessions").json()}
    assert titles[sid2] == "short question"


def test_session_id_reusable(client, agent):
    sid = ask(client, "one").json()["session_id"]
    resp = ask(client, "two", sid)
    assert resp.status_code == 200
    assert resp.json()["session_id"] == sid
    assert len(client.get("/api/sessions").json()) == 1


def test_unknown_session_404_creates_nothing(client, agent):
    resp = ask(client, "hi", str(uuid.uuid4()))
    assert_error(resp, 404, "session_not_found")
    assert client.get("/api/sessions").json() == []
    assert agent.calls == []


def test_unknown_session_messages_404(client):
    assert_error(client.get(f"/api/sessions/{uuid.uuid4()}/messages"), 404, "session_not_found")


def test_malformed_messages_id_422(client):
    assert_error(client.get("/api/sessions/not-a-uuid/messages"), 422, "validation_error")


@pytest.mark.parametrize(
    "payload",
    [
        {"query": ""},
        {"query": "   \n\t "},
        {"query": "a" * 2001},
        {},
        {"session_id": "not-a-uuid", "query": "hi"},
        {"query": 123},
        {"query": ["x"]},
    ],
)
def test_invalid_requests_422(client, agent, payload):
    assert_error(client.post("/api/conversation", json=payload), 422, "validation_error")
    assert agent.calls == []
    assert client.get("/api/sessions").json() == []


def test_max_length_query_ok(client):
    assert ask(client, "a" * 2000).status_code == 200


def test_non_json_body_422(client):
    resp = client.post(
        "/api/conversation", content="not json", headers={"content-type": "application/json"}
    )
    assert_error(resp, 422, "validation_error")


def test_unknown_route_uniform_error(client):
    assert_error(client.get("/api/nope"), 404, "http_404")


def test_agent_error_503_user_message_persisted(client, agent):
    agent.next = AgentError("provider down")
    resp = ask(client, "will fail")
    assert_error(resp, 503, "llm_unavailable")
    sessions = client.get("/api/sessions").json()
    assert len(sessions) == 1
    msgs = client.get(f"/api/sessions/{sessions[0]['id']}/messages").json()
    assert [(m["role"], m["content"]) for m in msgs] == [("user", "will fail")]


def test_agent_error_on_existing_session_keeps_user_message(client, agent):
    sid = ask(client, "ok").json()["session_id"]
    agent.next = AgentError("down")
    assert_error(ask(client, "bad", sid), 503, "llm_unavailable")
    msgs = client.get(f"/api/sessions/{sid}/messages").json()
    assert [m["role"] for m in msgs] == ["user", "assistant", "user"]


def test_llm_config_error_503(client, agent):
    agent.next = LLMConfigError("AGENT_MODEL missing")
    assert_error(ask(client), 503, "llm_not_configured")


def test_unexpected_error_500_hides_detail(client, agent):
    agent.next = ValueError("secret-detail")
    resp = ask(client)
    assert_error(resp, 500, "internal_error")
    assert "secret-detail" not in resp.text


def test_three_turns_history_and_messages(client, agent):
    r1 = ask(client, "q1").json()
    sid = r1["session_id"]
    agent.next = make_result("a2", row_index=1)
    r2 = ask(client, "q2", sid).json()
    agent.next = make_result("a3", row_index=2)
    r3 = ask(client, "q3", sid).json()

    assert [len(c[1]) for c in agent.calls] == [0, 2, 4]
    assert [c[0] for c in agent.calls] == ["q1", "q2", "q3"]
    h = agent.calls[2][1]
    assert [(t.role, t.content) for t in h] == [
        ("user", "q1"), ("assistant", "answer to q1"),
        ("user", "q2"), ("assistant", "a2"),
    ]  # fmt: skip
    assert h[0].part_numbers == [] and h[2].part_numbers == []
    assert h[1].part_numbers == [r1["products"][0]["part_number"]]
    assert h[3].part_numbers == [r2["products"][0]["part_number"]]

    msgs = client.get(f"/api/sessions/{sid}/messages").json()
    assert len(msgs) == 6
    assert all(set(m) == MESSAGE_KEYS for m in msgs)
    assert [m["role"] for m in msgs] == ["user", "assistant"] * 3
    assert [m["content"] for m in msgs] == [
        "q1", "answer to q1", "q2", "a2", "q3", "a3"
    ]  # fmt: skip
    ids = [m["id"] for m in msgs]
    assert ids == sorted(ids)
    for m, r in ((msgs[1], r1), (msgs[3], r2), (msgs[5], r3)):
        assert m["products"] == r["products"]
        assert m["trace"] == r["debug"]
    assert msgs[0]["products"] == [] and msgs[0]["trace"] == []


def test_agent_receives_conn_factory(client, agent):
    ask(client, "x")
    assert callable(agent.calls[0][2].get("conn_factory"))


def test_sessions_ordered_by_latest_activity(client):
    a = ask(client, "first").json()["session_id"]
    b = ask(client, "second").json()["session_id"]
    assert [s["id"] for s in client.get("/api/sessions").json()] == [b, a]
    ask(client, "again", a)
    assert [s["id"] for s in client.get("/api/sessions").json()] == [a, b]


def test_sessions_limit(client):
    for i in range(3):
        ask(client, f"q{i}")
    assert len(client.get("/api/sessions?limit=2").json()) == 2
    assert_error(client.get("/api/sessions?limit=0"), 422, "validation_error")
    assert_error(client.get("/api/sessions?limit=201"), 422, "validation_error")


def test_sessions_empty(client):
    assert client.get("/api/sessions").json() == []


def test_503_carries_session_id_and_retry_continues_session(client, agent):
    agent.next = AgentError("down")
    resp = ask(client, "will fail")
    assert_error(resp, 503, "llm_unavailable")
    sessions = client.get("/api/sessions").json()
    assert len(sessions) == 1 and resp.headers["X-Session-Id"] == str(sessions[0]["id"])
    agent.next = None
    retry = ask(client, "will fail", resp.headers["X-Session-Id"])
    assert retry.status_code == 200
    assert retry.headers["X-Session-Id"] == retry.json()["session_id"]
    assert len(client.get("/api/sessions").json()) == 1


def test_llm_config_503_has_header_but_404_and_422_do_not(client, agent):
    agent.next = LLMConfigError("AGENT_MODEL missing")
    assert "X-Session-Id" in ask(client).headers
    assert "X-Session-Id" not in ask(client, "hi", str(uuid.uuid4())).headers
    assert "X-Session-Id" not in ask(client, "").headers
