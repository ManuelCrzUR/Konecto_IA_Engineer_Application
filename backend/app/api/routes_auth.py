"""Login endpoints (mounted under "/api"), D-43.

Contract (router = APIRouter(); sync `def` endpoints):
- POST /auth/login  {email: str (1..254), password: str (1..200)}
    -> 200 {token, user: {email, role}}  (auth_repo.authenticate + issue_token)
    -> 401 ApiError("invalid_credentials", "Wrong email or password") for an unknown
       email or a wrong password (same message: no user enumeration).
- POST /auth/logout  (Bearer required) -> 204; revokes that token only.
- GET  /auth/me      (Bearer required) -> 200 {email, role}.

Everything else under /api requires a valid Bearer token: deps.get_current_user
raises ApiError(401, "unauthorized", "Sign in first") when the header is missing,
malformed, unknown or expired. /health stays public.
Role-based trace (D-43): for role "user" the `debug` list of POST /api/conversation
and the `trace` of GET /api/sessions/{id}/messages are returned EMPTY; only
"developer" receives them. What is stored in Postgres does not change.
"""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter()
