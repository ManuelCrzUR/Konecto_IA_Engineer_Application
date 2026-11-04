"""HTTP contract of the API (Sprint 4). Request/response bodies only.

POST /api/conversation          ConversationRequest -> ConversationResponse
GET  /api/sessions              -> list[SessionOut]
GET  /api/sessions/{id}/messages -> list[MessageOut]   (404 ErrorOut if unknown)
Errors always use ErrorOut {error, detail}.
"""

from __future__ import annotations

from pydantic import BaseModel

from app.domain.conversation import SessionInfo, StoredMessage
from app.domain.models import ConversationRequest, ConversationResponse

__all__ = [
    "ConversationRequest",
    "ConversationResponse",
    "ErrorOut",
    "MessageOut",
    "SessionOut",
]


class SessionOut(SessionInfo):
    pass


class MessageOut(StoredMessage):
    pass


class ErrorOut(BaseModel):
    error: str
    detail: str | None = None
