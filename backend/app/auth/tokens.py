"""Opaque bearer tokens (D-43). Pure functions, no I/O.

Contract:
- TOKEN_TTL = timedelta(days=7)
- new_token() -> str: secrets.token_urlsafe(32). Given to the client once, never stored.
- hash_token(token: str) -> str: lowercase hex SHA-256 of the token. This is the only
  form stored in auth_tokens.token_hash (a DB dump cannot be replayed). A fast hash
  is fine here because the token has 256 bits of entropy (unlike a password).
- parse_bearer(header: str | None) -> str | None: "Bearer <token>" (scheme
  case-insensitive, surrounding spaces ignored) -> token; anything else -> None.
"""

from __future__ import annotations

from datetime import timedelta

TOKEN_TTL = timedelta(days=7)


def new_token() -> str:
    raise NotImplementedError  # Sprint 8, wave 2


def hash_token(token: str) -> str:
    raise NotImplementedError  # Sprint 8, wave 2


def parse_bearer(header: str | None) -> str | None:
    raise NotImplementedError  # Sprint 8, wave 2
