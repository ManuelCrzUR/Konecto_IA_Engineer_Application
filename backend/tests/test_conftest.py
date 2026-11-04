import pytest


def _has_table(conn, name: str) -> bool:
    return conn.execute("SELECT to_regclass(%s)", (f"public.{name}",)).fetchone()[0] is not None


def test_golden_rows_count(golden_rows):
    assert len(golden_rows) == 68


def test_pg_isolation_write(pg):
    pg.execute("CREATE TEMP TABLE tmp_probe (x int)")
    pg.execute("INSERT INTO tmp_probe VALUES (1)")
    if not _has_table(pg, "sessions"):
        pytest.skip("schema.sql not applied yet")
    pg.execute("INSERT INTO sessions (title) VALUES ('probe')")
    assert pg.execute("SELECT count(*) FROM sessions").fetchone()[0] == 1


def test_pg_isolation_read(pg):
    if not _has_table(pg, "sessions"):
        pytest.skip("schema.sql not applied yet")
    assert pg.execute("SELECT count(*) FROM sessions").fetchone()[0] == 0
