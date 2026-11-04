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

import os
from collections.abc import Callable
from contextlib import AbstractContextManager
from pathlib import Path

import psycopg
from dotenv import load_dotenv
from psycopg.rows import dict_row

SCHEMA_SQL = Path(__file__).with_name("schema.sql")
DEFAULT_URL = "postgresql://series76:series76@localhost:5432/series76"

ConnFactory = Callable[[], AbstractContextManager[psycopg.Connection]]


def database_url() -> str:
    load_dotenv()
    return os.environ.get("DATABASE_URL") or DEFAULT_URL


def connect(url: str | None = None) -> psycopg.Connection:
    return psycopg.connect(url or database_url(), row_factory=dict_row)  # type: ignore[arg-type,return-value]


def apply_schema(conn: psycopg.Connection) -> None:
    conn.execute(SCHEMA_SQL.read_text())
    conn.commit()


def conn_factory(url: str | None = None) -> ConnFactory:
    def factory() -> AbstractContextManager[psycopg.Connection]:
        return connect(url)

    return factory
