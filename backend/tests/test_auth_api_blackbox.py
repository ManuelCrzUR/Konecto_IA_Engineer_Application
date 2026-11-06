"""Black-box HTTP tests for login, bearer auth, session ownership and trace visibility.

Only the HTTP contract is checked. The app is built against the test database with
bootstrap=True (seeded users), and the agent is replaced by a fake that returns a
non-empty trace, so debug/trace visibility can be verified. No LLM is called.
"""

from __future__ import annotations

import psycopg
import pytest
from fastapi.testclient import TestClient

from app.api import deps
from app.api.main import create_app
from app.db.connection import SCHEMA_SQL
from app.domain.conversation import AgentResult
from app.domain.models import ToolTrace
from tests.conftest import get_test_db_url

DB_URL = get_test_db_url("series76_t_api_a")

ANA = ("ana@konecto.test", "ana-series76", "user")
BEN = ("ben@konecto.test", "ben-series76", "user")
DEV = ("dev@konecto.test", "dev-series76", "developer")
PASSWORDS = [ANA[1], BEN[1], DEV[1]]


def fake_agent(query, history, **_kwargs) -> AgentResult:
    """Stands in for run_agent: fixed answer plus one tool call in the trace."""
    return AgentResult(
        answer=f"echo: {query}",
        trace=[
            ToolTrace(
                tool="search_actuators",
                params={"min_torque_nm": 10},
                result={"count": 1},
                duration_ms=1.5,
            )
        ],
    )


@pytest.fixture
def client():
    try:
        conn = psycopg.connect(DB_URL, autocommit=True, connect_timeout=3)
    except psycopg.OperationalError as exc:
        pytest.skip(f"Postgres unreachable ({exc})")
    conn.execute(SCHEMA_SQL.read_text())
    conn.execute(
        "TRUNCATE auth_tokens, messages, sessions, users, actuators, catalog_tables "
        "RESTART IDENTITY CASCADE"
    )
    conn.close()

    app = create_app(DB_URL, bootstrap=True)
    app.dependency_overrides[deps.get_agent] = lambda: fake_agent
    with TestClient(app) as c:
        yield c


def login(client: TestClient, email: str, password: str):
    return client.post("/api/auth/login", json={"email": email, "password": password})


def token_for(client: TestClient, user) -> str:
    r = login(client, user[0], user[1])
    assert r.status_code == 200, r.text
    return r.json()["token"]


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def items(body, key: str) -> list:
    """Accept either a bare list or an object wrapping the list under `key`."""
    return body if isinstance(body, list) else body[key]


def ask(client: TestClient, token: str, query: str, session_id: str | None = None):
    payload = {"query": query}
    if session_id is not None:
        payload["session_id"] = session_id
    return client.post("/api/conversation", json=payload, headers=auth(token))


# --- login -----------------------------------------------------------------


def test_login_returns_token_and_user(client):
    r = login(client, ANA[0], ANA[1])
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body["token"], str) and body["token"]
    assert body["user"] == {"email": ANA[0], "role": "user"}


def test_login_email_is_case_insensitive_and_trimmed(client):
    r = login(client, "ANA@konecto.test ", ANA[1])
    assert r.status_code == 200
    assert r.json()["user"]["email"] == ANA[0]


def test_wrong_password_and_unknown_email_share_one_error_body(client):
    wrong_pw = login(client, ANA[0], "not-the-password")
    unknown = login(client, "nobody@konecto.test", "whatever")
    assert wrong_pw.status_code == 401
    assert unknown.status_code == 401
    assert wrong_pw.json() == unknown.json()
    assert wrong_pw.json()["error"] == "invalid_credentials"
    assert "detail" in wrong_pw.json()


# --- bearer auth on protected routes ----------------------------------------


def test_health_is_public(client):
    assert client.get("/health").status_code == 200


def test_missing_authorization_header_is_401(client):
    r = client.get("/api/sessions")
    assert r.status_code == 401
    assert r.json()["error"] == "unauthorized"
    assert "www-authenticate" in {k.lower() for k in r.headers}


@pytest.mark.parametrize("header", ["Token abc", "Bearer ", "Bearer"])
def test_malformed_authorization_header_is_401(client, header):
    r = client.get("/api/sessions", headers={"Authorization": header})
    assert r.status_code == 401
    assert r.json()["error"] == "unauthorized"
    assert "www-authenticate" in {k.lower() for k in r.headers}


def test_unknown_token_is_401(client):
    r = client.get("/api/sessions", headers=auth("not-a-real-token"))
    assert r.status_code == 401
    assert r.json()["error"] == "unauthorized"


def test_me_returns_email_and_role_for_each_seeded_user(client):
    for user in (ANA, BEN, DEV):
        r = client.get("/api/auth/me", headers=auth(token_for(client, user)))
        assert r.status_code == 200
        assert r.json() == {"email": user[0], "role": user[2]}


