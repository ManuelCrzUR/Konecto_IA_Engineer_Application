"""Test users for the optional login (D-43), seeded at API startup after the schema.

Contract:
- TEST_USERS: tuple of (email, password, role), documented in the README:
    ana@konecto.test / ana-series76 / user
    ben@konecto.test / ben-series76 / user
    dev@konecto.test / dev-series76 / developer   (sees the Debug trace)
- seed_test_users(conn) -> int: upsert_user for each one (idempotent, never
  rewrites an existing password hash); returns how many rows exist afterwards.
  Disabled when SEED_TEST_USERS=off (a real deployment would not ship them).
"""

from __future__ import annotations

import os

import psycopg
from psycopg.rows import tuple_row

from app.auth.repo import Role, upsert_user

TEST_USERS: tuple[tuple[str, str, str], ...] = (
    ("ana@konecto.test", "ana-series76", "user"),
    ("ben@konecto.test", "ben-series76", "user"),
    ("dev@konecto.test", "dev-series76", "developer"),
)


def seed_test_users(conn: psycopg.Connection) -> int:
    if os.environ.get("SEED_TEST_USERS", "").strip().lower() == "off":
        return 0
    # Own tuple cursor: the API's pooled connections use dict_row, the tests' do not.
    with conn.cursor(row_factory=tuple_row) as cur:
        cur.execute(
            "SELECT email FROM users WHERE email = ANY(%s)", ([e for e, _, _ in TEST_USERS],)
        )
        existing = {r[0] for r in cur.fetchall()}
    for email, password, role in TEST_USERS:
        if email in existing:
            continue  # argon2 is deliberately slow: hash only users that are missing
        role_: Role = "developer" if role == "developer" else "user"
        upsert_user(conn, email, password, role_)
    with conn.cursor(row_factory=tuple_row) as cur:
        cur.execute("SELECT count(*) FROM users")
        row = cur.fetchone()
    return int(row[0]) if row else 0
