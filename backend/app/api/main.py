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
    Then seed_test_users(conn) (D-43) and log how many users exist (never passwords).
    BodyLimitMiddleware caps POST /api/transcribe (and /api/speech, 16 KB) before the body is read (411/413).
    Includes routes_auth, routes_conversation, routes_sessions, routes_transcribe and routes_speech routers (prefix
    "/api"), install_error_handlers(app), and GET /health ->
    {"status": "ok", "actuators": <row count>} (503 database_unavailable via
    the handlers if the DB is down).
- startup_escalator() -> Escalator | None: env STARTUP_ESCALATION = on|off|auto
  (case-insensitive, default auto; anything else raises RuntimeError). auto =
  ingestion.escalate.make_vision_escalator() only if LLM_API_KEY and
  EXTRACT_LLM_MODEL are both set, else None. The escalator is only called when
  the data must be rebuilt from the PDF, so a normal startup with a valid
  committed JSON never spends (D-49, CLAUDE.md §9).
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

from app.api import (
    routes_auth,
    routes_conversation,
    routes_sessions,
    routes_speech,
    routes_transcribe,
)
from app.api.body_limit import BodyLimitMiddleware
from app.api.errors import install_error_handlers
from app.auth.seed import seed_test_users
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
    mode = os.environ.get("STARTUP_ESCALATION", "auto").strip().lower() or "auto"
    if mode == "on":
        return make_vision_escalator()
    if mode == "off":
        return None
    if mode == "auto":
        configured = (
            os.environ.get("LLM_API_KEY", "").strip()
            and os.environ.get("EXTRACT_LLM_MODEL", "").strip()
        )
        return make_vision_escalator() if configured else None
    raise RuntimeError(f"STARTUP_ESCALATION must be on, off or auto (got {mode!r})")


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
        # Test each connection before handing it out: after a long LLM turn an idle
        # connection may have been dropped, and every repo call would hit it.
        check=ConnectionPool.check_connection,
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
                    users = seed_test_users(conn)
                logger.info(status.summary())
                logger.info("Login: %d user(s) in the database", users)
            yield
        finally:
            pool.close()

    app = FastAPI(title="Series 76 Technical Assistant", lifespan=lifespan)
    install_error_handlers(app)
    app.add_middleware(BodyLimitMiddleware)  # /api/transcribe only, before auth and parsing
    app.add_middleware(  # /api/speech: a JSON body of 1,500 characters fits well under 16 KB
        BodyLimitMiddleware,
        path="/api/speech",
        max_bytes=16 * 1024,
        too_large=("text_too_long", "Text is too long"),
    )
    app.include_router(routes_auth.router, prefix="/api")
    app.include_router(routes_conversation.router, prefix="/api")
    app.include_router(routes_sessions.router, prefix="/api")
    app.include_router(routes_transcribe.router, prefix="/api")
    app.include_router(routes_speech.router, prefix="/api")

    @app.get("/health")
    def health() -> dict[str, object]:
        with app.state.pool.connection() as conn:
            return {"status": "ok", "actuators": actuators_repo.count(conn)}

    return app


app: FastAPI = create_app()
