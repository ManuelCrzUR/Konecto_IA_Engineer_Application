"""Uniform error bodies: every error response is ErrorOut {error, detail}.

Contract:
- ApiError(status, error, detail=None): raised by routes for expected errors
  (e.g. ApiError(404, "session_not_found", "No session with id ...")).
- install_error_handlers(app) registers handlers so that:
    ApiError                 -> its status, {error, detail}
    RequestValidationError   -> 422, {"error": "validation_error", "detail": <short,
                                 human-readable summary of the first errors>}
    StarletteHTTPException   -> its status, {"error": "http_<status>", "detail": exc.detail}
                                 (e.g. unknown route -> 404 "http_404")
    AgentError               -> 503, {"error": "llm_unavailable", "detail": <generic
                                 message>}; the provider's reason is only logged.
    LLMConfigError           -> 503, {"error": "llm_not_configured", "detail": <var name msg>}
    psycopg.OperationalError -> 503, {"error": "database_unavailable", "detail": ...}
    (AgentError, LLMConfigError, OperationalError and any other Exception also add
     the header `X-Session-Id` when the exception carries a `session_id` attribute,
     set by POST /api/conversation once the session exists.)
    any other Exception      -> 500, {"error": "internal_error", "detail": "Unexpected
                                 server error"}; the traceback is logged, never returned.
"""

from __future__ import annotations

import logging

import psycopg
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.agent.agent import AgentError
from app.api.schemas import ErrorOut
from app.llm import LLMConfigError

logger = logging.getLogger("series76.api")


class ApiError(Exception):
    def __init__(
        self,
        status: int,
        error: str,
        detail: str | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(detail or error)
        self.status, self.error, self.detail, self.headers = status, error, detail, headers


def _reply(
    status: int, error: str, detail: str | None, exc: Exception | None = None
) -> JSONResponse:
    sid = getattr(exc, "session_id", None)
    headers = dict(getattr(exc, "headers", None) or {})
    if sid is not None:
        headers["X-Session-Id"] = str(sid)
    return JSONResponse(
        ErrorOut(error=error, detail=detail).model_dump(),
        status_code=status,
        headers=headers or None,
    )


def _summarize(exc: RequestValidationError) -> str:
    parts = []
    for err in exc.errors()[:3]:
        loc = ".".join(str(p) for p in err.get("loc", ()))
        parts.append(f"{loc}: {err.get('msg', 'invalid')}")
    return "; ".join(parts) or "Invalid request"


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def _api(_: Request, exc: ApiError) -> JSONResponse:
        return _reply(exc.status, exc.error, exc.detail, exc)

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError) -> JSONResponse:
        return _reply(422, "validation_error", _summarize(exc))

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        return _reply(exc.status_code, f"http_{exc.status_code}", str(exc.detail))

    @app.exception_handler(AgentError)
    async def _agent(_: Request, exc: AgentError) -> JSONResponse:
        # The provider's error text stays in the log; clients get a generic reason.
        logger.warning("Agent failed: %s", exc)
        return _reply(
            503, "llm_unavailable", "The language model is unavailable. Try again shortly.", exc
        )

    @app.exception_handler(LLMConfigError)
    async def _llm_config(_: Request, exc: LLMConfigError) -> JSONResponse:
        return _reply(503, "llm_not_configured", str(exc), exc)

    @app.exception_handler(psycopg.OperationalError)
    async def _db(_: Request, exc: psycopg.OperationalError) -> JSONResponse:
        logger.error("Database unavailable: %s", exc)
        return _reply(
            503, "database_unavailable", "The database is unavailable. Try again shortly.", exc
        )

    @app.exception_handler(Exception)
    async def _unexpected(_: Request, exc: Exception) -> JSONResponse:
        logger.error("Unhandled error", exc_info=(type(exc), exc, exc.__traceback__))
        return _reply(500, "internal_error", "Unexpected server error", exc)
