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

import psycopg

TEST_USERS: tuple[tuple[str, str, str], ...] = (
    ("ana@konecto.test", "ana-series76", "user"),
    ("ben@konecto.test", "ben-series76", "user"),
    ("dev@konecto.test", "dev-series76", "developer"),
)


def seed_test_users(conn: psycopg.Connection) -> int:
    raise NotImplementedError  # Sprint 8, wave 2
