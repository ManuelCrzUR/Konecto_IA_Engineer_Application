"""Login attempt limiter (D-52): unit tests with a fake clock, then API behaviour."""

from app.auth import attempts
from tests import test_routes_auth as _routes
from tests.test_routes_auth import ANA, BEN, login

# Reuse the auth API fixtures (fake agent, seeded users, clean tables).
db = _routes.db
client = _routes.client


def test_blocks_on_fifth_failure_and_reports_wait():
    for i in range(4):
        attempts.record_failure("a@x.test", now=100.0 + i)
        assert attempts.blocked("a@x.test", now=100.0 + i) is None
    attempts.record_failure("a@x.test", now=104.0)
    assert attempts.blocked("a@x.test", now=104.0) == 296  # window started at 100


def test_key_is_lowercased_and_stripped():
    for _ in range(5):
        attempts.record_failure("  A@X.test ", now=0.0)
    assert attempts.blocked("a@x.TEST", now=1.0) is not None


def test_window_expiry_unblocks_and_restarts():
    for _ in range(5):
        attempts.record_failure("a@x.test", now=0.0)
    assert attempts.blocked("a@x.test", now=299.0) == 1
    assert attempts.blocked("a@x.test", now=300.0) is None
    attempts.record_failure("a@x.test", now=301.0)  # fresh window, one failure
    assert attempts.blocked("a@x.test", now=301.0) is None


def test_reset_and_isolation_between_emails():
    for _ in range(5):
        attempts.record_failure("a@x.test", now=0.0)
    assert attempts.blocked("b@x.test", now=0.0) is None
    attempts.reset("a@x.test")
    assert attempts.blocked("a@x.test", now=0.0) is None


def test_tracked_emails_are_bounded(monkeypatch):
    monkeypatch.setattr(attempts, "MAX_TRACKED", 3)
    for i in range(10):
        attempts.record_failure(f"u{i}@x.test", now=float(i))
    assert len(attempts._entries) == 3
    assert "u9@x.test" in attempts._entries and "u0@x.test" not in attempts._entries


def _fail(client, email, n):
    for _ in range(n):
        assert login(client, email, "wrong").status_code == 401


def test_sixth_attempt_is_429_even_with_right_password(client):
    _fail(client, ANA[0], 5)
    r = login(client, *ANA)
    assert r.status_code == 429
    body = r.json()
    assert body["error"] == "too_many_attempts"
    assert body["detail"].startswith("Too many failed sign-ins. Try again in ")
    assert 1 <= int(r.headers["Retry-After"]) <= 300


def test_success_resets_the_counter(client):
    _fail(client, ANA[0], 4)
    assert login(client, *ANA).status_code == 200
    _fail(client, ANA[0], 4)
    assert login(client, *ANA).status_code == 200


def test_unknown_email_is_limited_the_same_way(client):
    _fail(client, "ghost@konecto.test", 5)
    r = login(client, "GHOST@konecto.test", "x")
    assert r.status_code == 429 and r.json()["error"] == "too_many_attempts"


def test_other_email_is_unaffected(client):
    _fail(client, ANA[0], 5)
    assert login(client, *BEN).status_code == 200


def test_window_expiry_through_the_api(client, monkeypatch):
    _fail(client, ANA[0], 5)
    assert login(client, *ANA).status_code == 429
    real = attempts.time.monotonic
    monkeypatch.setattr(attempts.time, "monotonic", lambda: real() + attempts.WINDOW_SECONDS + 1)
    assert login(client, *ANA).status_code == 200


def test_session_list_has_no_user_id(client):
    from tests.test_routes_auth import auth

    h = auth(client, *ANA)
    client.post("/api/conversation", json={"query": "hola"}, headers=h)
    items = client.get("/api/sessions", headers=h).json()
    assert items and all("user_id" not in i for i in items)
    msgs = client.get(f"/api/sessions/{items[0]['id']}/messages", headers=h).json()
    assert msgs and all("user_id" not in m for m in msgs)
