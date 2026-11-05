"""Conversation search over sessions and messages (D-37). Parameterized SQL only.

Contract: search_sessions(conn, q, user_id=None, limit=50) -> list[tuple[SessionInfo, SearchHit]]
- Case-insensitive substring (ILIKE) over sessions.title and messages.content.
- `%`, `_` and `\\` in the user text are escaped; the pattern is a bound parameter.
- Same user scoping and order (updated_at DESC, id) as sessions_repo.list_sessions;
  one query, the first matching message (oldest first) comes from a LATERAL subquery.
- No index: the data is small, a sequential scan is fine.
"""

from __future__ import annotations

import psycopg
from psycopg.rows import dict_row

from app.db.sessions_repo import USER_MATCH
from app.db.snippet import make_snippet
from app.domain.conversation import SearchHit, SessionInfo


def _like_pattern(q: str) -> str:
    """Substring pattern with LIKE wildcards escaped (used with ESCAPE '\\')."""
    esc = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{esc}%"


# Params (positional, in order): pattern, user_id, pattern, limit. The LATERAL only scans messages
# when the title did not match, since a title hit never uses the message.
_SEARCH_SQL = f"""
WITH hits AS (
    SELECT s.*, s.title ILIKE %s ESCAPE '\\' AS title_hit FROM sessions s
    WHERE s.{USER_MATCH}
)
SELECT h.id, h.user_id, h.title, h.created_at, h.updated_at, h.title_hit, m.content AS message
FROM hits h
LEFT JOIN LATERAL (
    SELECT content FROM messages
    WHERE session_id = h.id AND NOT h.title_hit AND content ILIKE %s ESCAPE '\\'
    ORDER BY created_at, id LIMIT 1
) m ON true
WHERE h.title_hit OR m.content IS NOT NULL
ORDER BY h.updated_at DESC, h.id LIMIT %s
"""


def search_sessions(
    conn: psycopg.Connection, q: str, user_id: str | None = None, limit: int = 50
) -> list[tuple[SessionInfo, SearchHit]]:
    """Sessions whose title or any message contains `q` (case-insensitive)."""
    q = q.strip()
    pat = _like_pattern(q)
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(_SEARCH_SQL, (pat, user_id, pat, limit))
        rows = cur.fetchall()
    out: list[tuple[SessionInfo, SearchHit]] = []
    for r in rows:
        title_hit, message = r.pop("title_hit"), r.pop("message")
        info = SessionInfo.model_validate(r)
        if title_hit:
            hit = SearchHit(where="title", snippet=info.title)
        else:
            hit = SearchHit(where="message", snippet=make_snippet(message, q))
        out.append((info, hit))
    return out
