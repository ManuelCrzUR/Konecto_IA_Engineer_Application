"""Users and auth tokens in Postgres (D-43). Parameterized SQL only.

Tables: users(id text, email unique lowercase, password_hash, role 'user'|'developer'),
auth_tokens(token_hash pk, user_id, expires_at). See app/db/schema.sql.

Contract (every function takes an open psycopg connection; autocommit pool):
- CurrentUser (pydantic): id: str, email: str, role: Literal["user", "developer"].
- authenticate(conn, email, password) -> CurrentUser | None: email is stripped and
  lowercased; None for an unknown email OR a wrong password. To avoid timing
  user enumeration, an unknown email still runs one verify_password against a fixed
  dummy hash.
- issue_token(conn, user_id) -> str: new_token(); stores hash_token(token) with
  expires_at = now() + TOKEN_TTL; returns the plain token.
- user_for_token(conn, token) -> CurrentUser | None: joins auth_tokens -> users on
  hash_token(token) AND expires_at > now(); None when missing or expired.
- revoke_token(conn, token) -> None: deletes that token's row (logout). Idempotent.
- upsert_user(conn, email, password, role) -> CurrentUser: INSERT ... ON CONFLICT (email)
  DO NOTHING; never rewrites an existing hash (seeding is idempotent, users can keep
  a changed password). Returns the stored user.
"""

from __future__ import annotations

from typing import Literal

import psycopg
from psycopg.rows import dict_row
from pydantic import BaseModel

from app.auth.passwords import hash_password, verify_password
from app.auth.tokens import TOKEN_TTL, hash_token, new_token

Role = Literal["user", "developer"]


class CurrentUser(BaseModel):
    id: str
    email: str
    role: Role


_COLS = "id, email, role"

# Verified once per process; an unknown email still pays one argon2 verification.
_DUMMY_HASH = hash_password("dummy-password-for-timing")


def _to_user(row: dict | None) -> CurrentUser | None:
    return CurrentUser(**row) if row else None


def authenticate(conn: psycopg.Connection, email: str, password: str) -> CurrentUser | None:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            f"SELECT {_COLS}, password_hash FROM users WHERE email = %s",
            (email.strip().lower(),),
        )
        row = cur.fetchone()
    if row is None:
        verify_password(password, _DUMMY_HASH)
        return None
    if not verify_password(password, row.pop("password_hash")):
        return None
    return CurrentUser(**row)


def issue_token(conn: psycopg.Connection, user_id: str) -> str:
    token = new_token()
    # Housekeeping: expired tokens are already rejected, this only keeps the table small.
    conn.execute("DELETE FROM auth_tokens WHERE expires_at < now()")
    conn.execute(
        "INSERT INTO auth_tokens (token_hash, user_id, expires_at) VALUES (%s, %s, now() + %s)",
        (hash_token(token), user_id, TOKEN_TTL),
    )
    return token


def user_for_token(conn: psycopg.Connection, token: str) -> CurrentUser | None:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            "SELECT u.id, u.email, u.role FROM auth_tokens t JOIN users u ON u.id = t.user_id "
            "WHERE t.token_hash = %s AND t.expires_at > now()",
            (hash_token(token),),
        )
        return _to_user(cur.fetchone())


def revoke_token(conn: psycopg.Connection, token: str) -> None:
    conn.execute("DELETE FROM auth_tokens WHERE token_hash = %s", (hash_token(token),))


def upsert_user(conn: psycopg.Connection, email: str, password: str, role: Role) -> CurrentUser:
    email = email.strip().lower()
    conn.execute(
        "INSERT INTO users (email, password_hash, role) VALUES (%s, %s, %s) "
        "ON CONFLICT (email) DO NOTHING",
        (email, hash_password(password), role),
    )
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(f"SELECT {_COLS} FROM users WHERE email = %s", (email,))
        user = _to_user(cur.fetchone())
    assert user is not None
    return user
