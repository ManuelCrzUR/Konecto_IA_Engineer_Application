"""HTTP contract of the API (Sprint 4). Request/response bodies only.

POST /api/conversation          ConversationRequest -> ConversationResponse
GET  /api/sessions?q=&limit=    -> list[SessionOut]  (match is null without q)
GET  /api/sessions/{id}/messages -> list[MessageOut]   (404 ErrorOut if unknown)
Errors always use ErrorOut {error, detail}.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel

from app.domain.conversation import SearchHit, StoredMessage
from app.domain.models import ConversationRequest, ConversationResponse

__all__ = [
    "ConversationRequest",
    "ConversationResponse",
    "ErrorOut",
    "MessageOut",
    "SearchMatch",
    "SessionOut",
]


class SearchMatch(SearchHit):
    """`match` of a search result: {where: "title"|"message", snippet}."""


class SessionOut(BaseModel):
    """Explicit field list: the owner's `user_id` is never part of the payload (D-52)."""

    id: uuid.UUID
    title: str
    created_at: datetime
    updated_at: datetime
    match: SearchMatch | None = None


class MessageOut(StoredMessage):
    pass


class ErrorOut(BaseModel):
    error: str
    detail: str | None = None
