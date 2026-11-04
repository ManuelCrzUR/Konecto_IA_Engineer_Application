"""Conversation history endpoints (mounted under "/api").

Contract (router = APIRouter(); sync `def` endpoints):
- GET /sessions?limit=50 (1..200) -> list[SessionOut]
    sessions_repo.list_sessions(conn, user_id=get_current_user(), limit),
    most recently updated first. Empty list when there are none.
- GET /sessions/{session_id}/messages -> list[MessageOut]
    404 ApiError("session_not_found", "No conversation with id <id>") when
    get_session(conn, id, user) is None; else list_messages oldest first,
    each with role, content, products and trace.
    A malformed id (not a UUID) -> 422 validation_error (FastAPI path typing).
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from psycopg import Connection

from app.api.deps import get_conn, get_current_user
from app.api.errors import ApiError
from app.api.schemas import MessageOut, SessionOut
from app.db import sessions_repo
from app.domain.conversation import SessionInfo, StoredMessage

router = APIRouter()


@router.get("/sessions", response_model=list[SessionOut])
def list_sessions(
    conn: Annotated[Connection, Depends(get_conn)],
    user_id: Annotated[str | None, Depends(get_current_user)],
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[SessionInfo]:
    return sessions_repo.list_sessions(conn, user_id=user_id, limit=limit)


@router.get("/sessions/{session_id}/messages", response_model=list[MessageOut])
def list_session_messages(
    session_id: uuid.UUID,
    conn: Annotated[Connection, Depends(get_conn)],
    user_id: Annotated[str | None, Depends(get_current_user)],
) -> list[StoredMessage]:
    if sessions_repo.get_session(conn, session_id, user_id=user_id) is None:
        raise ApiError(404, "session_not_found", f"No conversation with id {session_id}")
    return sessions_repo.list_messages(conn, session_id)
