"""Login endpoints (mounted under "/api"), D-43.

Contract (router = APIRouter(); sync `def` endpoints):
- POST /auth/login  {email: str (1..254), password: str (1..200)}
    -> 200 {token, user: {email, role}}  (auth_repo.authenticate + issue_token)
    -> 401 ApiError("invalid_credentials", "Wrong email or password") for an unknown
       email or a wrong password (same message: no user enumeration).
    -> 429 "too_many_attempts" + Retry-After after 5 attempts per email and client address in
       5 minutes, sliding window (D-52, app.auth.attempts); the password is not checked while blocked.
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

from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, Field

from app.api.deps import get_conn_factory, get_current_user, get_token
from app.api.errors import ApiError
from app.auth import attempts
from app.auth import repo as auth_repo
from app.auth.repo import CurrentUser, Role
from app.db.connection import ConnFactory

router = APIRouter()


class LoginRequest(BaseModel):
    email: str = Field(min_length=1, max_length=254)
    password: str = Field(min_length=1, max_length=200)


class UserOut(BaseModel):
    email: str
    role: Role


class LoginResponse(BaseModel):
    token: str
    user: UserOut


@router.post("/auth/login", response_model=LoginResponse)
def login(
    body: LoginRequest,
    request: Request,
    conn_factory: Annotated[ConnFactory, Depends(get_conn_factory)],
) -> LoginResponse:
    # Direct peer address only: X-Forwarded-For is client-controlled, so it is not trusted.
    key = attempts.make_key(body.email, request.client.host if request.client else None)
    wait = attempts.try_begin(key)  # counts this attempt before any DB or hash work
    if wait is not None:
        raise ApiError(
            429,
            "too_many_attempts",
            f"Too many failed sign-ins. Try again in {wait} seconds.",
            headers={"Retry-After": str(wait)},
        )
    with conn_factory() as conn:
        user = auth_repo.authenticate(conn, body.email, body.password)
        if user is None:
            raise ApiError(401, "invalid_credentials", "Wrong email or password")
        attempts.succeed(key)
        token = auth_repo.issue_token(conn, user.id)
    return LoginResponse(token=token, user=UserOut(email=user.email, role=user.role))


@router.post("/auth/logout", status_code=204)
def logout(
    token: Annotated[str, Depends(get_token)],
    _user: Annotated[CurrentUser, Depends(get_current_user)],
    conn_factory: Annotated[ConnFactory, Depends(get_conn_factory)],
) -> Response:
    with conn_factory() as conn:
        auth_repo.revoke_token(conn, token)
    return Response(status_code=204)


@router.get("/auth/me", response_model=UserOut)
def me(user: Annotated[CurrentUser, Depends(get_current_user)]) -> UserOut:
    return UserOut(email=user.email, role=user.role)
