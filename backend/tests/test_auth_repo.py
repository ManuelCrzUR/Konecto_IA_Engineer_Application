from app.auth.repo import (
    authenticate,
    issue_token,
    revoke_token,
    upsert_user,
    user_for_token,
)


def _user(pg, email="ana@x.test", pw="pw-1234", role="user"):
    return upsert_user(pg, email, pw, role)


def test_authenticate_ok_and_normalizes_email(pg):
    u = _user(pg)
    got = authenticate(pg, "  ANA@X.test ", "pw-1234")
    assert got is not None and got.id == u.id and got.role == "user"


def test_authenticate_wrong_password_and_unknown_email(pg):
    _user(pg)
    assert authenticate(pg, "ana@x.test", "bad") is None
    assert authenticate(pg, "nobody@x.test", "pw-1234") is None


def test_token_round_trip_and_revoke(pg):
    u = _user(pg)
    token = issue_token(pg, u.id)
    assert user_for_token(pg, token) == u
    assert user_for_token(pg, token + "x") is None
    revoke_token(pg, token)
    assert user_for_token(pg, token) is None
    revoke_token(pg, token)  # idempotent


def test_expired_token_is_rejected(pg):
    u = _user(pg)
    token = issue_token(pg, u.id)
    pg.execute("UPDATE auth_tokens SET expires_at = now() - interval '1 second'")
    assert user_for_token(pg, token) is None


def test_expiry_is_about_ttl(pg):
    u = _user(pg)
    issue_token(pg, u.id)
    days = pg.execute(
        "SELECT extract(epoch FROM expires_at - now()) / 86400 FROM auth_tokens"
    ).fetchone()[0]
    assert 6.99 < float(days) <= 7


def test_db_never_stores_plain_token_or_password(pg):
    u = _user(pg, pw="plain-pw-xyz")
    token = issue_token(pg, u.id)
    for table in ("users", "auth_tokens"):
        rows = pg.execute(f"SELECT * FROM {table}").fetchall()
        assert rows
        assert token not in repr(rows)
        assert "plain-pw-xyz" not in repr(rows)


def test_upsert_idempotent_and_keeps_existing_hash(pg):
    first = _user(pg, pw="original")
    h1 = pg.execute("SELECT password_hash FROM users").fetchone()[0]
    second = upsert_user(pg, "ANA@x.test", "changed", "developer")
    assert second == first
    assert pg.execute("SELECT count(*) FROM users").fetchone()[0] == 1
    assert pg.execute("SELECT password_hash FROM users").fetchone()[0] == h1
    assert authenticate(pg, "ana@x.test", "original") is not None
    assert authenticate(pg, "ana@x.test", "changed") is None
