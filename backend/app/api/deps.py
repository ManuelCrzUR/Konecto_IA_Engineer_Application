"""FastAPI dependencies: DB connections, the agent, the current user (login hook).

Contract:
- The app holds ONE psycopg_pool.ConnectionPool in `app.state.pool`, opened in
  main.lifespan with kwargs {"autocommit": True, "row_factory": dict_row}.
  Autocommit is deliberate: the user's message is saved before the agent runs
  and must stay saved if the agent then fails (503). Multi-statement writes use
  `conn.transaction()` inside the repos (sessions_repo.add_message does).
- get_conn(request) -> Iterator[psycopg.Connection]: `with pool.connection()`
  for the duration of the request.
- get_conn_factory(request) -> ConnFactory: `pool.connection` (what run_agent's
  tools use; each tool call borrows its own pooled connection).
- get_agent() -> AgentRunner: returns app.agent.agent.run_agent. Tests replace
  it with `app.dependency_overrides[get_agent] = lambda: fake`.
- get_token(request) -> str: the Bearer token of the Authorization header, or
  ApiError(401, "unauthorized", "Sign in first") + `WWW-Authenticate: Bearer`.
- get_current_user(request, conn_factory) -> CurrentUser (D-43): get_token, then
  auth_repo.user_for_token on a short pooled borrow (released before the route body,
  so no connection is held during the agent call, D-32). Missing, malformed, unknown
  or expired token -> the same 401. Routes pass `user.id` to every sessions_repo call.
  Login is the only /api route that does not depend on it; /health is public.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from typing import Annotated

import psycopg
from fastapi import Depends, Request

from app.agent.agent import run_agent
from app.api.errors import ApiError
from app.auth import repo as auth_repo
from app.auth.repo import CurrentUser
from app.auth.tokens import parse_bearer
from app.db.connection import ConnFactory
from app.domain.conversation import AgentResult

AgentRunner = Callable[..., AgentResult]  # run_agent(query, history, *, conn_factory=...)


def get_conn(request: Request) -> Iterator[psycopg.Connection]:
    with request.app.state.pool.connection() as conn:
        yield conn


def get_conn_factory(request: Request) -> ConnFactory:
    return request.app.state.pool.connection  # type: ignore[no-any-return]


def get_agent() -> AgentRunner:
    return run_agent


def _unauthorized() -> ApiError:
    return ApiError(401, "unauthorized", "Sign in first", headers={"WWW-Authenticate": "Bearer"})


def get_token(request: Request) -> str:
    token = parse_bearer(request.headers.get("Authorization"))
    if token is None:
        raise _unauthorized()
    return token


def get_current_user(
    token: Annotated[str, Depends(get_token)],
    conn_factory: Annotated[ConnFactory, Depends(get_conn_factory)],
) -> CurrentUser:
    with conn_factory() as conn:
        user = auth_repo.user_for_token(conn, token)
    if user is None:
        raise _unauthorized()
    return user
