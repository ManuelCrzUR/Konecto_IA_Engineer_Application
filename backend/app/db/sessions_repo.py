"""Conversation persistence: `sessions` and `messages`. Parameterized SQL only.

user_id is accepted everywhere and is None until login exists (hook).
"""

from __future__ import annotations

import uuid

import psycopg

from app.domain.conversation import Role, SessionInfo, StoredMessage
from app.domain.models import Product, ToolTrace

TITLE_MAX = 50


def create_session(conn: psycopg.Connection, title: str, user_id: str | None = None) -> SessionInfo:
    """Insert a session. Title is trimmed to TITLE_MAX chars (no LLM)."""
    raise NotImplementedError


def get_session(
    conn: psycopg.Connection, session_id: uuid.UUID, user_id: str | None = None
) -> SessionInfo | None:
    """None when the id does not exist (or belongs to another user)."""
    raise NotImplementedError


def list_sessions(
    conn: psycopg.Connection, user_id: str | None = None, limit: int = 50
) -> list[SessionInfo]:
    """Most recently updated first."""
    raise NotImplementedError


def add_message(
    conn: psycopg.Connection,
    session_id: uuid.UUID,
    role: Role,
    content: str,
    products: list[Product] | None = None,
    trace: list[ToolTrace] | None = None,
) -> StoredMessage:
    """Insert a message (products/trace as jsonb) and bump sessions.updated_at."""
    raise NotImplementedError


def list_messages(conn: psycopg.Connection, session_id: uuid.UUID) -> list[StoredMessage]:
    """Oldest first."""
    raise NotImplementedError
