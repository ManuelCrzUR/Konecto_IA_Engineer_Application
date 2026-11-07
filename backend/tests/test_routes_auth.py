"""Login, logout, /me and per-user isolation through the real create_app (fake agent, D-43)."""

import psycopg
import pytest
from fastapi.testclient import TestClient

from app.api import deps
from app.api.main import create_app
from app.auth.seed import TEST_USERS
from app.db import sessions_repo
from app.domain.conversation import AgentResult
from app.domain.models import Product, ToolTrace
from tests.conftest import get_test_db_url

DB_URL = get_test_db_url()
PRODUCT = Product(
    part_number="761C",
    enclosure="weatherproof",
    voltage="110V",
    service="on_off",
    has_data=True,
    fields={"onoff_torque_nm": 50.0},
)
TRACE = ToolTrace(tool="get_actuator", params={"part_number": "761C"}, result={"found": True})


def fake_agent(query, history, *, conn_factory):
    return AgentResult(answer=f"re: {query}", products=[PRODUCT], trace=[TRACE])


@pytest.fixture
def db():
    from app.db.connection import SCHEMA_SQL

    try:
        conn = psycopg.connect(DB_URL, autocommit=True, connect_timeout=3)
    except psycopg.OperationalError as exc:
        pytest.skip(f"Postgres unreachable ({exc})")
    conn.execute(SCHEMA_SQL.read_text())
    conn.execute("TRUNCATE auth_tokens, messages, sessions, users RESTART IDENTITY CASCADE")
    yield conn
    conn.close()


@pytest.fixture
def client(db):
    app = create_app(DB_URL, bootstrap=False)
    app.dependency_overrides[deps.get_agent] = lambda: fake_agent
    with TestClient(app, raise_server_exceptions=False) as c:
        from app.auth.seed import seed_test_users

        seed_test_users(db)
        yield c


def login(client, email, password):
    return client.post("/api/auth/login", json={"email": email, "password": password})


def auth(client, email, password) -> dict[str, str]:
    r = login(client, email, password)
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


ANA = ("ana@konecto.test", "ana-series76")
BEN = ("ben@konecto.test", "ben-series76")
DEV = ("dev@konecto.test", "dev-series76")


def test_login_ok(client):
    r = login(client, *ANA)
    assert r.status_code == 200
    body = r.json()
    assert set(body) == {"token", "user"} and len(body["token"]) >= 40
    assert body["user"] == {"email": ANA[0], "role": "user"}


def test_login_email_is_case_insensitive(client):
    assert login(client, "ANA@Konecto.test ", ANA[1]).status_code == 200


def test_wrong_password_and_unknown_email_look_identical(client):
    wrong = login(client, ANA[0], "nope")
    unknown = login(client, "ghost@konecto.test", "nope")
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json()
    assert wrong.json() == {"error": "invalid_credentials", "detail": "Wrong email or password"}


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"email": "", "password": "x"},
        {"email": "a", "password": ""},
        {"email": "a" * 255, "password": "x"},
        {"email": "a", "password": "x" * 201},
    ],
)
def test_login_validation_422(client, payload):
    r = client.post("/api/auth/login", json=payload)
    assert r.status_code == 422 and r.json()["error"] == "validation_error"


def test_me(client):
    h = auth(client, *DEV)
    r = client.get("/api/auth/me", headers=h)
    assert r.status_code == 200 and r.json() == {"email": DEV[0], "role": "developer"}


def test_logout_revokes_only_that_token(client):
    h1, h2 = auth(client, *ANA), auth(client, *ANA)
    assert client.post("/api/auth/logout", headers=h1).status_code == 204
    assert client.get("/api/auth/me", headers=h1).status_code == 401
    assert client.get("/api/auth/me", headers=h2).status_code == 200


def _assert_unauthorized(r):
    assert r.status_code == 401
    assert r.json() == {"error": "unauthorized", "detail": "Sign in first"}
    assert r.headers["WWW-Authenticate"] == "Bearer"


SID = "00000000-0000-0000-0000-000000000000"


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("post", "/api/conversation"),
        ("get", "/api/sessions"),
        ("get", f"/api/sessions/{SID}/messages"),
        ("post", "/api/auth/logout"),
        ("get", "/api/auth/me"),
    ],
)
def test_routes_need_a_token(client, method, path):
    kwargs = {"json": {"query": "hi"}} if method == "post" and "conversation" in path else {}
    _assert_unauthorized(getattr(client, method)(path, **kwargs))


