"""Password hashing (D-43). Pure functions, no I/O.

Contract:
- hash_password(password: str) -> str: argon2id via pwdlib (PasswordHash.recommended()).
  Never returns or logs the password; two calls give different hashes (random salt).
- verify_password(password: str, password_hash: str) -> bool: False (never raises)
  for a wrong password or a malformed hash.
"""

from __future__ import annotations

from pwdlib import PasswordHash

_HASHER = PasswordHash.recommended()


def hash_password(password: str) -> str:
    return _HASHER.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _HASHER.verify(password, password_hash)
    except Exception:  # noqa: BLE001 - malformed or empty hash: treat as a failed login, never raise
        return False
