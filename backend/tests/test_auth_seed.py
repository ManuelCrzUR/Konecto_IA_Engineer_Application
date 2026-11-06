from app.auth.repo import authenticate
from app.auth.seed import TEST_USERS, seed_test_users


def test_seed_creates_three_users_idempotently(pg, monkeypatch):
    monkeypatch.delenv("SEED_TEST_USERS", raising=False)
    assert seed_test_users(pg) == 3
    roles = [r[0] for r in pg.execute("SELECT role FROM users ORDER BY email").fetchall()]
    assert roles == ["user", "user", "developer"]
    assert seed_test_users(pg) == 3
    assert pg.execute("SELECT count(*) FROM users").fetchone()[0] == 3
    email, password, _ = TEST_USERS[0]
    assert authenticate(pg, email, password) is not None


def test_seed_off_returns_zero_without_touching_db(pg, monkeypatch):
    monkeypatch.setenv("SEED_TEST_USERS", "OFF")
    assert seed_test_users(pg) == 0
    assert pg.execute("SELECT count(*) FROM users").fetchone()[0] == 0


def test_seed_works_on_a_dict_row_connection(pg) -> None:
    """The API's pool opens connections with row_factory=dict_row (main.py); seeding runs there."""
    from psycopg.rows import dict_row, tuple_row

    pg.row_factory = dict_row
    try:
        assert seed_test_users(pg) == 3
    finally:
        pg.row_factory = tuple_row