def test_logout_revokes_only_that_token(client):
    first = token_for(client, ANA)
    second = token_for(client, ANA)

    r = client.post("/api/auth/logout", headers=auth(first))
    assert r.status_code == 204

    assert client.get("/api/auth/me", headers=auth(first)).status_code == 401
    assert client.get("/api/auth/me", headers=auth(second)).status_code == 200


# --- sessions and ownership --------------------------------------------------


def test_new_conversation_creates_session_for_caller(client):
    token = token_for(client, ANA)
    r = ask(client, token, "What torque does 761A need?")
    assert r.status_code == 200
    body = r.json()
    assert body["session_id"]
    assert body["answer"] == "echo: What torque does 761A need?"

    listed = items(client.get("/api/sessions", headers=auth(token)).json(), "sessions")
    assert body["session_id"] in [str(s["id"]) for s in listed]


def test_session_list_contains_only_callers_sessions(client):
    ana_token = token_for(client, ANA)
    ben_token = token_for(client, BEN)
    ana_session = ask(client, ana_token, "ana question").json()["session_id"]
    ben_session = ask(client, ben_token, "ben question").json()["session_id"]

    ana_ids = {
        str(s["id"])
        for s in items(client.get("/api/sessions", headers=auth(ana_token)).json(), "sessions")
    }
    ben_ids = {
        str(s["id"])
        for s in items(client.get("/api/sessions", headers=auth(ben_token)).json(), "sessions")
    }
    assert ana_session in ana_ids and ben_session not in ana_ids
    assert ben_session in ben_ids and ana_session not in ben_ids


def test_continuing_own_session_appends_messages(client):
    token = token_for(client, ANA)
    session_id = ask(client, token, "first").json()["session_id"]
    r = ask(client, token, "second", session_id=session_id)
    assert r.status_code == 200
    assert r.json()["session_id"] == session_id

    msgs = items(
        client.get(f"/api/sessions/{session_id}/messages", headers=auth(token)).json(),
        "messages",
    )
    contents = [m["content"] for m in msgs]
    assert "first" in contents and "second" in contents


def test_other_users_session_messages_are_404_not_403(client):
    ana_token = token_for(client, ANA)
    ben_token = token_for(client, BEN)
    session_id = ask(client, ana_token, "private to ana").json()["session_id"]

    r = client.get(f"/api/sessions/{session_id}/messages", headers=auth(ben_token))
    assert r.status_code == 404
    assert "private to ana" not in r.text


def test_posting_into_other_users_session_is_404_and_adds_nothing(client):
    ana_token = token_for(client, ANA)
    ben_token = token_for(client, BEN)
    session_id = ask(client, ana_token, "ana only").json()["session_id"]

    before = items(
        client.get(f"/api/sessions/{session_id}/messages", headers=auth(ana_token)).json(),
        "messages",
    )
    r = ask(client, ben_token, "intruding", session_id=session_id)
    assert r.status_code == 404

    after = items(
        client.get(f"/api/sessions/{session_id}/messages", headers=auth(ana_token)).json(),
        "messages",
    )
    assert len(after) == len(before)
    assert (
        "intruding"
        not in client.get(f"/api/sessions/{session_id}/messages", headers=auth(ana_token)).text
    )


# --- debug / trace visibility by role -----------------------------------------


def test_debug_is_empty_for_user_role(client):
    token = token_for(client, ANA)
    body = ask(client, token, "torque?").json()
    assert body["debug"] == []


def test_debug_is_populated_for_developer_role(client):
    token = token_for(client, DEV)
    body = ask(client, token, "torque?").json()
    assert isinstance(body["debug"], list) and body["debug"]


def test_message_trace_follows_role(client):
    ana_token = token_for(client, ANA)
    dev_token = token_for(client, DEV)
    ana_session = ask(client, ana_token, "ana trace").json()["session_id"]
    dev_session = ask(client, dev_token, "dev trace").json()["session_id"]

    ana_msgs = items(
        client.get(f"/api/sessions/{ana_session}/messages", headers=auth(ana_token)).json(),
        "messages",
    )
    dev_msgs = items(
        client.get(f"/api/sessions/{dev_session}/messages", headers=auth(dev_token)).json(),
        "messages",
    )
    assert ana_msgs and all(m["trace"] == [] for m in ana_msgs)
    assert any(m["trace"] for m in dev_msgs)


# --- secrets ----------------------------------------------------------------


def test_passwords_never_appear_in_any_response(client):
    responses = [
        login(client, ANA[0], ANA[1]),
        login(client, ANA[0], "wrong"),
        client.get("/health"),
    ]
    dev_token = token_for(client, DEV)
    responses.append(client.get("/api/auth/me", headers=auth(dev_token)))
    chat = ask(client, dev_token, "hello")
    responses.append(chat)
    session_id = chat.json()["session_id"]
    responses.append(client.get("/api/sessions", headers=auth(dev_token)))
    responses.append(client.get(f"/api/sessions/{session_id}/messages", headers=auth(dev_token)))

    for r in responses:
        for password in PASSWORDS:
            assert password not in r.text, f"password leaked in {r.request.url}"
