"""Login attempt limiter (D-52): unit tests with a fake clock, then API behaviour."""

import threading

from fastapi.testclient import TestClient

from app.auth import attempts
from tests import test_routes_auth as _routes
from tests.test_routes_auth import ANA, BEN, login

# Reuse the auth API fixtures (fake agent, seeded users, clean tables).
db = _routes.db
client = _routes.client

K = attempts.make_key("a@x.test", "1.1.1.1")


def test_sixth_attempt_blocked_and_reports_wait():
    for i in range(5):
        assert attempts.try_begin(K, now=100.0 + i) is None
    assert attempts.try_begin(K, now=104.0) == 296  # oldest attempt at 100


def test_key_is_lowercased_and_stripped_and_split_by_address():
    assert attempts.make_key("  A@X.test ", "1.1.1.1") == attempts.make_key("a@x.TEST", "1.1.1.1")
    assert attempts.make_key("a@x.test", "1.1.1.1") != attempts.make_key("a@x.test", "2.2.2.2")


def test_sliding_window_frees_slots_one_by_one():
    for t in (0.0, 75.0, 150.0, 225.0, 299.0):
        assert attempts.try_begin(K, now=t) is None
    assert attempts.try_begin(K, now=299.5) is not None  # first not yet expired
    assert attempts.try_begin(K, now=301.0) is None  # attempt at 0 expired, 6th allowed
    assert attempts.try_begin(K, now=302.0) is not None  # 75 s attempt still inside


def test_blocked_attempts_are_not_recorded():
    for _ in range(5):
        attempts.try_begin(K, now=0.0)
    for t in (10.0, 20.0, 299.0):
        assert attempts.try_begin(K, now=t) is not None
    assert attempts.try_begin(K, now=300.0) is None  # block ends with the first window


def test_parallel_attempts_admit_exactly_max():
    results: list[int | None] = []
    barrier = threading.Barrier(40)

    def hit() -> None:
        barrier.wait()
        results.append(attempts.try_begin(K))

    threads = [threading.Thread(target=hit) for _ in range(40)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert results.count(None) == attempts.MAX_FAILURES == 5


def test_succeed_clears_and_isolation_between_keys():
    for _ in range(5):
        attempts.try_begin(K, now=0.0)
    other = attempts.make_key("b@x.test", "1.1.1.1")
    assert attempts.try_begin(other, now=0.0) is None
    attempts.succeed(K)
    assert attempts.try_begin(K, now=0.0) is None


def test_tracked_keys_are_bounded(monkeypatch):
    monkeypatch.setattr(attempts, "MAX_TRACKED", 3)
    for i in range(10):
        attempts.try_begin(f"u{i}", now=float(i))
    assert len(attempts._entries) == 3
    assert "u9" in attempts._entries and "u0" not in attempts._entries


def test_expired_keys_are_evicted_before_oldest(monkeypatch):
    monkeypatch.setattr(attempts, "MAX_TRACKED", 2)
    attempts.try_begin("old", now=0.0)
    attempts.try_begin("fresh", now=1000.0)
    attempts.try_begin("new", now=1000.0)  # "old" expired, "fresh" kept
    assert set(attempts._entries) == {"fresh", "new"}


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


def test_another_client_address_is_not_blocked(client):
    _fail(client, ANA[0], 5)
    assert login(client, *ANA).status_code == 429
    other = TestClient(client.app, client=("9.9.9.9", 4321))
    assert login(other, *ANA).status_code == 200


def test_forwarded_for_is_ignored(client):
    _fail(client, ANA[0], 5)
    r = client.post(
        "/api/auth/login",
        json={"email": ANA[0], "password": ANA[1]},
        headers={"X-Forwarded-For": "8.8.8.8"},
    )
    assert r.status_code == 429


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
