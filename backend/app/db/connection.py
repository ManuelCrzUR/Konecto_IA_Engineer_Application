"""Postgres connections (psycopg 3). No ORM.

Contract:
- database_url() -> str: DATABASE_URL from the environment (loads .env), or the
  local default postgresql://series76:series76@localhost:5432/series76.
- connect(url=None) -> psycopg.Connection with dict_row row factory.
- apply_schema(conn) -> None: runs schema.sql (idempotent).
- conn_factory(url=None) -> Callable[[], ContextManager[Connection]]: what the
  tools and the API receive, so tests can pass the test database.
"""

from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractContextManager
from pathlib import Path

import psycopg

SCHEMA_SQL = Path(__file__).with_name("schema.sql")
DEFAULT_URL = "postgresql://series76:series76@localhost:5432/series76"

ConnFactory = Callable[[], AbstractContextManager[psycopg.Connection]]


def database_url() -> str:
    raise NotImplementedError


def connect(url: str | None = None) -> psycopg.Connection:
    raise NotImplementedError


def apply_schema(conn: psycopg.Connection) -> None:
    raise NotImplementedError


def conn_factory(url: str | None = None) -> ConnFactory:
    raise NotImplementedError
