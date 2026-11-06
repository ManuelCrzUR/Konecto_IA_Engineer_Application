"""Shared fixtures: golden rows and an isolated Postgres test database."""

import json
import os
from pathlib import Path

import psycopg
import pytest
from dotenv import dotenv_values

BACKEND_DIR = Path(__file__).resolve().parent.parent
PROCESSED_JSON = BACKEND_DIR / "data" / "processed" / "actuators.json"
GOLDEN_DRAFT = Path(__file__).resolve().parent / "fixtures" / "golden_draft.json"
SCHEMA_SQL = Path(__file__).resolve().parent.parent / "app" / "db" / "schema.sql"
REPO_ENV = BACKEND_DIR.parent / ".env"
# Only the DB-related keys are taken from the root .env (override=False semantics: a real
# environment variable wins); the LLM key must never leak into the tests.
for _k, _v in dotenv_values(REPO_ENV).items():
    if _k in ("DB_PORT", "TEST_DATABASE_URL") and _v:
        os.environ.setdefault(_k, _v)


def get_test_db_url(db: str = "series76_test") -> str:
    """The single source of the test DB URL: TEST_DATABASE_URL, else built from DB_PORT."""
    explicit = os.environ.get("TEST_DATABASE_URL")
    if explicit:
        return explicit
    port = os.environ.get("DB_PORT", "5432")
    return f"postgresql://series76:series76@localhost:{port}/{db}"


# Evaluated after the .env load above; kept for modules that import the constant.
DEFAULT_TEST_URL = get_test_db_url()
TRUNCATE_TABLES = ("auth_tokens", "messages", "sessions", "users", "actuators", "catalog_tables")


@pytest.fixture(scope="session")
def golden_rows() -> list[dict]:
    path = PROCESSED_JSON if PROCESSED_JSON.exists() else GOLDEN_DRAFT
    return json.loads(path.read_text())["rows"]


@pytest.fixture(scope="session")
def pg_conn():
    url = get_test_db_url()
    try:
        conn = psycopg.connect(url, autocommit=True, connect_timeout=3)
    except psycopg.OperationalError as exc:
        if "does not exist" in str(exc):
            # Server is up but the DB is missing (e.g. after `docker compose down -v`):
            # fail loudly; a silent skip would hide every DB test.
            pytest.fail(f"Test database missing at {url}: {exc}. Create it or reset the volume.")
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


@pytest.fixture(autouse=True)
def _no_paid_network(monkeypatch, tmp_path):
    """Tests never reach OpenRouter through app.spend and never write the real spend log.

    A test that needs key status injects `http_get` or `reader` explicitly.
    """
    from app import spend

    def _blocked(url, headers):
        raise AssertionError("network call to OpenRouter attempted in a test")

    monkeypatch.setattr(spend, "_urllib_get", _blocked)
    monkeypatch.setattr(spend, "SPEND_LOG", tmp_path / "spend-log.md")
    monkeypatch.setattr(spend, "SETTLE_S", 0.0)


@pytest.fixture
def test_users(pg):
    """Rows in `users` for the plain ids the isolation tests use ("a", "b", "u1").

    sessions.user_id references users.id (D-43), so a session can only belong to a real user.
    """
    for uid in ("a", "b", "u1"):
        pg.execute(
            "INSERT INTO users (id, email, password_hash) VALUES (%s, %s, 'x')",
            (uid, f"{uid}@test.invalid"),
        )
    return pg


@pytest.fixture
def dev_user(pg):
    """A real `developer` row in users (sessions.user_id has a foreign key to it)."""
    from app.auth.repo import upsert_user

    return upsert_user(pg, "dev@test.invalid", "dev-pass-1", "developer")


@pytest.fixture
def plain_user(pg):
    """A real `user` (no trace) row in users."""
    from app.auth.repo import upsert_user

    return upsert_user(pg, "plain@test.invalid", "plain-pass-1", "user")


def act_as(app, user) -> None:
    """Make every request of `app` run as `user`, skipping the Bearer lookup."""
    from app.api import deps

    app.dependency_overrides[deps.get_current_user] = lambda: user


def pytest_collection_modifyitems(items):
    for item in items:
        if {"pg", "pg_conn"} & set(getattr(item, "fixturenames", ())):
            item.add_marker(pytest.mark.integration)
