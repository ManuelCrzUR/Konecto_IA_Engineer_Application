"""POST /api/conversation: one user turn -> agent -> persisted answer.

Contract (router = APIRouter(); path "/conversation", mounted under "/api"):
  Request  ConversationRequest {session_id?: uuid, query: str (1..2000, stripped)}
  Response ConversationResponse {session_id, answer, products[], debug[]}
           (debug = the AgentResult trace, ALWAYS present; the app hides it).
Steps (sync `def` endpoint; FastAPI runs it in its threadpool). DB steps use
short `with conn_factory() as conn:` blocks (1-3, then 5); no connection is
held while the agent runs, because its tools borrow from the same pool.
  1. user = get_current_user(). If session_id is given: sessions_repo.get_session
     (conn, id, user) or ApiError(404, "session_not_found", "No conversation with
     id <id>"). Never create a session by accident. Without session_id:
     create_session(conn, title=query, user_id=user) (title cut to 50 chars by
     the repo).
  2. history = to_history(list_messages(conn, session_id))  — BEFORE saving the
     new message.
  3. add_message(conn, session_id, "user", query)  — committed now (autocommit
     pool), so a later agent failure does not lose it.
  4. result = agent(query, history, conn_factory=<get_conn_factory>).
     AgentError / LLMConfigError propagate to the handlers (503); the user
     message stays saved and no assistant message is written.
  5. add_message(conn, session_id, "assistant", result.answer, result.products,
     result.trace).
  Header X-Session-Id: <uuid> is set on the success response and, once the
     session exists, on any failure after step 3 (the exception gets a
     `session_id` attribute that the handlers in errors.py turn into the header).
     A client that got a 503 retries with that id instead of creating a duplicate
     session. The body of errors stays {error, detail}.
  6. return ConversationResponse(session_id=..., answer=result.answer,
     products=result.products, debug=result.trace).
- to_history(messages: list[StoredMessage]) -> list[HistoryTurn]: role and
  content as stored; assistant turns get part_numbers = [p.part_number for p
  in products]; user turns get [].
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Response

from app.api.deps import AgentRunner, get_agent, get_conn_factory, get_current_user
from app.api.errors import ApiError
from app.db import sessions_repo
from app.db.connection import ConnFactory
from app.domain.conversation import HistoryTurn, StoredMessage
from app.domain.models import ConversationRequest, ConversationResponse

router = APIRouter()


def to_history(messages: list[StoredMessage]) -> list[HistoryTurn]:
    """Stored messages -> agent history; assistant turns carry their product part numbers."""
    return [
        HistoryTurn(
            role=m.role,
            content=m.content,
            part_numbers=[p.part_number for p in m.products] if m.role == "assistant" else [],
        )
        for m in messages
    ]


@router.post("/conversation", response_model=ConversationResponse)
def post_conversation(
    body: ConversationRequest,
    response: Response,
    conn_factory: Annotated[ConnFactory, Depends(get_conn_factory)],
    agent: Annotated[AgentRunner, Depends(get_agent)],
    user: Annotated[str | None, Depends(get_current_user)],
) -> ConversationResponse:
    # Connections are borrowed only around the DB steps, never held while the LLM
    # runs: the agent's tools draw from the same pool (D-32).
    with conn_factory() as conn:
        if body.session_id is not None:
            session = sessions_repo.get_session(conn, body.session_id, user)
            if session is None:
                raise ApiError(
                    404, "session_not_found", f"No conversation with id {body.session_id}"
                )
        else:
            session = sessions_repo.create_session(conn, body.query, user)
        history = to_history(sessions_repo.list_messages(conn, session.id))
        # Saved (and committed) before the agent runs: a 503 below never loses it.
        sessions_repo.add_message(conn, session.id, "user", body.query)
    try:
        result = agent(body.query, history, conn_factory=conn_factory)
        with conn_factory() as conn:
            sessions_repo.add_message(
                conn, session.id, "assistant", result.answer, result.products, result.trace
            )
    except Exception as exc:
        exc.session_id = session.id  # type: ignore[attr-defined]  # read by errors.py
        raise
    response.headers["X-Session-Id"] = str(session.id)
    return ConversationResponse(
        session_id=session.id, answer=result.answer, products=result.products, debug=result.trace
    )
