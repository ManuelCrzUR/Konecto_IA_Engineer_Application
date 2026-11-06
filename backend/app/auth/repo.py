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
from pydantic import BaseModel

Role = Literal["user", "developer"]


class CurrentUser(BaseModel):
    id: str
    email: str
    role: Role


def authenticate(conn: psycopg.Connection, email: str, password: str) -> CurrentUser | None:
    raise NotImplementedError  # Sprint 8, wave 2


def issue_token(conn: psycopg.Connection, user_id: str) -> str:
    raise NotImplementedError  # Sprint 8, wave 2


def user_for_token(conn: psycopg.Connection, token: str) -> CurrentUser | None:
    raise NotImplementedError  # Sprint 8, wave 2


def revoke_token(conn: psycopg.Connection, token: str) -> None:
    raise NotImplementedError  # Sprint 8, wave 2


def upsert_user(conn: psycopg.Connection, email: str, password: str, role: Role) -> CurrentUser:
    raise NotImplementedError  # Sprint 8, wave 2
