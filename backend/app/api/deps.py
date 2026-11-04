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
- get_current_user() -> str | None: always None until login exists (hook,
  D-10). Every sessions_repo call receives its value as user_id.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator

import psycopg
from fastapi import Request

from app.agent.agent import run_agent
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


def get_current_user() -> str | None:
    return None