@pytest.mark.parametrize("header", ["Basic abc", "Bearer", "Bearer not-a-real-token", "token"])
def test_malformed_or_unknown_token_401(client, header):
    _assert_unauthorized(client.get("/api/auth/me", headers={"Authorization": header}))


def test_health_and_login_are_public(client):
    assert client.get("/health").status_code == 200
    assert login(client, *ANA).status_code == 200


def test_expired_token_401(client, db):
    h = auth(client, *ANA)
    assert client.get("/api/auth/me", headers=h).status_code == 200
    db.execute("UPDATE auth_tokens SET expires_at = now() - interval '1 second'")
    _assert_unauthorized(client.get("/api/auth/me", headers=h))


def ask(client, headers, query="hello", session_id=None):
    body = {"query": query}
    if session_id:
        body["session_id"] = session_id
    return client.post("/api/conversation", json=body, headers=headers)


def test_user_cannot_see_or_use_another_users_session(client, db):
    ha, hb = auth(client, *ANA), auth(client, *BEN)
    sid = ask(client, ha, "ana secret").json()["session_id"]
    assert client.get("/api/sessions", headers=hb).json() == []
    assert [s["id"] for s in client.get("/api/sessions", headers=ha).json()] == [sid]
    assert client.get("/api/sessions", params={"q": "secret"}, headers=hb).json() == []
    r = client.get(f"/api/sessions/{sid}/messages", headers=hb)
    assert r.status_code == 404 and r.json()["error"] == "session_not_found"
    r = ask(client, hb, "intruder", session_id=sid)
    assert r.status_code == 404 and r.json()["error"] == "session_not_found"
    count = db.execute("SELECT count(*) FROM messages WHERE session_id = %s", (sid,)).fetchone()
    assert count[0] == 2  # Ana's own question and answer only
    assert db.execute("SELECT busy_since FROM sessions WHERE id = %s", (sid,)).fetchone()[0] is None
    assert len(client.get(f"/api/sessions/{sid}/messages", headers=ha).json()) == 2


def test_role_user_gets_no_trace_developer_does(client, db):
    hu, hd = auth(client, *ANA), auth(client, *DEV)
    ru = ask(client, hu, "hi").json()
    assert ru["debug"] == [] and ru["products"][0]["part_number"] == "761C"
    rd = ask(client, hd, "hi").json()
    assert rd["debug"][0]["tool"] == "get_actuator"
    # Stored unchanged for both: the trace is only hidden on the way out.
    stored = db.execute(
        "SELECT count(*) FROM messages WHERE role = 'assistant' AND trace <> '[]'::jsonb"
    ).fetchone()
    assert stored[0] == 2
    for h, sid in ((hu, ru["session_id"]), (hd, rd["session_id"])):
        msgs = client.get(f"/api/sessions/{sid}/messages", headers=h).json()
        assert msgs[1]["products"][0]["part_number"] == "761C"
        assert bool(msgs[1]["trace"]) == (h is hd)


def test_same_stored_message_differs_by_role(client, db):
    """One stored message with a trace: the developer sees it, the user (owner) does not."""
    users = {r[1]: r[0] for r in db.execute("SELECT id, email FROM users").fetchall()}
    for email, h in ((DEV[0], auth(client, *DEV)), (ANA[0], auth(client, *ANA))):
        s = sessions_repo.create_session(db, "t", users[email])
        sessions_repo.add_message(db, s.id, "assistant", "a", [PRODUCT], [TRACE])
        trace = client.get(f"/api/sessions/{s.id}/messages", headers=h).json()[0]["trace"]
        assert bool(trace) == (email == DEV[0])


def test_startup_seeds_the_three_test_users(db, caplog):
    db.execute("TRUNCATE auth_tokens, messages, sessions, users CASCADE")
    app = create_app(DB_URL, bootstrap=True)
    with caplog.at_level("INFO", logger="series76.api"), TestClient(app) as c:
        assert login(c, *DEV).json()["user"]["role"] == "developer"
    emails = {r[0] for r in db.execute("SELECT email FROM users").fetchall()}
    assert emails == {e for e, _, _ in TEST_USERS}
    assert "3 user(s)" in caplog.text
    assert not any(pw in caplog.text for _, pw, _ in TEST_USERS)  # never log passwords
