"""App factory, startup, error handlers and dependencies (needs local Postgres)."""

from __future__ import annotations

import logging

import psycopg
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel

from app.agent.agent import AgentError, run_agent
from app.api import main
from app.api.deps import get_agent, get_current_user
from app.api.errors import ApiError
from app.api.main import create_app, startup_escalator
from app.db.connection import SCHEMA_SQL
from app.llm import LLMConfigError
from tests.conftest import get_test_db_url

DB_URL = get_test_db_url("series76_t_api_a")


class Body(BaseModel):
    n: int


@pytest.fixture
def clean_db():
    try:
        conn = psycopg.connect(DB_URL, autocommit=True, connect_timeout=3)
    except psycopg.OperationalError as exc:
        pytest.skip(f"Postgres unreachable ({exc})")
    conn.execute(SCHEMA_SQL.read_text())
    conn.execute("TRUNCATE messages, sessions, actuators, catalog_tables RESTART IDENTITY CASCADE")
    yield
    conn.close()


def _add_test_routes(app: FastAPI) -> None:
    def boom(exc: Exception):
        def route() -> None:
            raise exc

        return route

    for path, exc in {
        "/t/api": ApiError(409, "conflict", "already there"),
        "/t/agent": AgentError("model timed out"),
        "/t/llmcfg": LLMConfigError("AGENT_MODEL is not set"),
        "/t/db": psycopg.OperationalError("connection to server at 10.0.0.1 failed"),
        "/t/value": ValueError("secret internal detail"),
    }.items():
        app.add_api_route(path, boom(exc))

    @app.post("/t/body")
    def body(b: Body) -> int:
        return b.n


@pytest.fixture
def client(clean_db):
    app = create_app(DB_URL, bootstrap=False)
    _add_test_routes(app)
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


def test_health_after_bootstrap(clean_db, caplog):
    with (
        caplog.at_level(logging.INFO, logger="series76.api"),
        TestClient(create_app(DB_URL, bootstrap=True)) as c,
    ):
        assert c.get("/health").json() == {"status": "ok", "actuators": 68}
    assert "Data ready: 68 actuators (source: " in caplog.text


def test_data_ready_logged_when_db_already_full(clean_db, caplog):
    with TestClient(create_app(DB_URL, bootstrap=True)):
        pass  # first start fills the database
    with (
        caplog.at_level(logging.INFO, logger="series76.api"),
        TestClient(create_app(DB_URL, bootstrap=True)),
    ):
        pass
    assert "Data ready: 68 actuators (source: db)" in caplog.text


def test_health_without_bootstrap_is_empty(client):
    assert client.get("/health").json() == {"status": "ok", "actuators": 0}


@pytest.mark.parametrize(
    ("path", "status", "error", "detail"),
    [
        ("/t/api", 409, "conflict", "already there"),
        (
            "/t/agent",
            503,
            "llm_unavailable",
            "The language model is unavailable. Try again shortly.",
        ),
        ("/t/llmcfg", 503, "llm_not_configured", "AGENT_MODEL is not set"),
        ("/t/db", 503, "database_unavailable", None),
        ("/t/value", 500, "internal_error", "Unexpected server error"),
        ("/nope", 404, "http_404", "Not Found"),
    ],
)
def test_error_formats(client, path, status, error, detail):
    r = client.get(path)
    assert r.status_code == status
    body = r.json()
    assert body["error"] == error
    assert set(body) == {"error", "detail"}
    if detail is not None:
        assert body["detail"] == detail


def test_db_error_does_not_leak_host(client):
    assert "10.0.0.1" not in client.get("/t/db").text


def test_500_never_leaks_exception_text(client, caplog):
    with caplog.at_level(logging.ERROR, logger="series76.api"):
        r = client.get("/t/value")
    assert "secret internal detail" not in r.text
    assert "secret internal detail" in caplog.text  # logged with traceback


def test_request_validation_error(client):
    r = client.post("/t/body", json={"n": "abc"})
    assert r.status_code == 422
    assert r.json()["error"] == "validation_error"
    assert "n" in r.json()["detail"]


def test_dependencies():
    assert get_current_user() is None
    assert get_agent() is run_agent


def test_startup_escalator(monkeypatch):
    monkeypatch.delenv("STARTUP_ESCALATION", raising=False)
    assert startup_escalator() is None
    monkeypatch.setenv("STARTUP_ESCALATION", "off")
    assert startup_escalator() is None
    monkeypatch.setattr(main, "make_vision_escalator", lambda: lambda t, b: [])
    monkeypatch.setenv("STARTUP_ESCALATION", "on")
    assert callable(startup_escalator())


def test_unreachable_db_fails_clearly(monkeypatch):
    monkeypatch.setattr(main, "POOL_TIMEOUT", 1.0)
    app = create_app("postgresql://u:hunter2@localhost:1/nodb", bootstrap=False)
    with pytest.raises(RuntimeError) as exc_info, TestClient(app):
        pass
    msg = str(exc_info.value)
    assert "Cannot reach Postgres at localhost:1/nodb" in msg
    assert "docker compose up -d db" in msg
    assert "hunter2" not in msg


def test_no_connection_held_while_agent_runs(clean_db, monkeypatch):
    """Pool of ONE connection: the agent's tools must still get it (D-32)."""
    from app.api import deps
    from app.api import main as main_mod
    from app.domain.conversation import AgentResult

    monkeypatch.setattr(main_mod, "POOL_MAX", 1)
    app = create_app(DB_URL, bootstrap=False)

    def agent(query, history, *, conn_factory):
        with conn_factory() as conn:  # what a tool does
            conn.execute("SELECT 1")
        return AgentResult(answer="ok")

    app.dependency_overrides[deps.get_agent] = lambda: agent
    with TestClient(app) as c:
        app.state.pool.timeout = 3  # fail fast instead of hanging if a conn is held
        r = c.post("/api/conversation", json={"query": "hello"})
    assert r.status_code == 200, r.text


def test_503_does_not_leak_provider_text(client, caplog):
    r = client.get("/t/agent")
    assert r.status_code == 503 and "model timed out" not in r.text
    assert "model timed out" in caplog.text  # still logged for the operator
