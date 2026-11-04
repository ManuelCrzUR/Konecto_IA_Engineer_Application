"""Shared fixtures: golden rows and an isolated Postgres test database."""

import json
import os
from pathlib import Path

import psycopg
import pytest

BACKEND_DIR = Path(__file__).resolve().parent.parent
PROCESSED_JSON = BACKEND_DIR / "data" / "processed" / "actuators.json"
GOLDEN_DRAFT = Path(__file__).resolve().parent / "fixtures" / "golden_draft.json"
SCHEMA_SQL = Path(__file__).resolve().parent.parent / "app" / "db" / "schema.sql"
DEFAULT_TEST_URL = "postgresql://series76:series76@localhost:5432/series76_test"
TRUNCATE_TABLES = ("messages", "sessions", "actuators", "catalog_tables")


@pytest.fixture(scope="session")
def golden_rows() -> list[dict]:
    path = PROCESSED_JSON if PROCESSED_JSON.exists() else GOLDEN_DRAFT
    return json.loads(path.read_text())["rows"]


@pytest.fixture(scope="session")
def pg_conn():
    url = os.environ.get("TEST_DATABASE_URL", DEFAULT_TEST_URL)
    try:
        conn = psycopg.connect(url, autocommit=True, connect_timeout=3)
    except psycopg.OperationalError as exc:
        pytest.skip(f"Postgres unreachable at {url} ({exc}). Start it: docker compose up -d db")
    if SCHEMA_SQL.exists():
        conn.execute(SCHEMA_SQL.read_text())
    yield conn
    conn.close()


@pytest.fixture
def pg(pg_conn):
    pg_conn.autocommit = True
    existing = {
        r[0]
        for r in pg_conn.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"
        )
    }
    tables = [t for t in TRUNCATE_TABLES if t in existing]
    if tables:
        pg_conn.execute(f"TRUNCATE {', '.join(tables)} RESTART IDENTITY CASCADE")
    yield pg_conn


def pytest_collection_modifyitems(items):
    for item in items:
        if {"pg", "pg_conn"} & set(getattr(item, "fixturenames", ())):
            item.add_marker(pytest.mark.integration)
