"""Integration tests for app/db/schema.sql (needs a reachable Postgres)."""

import os
from collections.abc import Iterator
from pathlib import Path

import psycopg
import pytest
from psycopg import errors

pytestmark = pytest.mark.integration

SCHEMA_SQL = Path(__file__).resolve().parents[1] / "app" / "db" / "schema.sql"
DEFAULT_URL = "postgresql://series76:series76@localhost:5432/series76_test"
TEST_SCHEMA = "schema_test"


@pytest.fixture
def conn() -> Iterator[psycopg.Connection]:
    url = os.environ.get("TEST_DATABASE_URL", DEFAULT_URL)
    try:
        c = psycopg.connect(url, autocommit=True, connect_timeout=3)
    except psycopg.OperationalError as exc:
        pytest.skip(f"Postgres not reachable at TEST_DATABASE_URL ({exc})")
    c.execute(f"DROP SCHEMA IF EXISTS {TEST_SCHEMA} CASCADE")
    c.execute(f"CREATE SCHEMA {TEST_SCHEMA}")
    c.execute(f"SET search_path TO {TEST_SCHEMA}")
    c.execute(SCHEMA_SQL.read_text())
    c.execute("INSERT INTO catalog_tables (table_id, title) VALUES ('t1', 'Table 1')")
    yield c
    c.execute(f"DROP SCHEMA IF EXISTS {TEST_SCHEMA} CASCADE")
    c.close()


def insert_actuator(conn: psycopg.Connection, part_number: str = "764A", **overrides: object) -> None:
    row: dict[str, object] = {
        "part_number": part_number,
        "table_id": "t1",
        "enclosure": "weatherproof",
        "certifications": "CSA, CE, UKCA",
        "voltage": "110V",
        "current_type": "AC",
        "phase": 1,
        "service": "on_off",
        "has_data": True,
    }
    row.update(overrides)
    cols = ", ".join(row)
    params = ", ".join(f"%({k})s" for k in row)
    conn.execute(f"INSERT INTO actuators ({cols}) VALUES ({params})", row)


def count(conn: psycopg.Connection, table: str) -> int:
    row = conn.execute(f"SELECT count(*) FROM {table}").fetchone()
    assert row is not None
    return int(row[0])


def test_schema_applies_twice(conn: psycopg.Connection) -> None:
    conn.execute(SCHEMA_SQL.read_text())
    conn.execute(SCHEMA_SQL.read_text())


@pytest.mark.parametrize(
    "overrides",
    [
        {"enclosure": "waterproof"},
        {"onoff_duty_cycle_pct": 150},
        {"duty_cycle_pct": -1},
        {"phase": 2},
        {"service": "x"},
        {"current_type": "XX"},
    ],
)
def test_invalid_values_rejected(conn: psycopg.Connection, overrides: dict[str, object]) -> None:
    with pytest.raises(errors.CheckViolation):
        insert_actuator(conn, **overrides)


def test_unknown_table_id_rejected(conn: psycopg.Connection) -> None:
    with pytest.raises(errors.ForeignKeyViolation):
        insert_actuator(conn, table_id="nope")


def test_duplicate_part_number_rejected(conn: psycopg.Connection) -> None:
    insert_actuator(conn)
    with pytest.raises(errors.UniqueViolation):
        insert_actuator(conn)


def test_upsert_updates_in_place(conn: psycopg.Connection) -> None:
    insert_actuator(conn, onoff_torque_nm=100)
    conn.execute(
        """
        INSERT INTO actuators (part_number, table_id, enclosure, certifications, voltage,
                               current_type, service, has_data, onoff_torque_nm)
        VALUES ('764A', 't1', 'weatherproof', 'CSA', '110V', 'AC', 'on_off', true, 250.5)
        ON CONFLICT (part_number) DO UPDATE
            SET onoff_torque_nm = EXCLUDED.onoff_torque_nm, updated_at = now()
        """
    )
    assert count(conn, "actuators") == 1
    row = conn.execute("SELECT onoff_torque_nm FROM actuators").fetchone()
    assert row is not None
    assert str(row[0]) == "250.5"


def test_session_delete_cascades_messages(conn: psycopg.Connection) -> None:
    row = conn.execute("INSERT INTO sessions (title) VALUES ('chat') RETURNING id").fetchone()
    assert row is not None
    sid = row[0]
    conn.execute(
        "INSERT INTO messages (session_id, role, content) VALUES (%s, 'user', 'hi'), (%s, 'assistant', 'yo')",
        (sid, sid),
    )
    assert count(conn, "messages") == 2
    conn.execute("DELETE FROM sessions WHERE id = %s", (sid,))
    assert count(conn, "messages") == 0


def test_message_role_check(conn: psycopg.Connection) -> None:
    row = conn.execute("INSERT INTO sessions (title) VALUES ('chat') RETURNING id").fetchone()
    assert row is not None
    with pytest.raises(errors.CheckViolation):
        conn.execute(
            "INSERT INTO messages (session_id, role, content) VALUES (%s, 'system', 'x')",
            (row[0],),
        )
