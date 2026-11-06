"""Password hashing (D-43). Pure functions, no I/O.

Contract:
- hash_password(password: str) -> str: argon2id via pwdlib (PasswordHash.recommended()).
  Never returns or logs the password; two calls give different hashes (random salt).
- verify_password(password: str, password_hash: str) -> bool: False (never raises)
  for a wrong password or a malformed hash.
"""

from __future__ import annotations


def hash_password(password: str) -> str:
    raise NotImplementedError  # Sprint 8, wave 2


def verify_password(password: str, password_hash: str) -> bool:
    raise NotImplementedError  # Sprint 8, wave 2
