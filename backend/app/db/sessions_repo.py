"""Conversation persistence: `sessions` and `messages`. Parameterized SQL only.

user_id is accepted everywhere and is None until login exists (hook).
With user_id=None only sessions whose user_id IS NULL are visible; with a
value only that user's sessions are.

Search lives in app.db.sessions_search (D-37).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from app.domain.conversation import Role, SessionInfo, StoredMessage
from app.domain.models import Product, ToolTrace

TITLE_MAX = 50

_SESSION_COLS = "id, user_id, title, created_at, updated_at"
_MESSAGE_COLS = "id, session_id, role, content, products, trace, created_at"
# `IS NOT DISTINCT FROM` matches NULL = NULL, so one query serves both cases.
USER_MATCH = "user_id IS NOT DISTINCT FROM %s"


def _clean_title(title: str) -> str:
    """Strip, collapse whitespace, cut to TITLE_MAX chars (ellipsis within the limit)."""
    clean = " ".join(title.split())
    if len(clean) <= TITLE_MAX:
        return clean
    return clean[: TITLE_MAX - 1].rstrip() + "…"


def _to_message(row: dict) -> StoredMessage:
    return StoredMessage(
        id=row["id"],
        session_id=row["session_id"],
        role=row["role"],
        content=row["content"],
        products=[Product.model_validate(p) for p in row["products"]],
        trace=[ToolTrace.model_validate(t) for t in row["trace"]],
        created_at=row["created_at"],
    )


def create_session(conn: psycopg.Connection, title: str, user_id: str | None = None) -> SessionInfo:
    """Insert a session. Title is trimmed to TITLE_MAX chars (no LLM)."""
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            f"INSERT INTO sessions (user_id, title) VALUES (%s, %s) RETURNING {_SESSION_COLS}",
            (user_id, _clean_title(title)),
        )
        row = cur.fetchone()
    assert row is not None
    return SessionInfo.model_validate(row)


def get_session(
    conn: psycopg.Connection, session_id: uuid.UUID, user_id: str | None = None
) -> SessionInfo | None:
    """None when the id does not exist (or belongs to another user)."""
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            f"SELECT {_SESSION_COLS} FROM sessions WHERE id = %s AND {USER_MATCH}",
            (session_id, user_id),
        )
        row = cur.fetchone()
    return SessionInfo.model_validate(row) if row else None


def list_sessions(
    conn: psycopg.Connection, user_id: str | None = None, limit: int = 50
) -> list[SessionInfo]:
    """Most recently updated first."""
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            f"SELECT {_SESSION_COLS} FROM sessions WHERE {USER_MATCH} "
            "ORDER BY updated_at DESC, id LIMIT %s",
            (user_id, limit),
        )
        return [SessionInfo.model_validate(r) for r in cur.fetchall()]


def add_message(
    conn: psycopg.Connection,
    session_id: uuid.UUID,
    role: Role,
    content: str,
    products: list[Product] | None = None,
    trace: list[ToolTrace] | None = None,
) -> StoredMessage:
    """Insert a message (products/trace as jsonb) and bump sessions.updated_at."""
    products_json = Jsonb([p.model_dump(mode="json") for p in products or []])
    trace_json = Jsonb([t.model_dump(mode="json") for t in trace or []])
    # One transaction: the message and the session bump succeed or fail together.
    with conn.transaction(), conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            "INSERT INTO messages (session_id, role, content, products, trace) "
            f"VALUES (%s, %s, %s, %s, %s) RETURNING {_MESSAGE_COLS}",
            (session_id, role, content, products_json, trace_json),
        )
        row = cur.fetchone()
        cur.execute("UPDATE sessions SET updated_at = now() WHERE id = %s", (session_id,))
    assert row is not None
    return _to_message(row)


def try_lock_session(
    conn: psycopg.Connection,
    session_id: uuid.UUID,
    stale_after: timedelta = timedelta(minutes=2),
) -> datetime | None:
    """Take the per-session turn lock (D-46); None if another turn holds a fresh one.

    One atomic UPDATE: a lock older than `stale_after` (crashed worker) is retaken.
    Returns the lock's own timestamp: pass it to unlock_session so a turn that ran
    past `stale_after` cannot release a lock another turn has taken since.
    """
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE sessions SET busy_since = clock_timestamp() WHERE id = %s "
            "AND (busy_since IS NULL OR busy_since < now() - %s) RETURNING busy_since",
            (session_id, stale_after),
        )
        row = cur.fetchone()
    if row is None:
        return None
    return row["busy_since"] if isinstance(row, dict) else row[0]


def unlock_session(
    conn: psycopg.Connection, session_id: uuid.UUID, token: datetime | None = None
) -> None:
    """Release the turn lock (idempotent); with `token`, only if this turn still owns it."""
    with conn.cursor() as cur:
        if token is None:
            cur.execute("UPDATE sessions SET busy_since = NULL WHERE id = %s", (session_id,))
        else:
            cur.execute(
                "UPDATE sessions SET busy_since = NULL WHERE id = %s AND busy_since = %s",
                (session_id, token),
            )


def list_messages(conn: psycopg.Connection, session_id: uuid.UUID) -> list[StoredMessage]:
    """Oldest first."""
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            f"SELECT {_MESSAGE_COLS} FROM messages WHERE session_id = %s ORDER BY created_at, id",
            (session_id,),
        )
        return [_to_message(r) for r in cur.fetchall()]
