"""FastAPI application factory and startup.

Run (from backend/): uv run uvicorn app.api.main:app --host 0.0.0.0 --port 8000

Contract:
- create_app(database_url=None, *, bootstrap=True) -> FastAPI
    lifespan:
      1. open ConnectionPool(database_url or connection.database_url(),
         min_size=1, max_size=POOL_MAX (10), kwargs={"autocommit": True,
         "row_factory": dict_row}, open=True, wait=True with a clear startup
         error if Postgres is unreachable) -> app.state.pool
      2. if bootstrap: with a pooled connection: apply_schema, then
         ensure_data(conn, escalator=startup_escalator()); log the DataStatus.
         A data failure aborts startup with the clear message (never serve
         doubtful data).
      3. on shutdown: pool.close().
    Includes routes_conversation.router and routes_sessions.router (prefix
    "/api"), install_error_handlers(app), and GET /health ->
    {"status": "ok", "actuators": <row count>} (503 database_unavailable via
    the handlers if the DB is down).
- startup_escalator() -> Escalator | None: None unless env
  STARTUP_ESCALATION is "on" (then ingestion.escalate.make_vision_escalator()).
  The API never spends on vision calls unless explicitly enabled (CLAUDE.md §9).
- app = create_app()   (module level, for uvicorn)
Tests call create_app(<test db url>, bootstrap=False or True) with TestClient.
"""

from __future__ import annotations

import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from urllib.parse import urlsplit

from fastapi import FastAPI
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool, PoolTimeout

from app.api import routes_conversation, routes_sessions
from app.api.errors import install_error_handlers
from app.bootstrap import ensure_data
from app.db import actuators_repo
from app.db.connection import apply_schema
from app.db.connection import database_url as default_database_url
from app.ingestion.escalate import make_vision_escalator
from app.ingestion.pipeline import Escalator

logger = logging.getLogger("series76.api")


def _ensure_app_logging() -> None:
    """uvicorn only configures its own loggers, so series76.* INFO lines had no handler.

    If nobody configured the root logger (plain uvicorn), give it one stderr handler.
    The app logger keeps propagating, so gunicorn, basicConfig or pytest's caplog,
    which own the root logger, receive the records once and nothing is duplicated.
    """
    root = logging.getLogger()
    if not root.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(levelname)s:     %(name)s: %(message)s"))
        root.addHandler(handler)
    app_logger = logging.getLogger("series76")
    if app_logger.level == logging.NOTSET:
        app_logger.setLevel(logging.INFO)


POOL_MAX = 10
POOL_TIMEOUT = 10.0  # seconds to wait for Postgres at startup


def startup_escalator() -> Escalator | None:
    if os.environ.get("STARTUP_ESCALATION", "off").strip().lower() == "on":
        return make_vision_escalator()
    return None


def _redact(url: str) -> str:
    """host:port/db only: never show user or password."""
    parts = urlsplit(url)
    return f"{parts.hostname}:{parts.port or 5432}{parts.path}"


def _open_pool(url: str) -> ConnectionPool:
    pool = ConnectionPool(
        url,
        min_size=1,
        max_size=POOL_MAX,
        kwargs={"autocommit": True, "row_factory": dict_row},
        open=False,
    )
    try:
        pool.open(wait=True, timeout=POOL_TIMEOUT)
    except PoolTimeout as exc:
        pool.close()
        raise RuntimeError(
            f"Cannot reach Postgres at {_redact(url)} - start it: docker compose up -d db"
        ) from exc
    return pool


def create_app(database_url: str | None = None, *, bootstrap: bool = True) -> FastAPI:
    _ensure_app_logging()
    url = database_url or default_database_url()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        pool = _open_pool(url)
        app.state.pool = pool
        try:
            if bootstrap:
                with pool.connection() as conn:
                    apply_schema(conn)
                    status = ensure_data(conn, escalator=startup_escalator())
                logger.info(status.summary())
            yield
        finally:
            pool.close()

    app = FastAPI(title="Series 76 Technical Assistant", lifespan=lifespan)
    install_error_handlers(app)
    app.include_router(routes_conversation.router, prefix="/api")
    app.include_router(routes_sessions.router, prefix="/api")

    @app.get("/health")
    def health() -> dict[str, object]:
        with app.state.pool.connection() as conn:
            return {"status": "ok", "actuators": actuators_repo.count(conn)}

    return app


app: FastAPI = create_app()
