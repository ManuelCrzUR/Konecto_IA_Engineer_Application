"""run_agent(query, history): the single entry point to the LangChain agent.

Built with langchain.agents.create_agent (no checkpointer: history is ours,
stored in Postgres and passed in). `llm` and `conn_factory` are injectable for
tests (fake chat model, test DB); defaults are app.llm.get_llm("agent") and
app.db.connection.conn_factory().

Contract:
- TraceRecorder(AgentMiddleware): wrap_tool_call times the handler and appends
  ToolTrace(tool=<tool name>, params=<tool call args>, result=<the tool's dict
  output, parsed back from the ToolMessage if it was serialized; the raw string
  if it is not JSON>, duration_ms). One recorder per run_agent call (no shared
  state between calls). A tool that raises: the exception text is recorded as
  result {"error": "<message>"} and returned to the model as an error
  ToolMessage, so the model can recover (no crash).
- run_agent(query, history=None, *, llm=None, conn_factory=None) -> AgentResult
    1. messages = prompts.build_messages(query, history).
    2. agent = create_agent(llm, tools.make_tools(conn_factory),
       middleware=[recorder]); invoke cast("Any", {"messages": messages}) with
       config {"recursion_limit": RECURSION_LIMIT}.
    3. answer = text of the last AIMessage (string content, or the joined
       text blocks if content is a list).
    4. return response.build_result(answer, recorder.trace, query, user_history)
       (user_history = the user turns of `history` joined by newlines).
  Errors:
    - GraphRecursionError (too many steps) -> not raised: result of
      build_result(LOOP_ANSWER, trace, query, user_history) (the guard then may swap in the
      template; that's fine).
    - A provider failure (PROVIDER_ERRORS: openai.APIError, httpx.HTTPError,
      TimeoutError, ConnectionError) -> AgentError(<short reason>) chained from
      the original. The API maps it to 503. Other exceptions are bugs and
      propagate unchanged.
    - LLMConfigError from get_llm propagates unchanged.
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from typing import Any, cast

import httpx
from langchain.agents import create_agent
from langchain.agents.middleware import AgentMiddleware
from langchain.agents.middleware.types import ToolCallRequest
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langgraph.errors import GraphRecursionError
from langgraph.types import Command
from openai import APIError

from app.agent import prompts, response, tools
from app.db.connection import ConnFactory
from app.db.connection import conn_factory as default_conn_factory
from app.domain.conversation import AgentResult, HistoryTurn
from app.domain.models import ToolTrace
from app.llm import get_llm

# Each tool round is 2 graph steps: 25 allows ~12 sequential tool calls (a
# follow-up re-checking 5 products plus a search still fits).
RECURSION_LIMIT = 25
LOOP_ANSWER = "I could not complete the lookup. Please rephrase or give more detail."


# Failures of the LLM provider call (network, auth, rate limit, timeout). Anything
# else raised inside the agent is a bug and propagates unchanged (API -> 500).
PROVIDER_ERRORS: tuple[type[BaseException], ...] = (
    APIError, httpx.HTTPError, TimeoutError, ConnectionError
)


class AgentError(RuntimeError):
    """The LLM call failed (network, auth, rate limit, timeout)."""


def _text(content: Any) -> str:
    if isinstance(content, str):
        return content
    parts = [b if isinstance(b, str) else b.get("text", "") for b in content or []]
    return "".join(p for p in parts if isinstance(p, str))


def _parse(content: Any) -> Any:
    """Tool dicts reach ToolMessage.content as JSON text; give the dict back."""
    if isinstance(content, str):
        try:
            return json.loads(content)
        except ValueError:
            return content
    return content


def _requested_order(messages: list[Any]) -> list[str]:
    return [str(c["id"]) for m in messages if isinstance(m, AIMessage) for c in m.tool_calls]


class TraceRecorder(AgentMiddleware):
    """Records every tool call; turns tool exceptions into error ToolMessages."""

    def __init__(self) -> None:
        super().__init__()
        # (tool_call id, trace) in arrival order. ONE list, appended once per call,
        # so parallel tool threads can never misalign ids and traces.
        self.calls: list[tuple[str, ToolTrace]] = []

    @property
    def trace(self) -> list[ToolTrace]:
        return [t for _, t in self.calls]

    def wrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], ToolMessage | Command[Any]],
    ) -> ToolMessage | Command[Any]:
        call = request.tool_call
        start = time.perf_counter()
        try:
            out = handler(request)
            result = _parse(out.content) if isinstance(out, ToolMessage) else str(out)
        except Exception as exc:  # noqa: BLE001 - the model gets to recover
            result = {"error": str(exc)}
            out = ToolMessage(
                content=json.dumps(result),
                tool_call_id=call["id"],
                name=call["name"],
                status="error",
            )
        ms = round((time.perf_counter() - start) * 1000, 2)
        entry = ToolTrace(tool=call["name"], params=dict(call["args"]), result=result, duration_ms=ms)
        self.calls.append((call["id"] or "", entry))
        return out


def run_agent(
    query: str,
    history: list[HistoryTurn] | None = None,
    *,
    llm: BaseChatModel | None = None,
    conn_factory: ConnFactory | None = None,
) -> AgentResult:
    user_history = "\n".join(h.content for h in history or [] if h.role == "user")
    recorder = TraceRecorder()
    agent = create_agent(
        llm or get_llm("agent"),
        tools.make_tools(conn_factory or default_conn_factory()),
        middleware=[recorder],
    )
    messages = prompts.build_messages(query, history)
    try:
        state = agent.invoke(
            cast("Any", {"messages": messages}),
            config=RunnableConfig(recursion_limit=RECURSION_LIMIT),
        )
    except GraphRecursionError:
        return response.build_result(LOOP_ANSWER, recorder.trace, query, user_history)
    except PROVIDER_ERRORS as exc:
        raise AgentError(f"LLM call failed: {exc}") from exc
    # parallel tool calls finish in any order: report them as the model requested them
    order = _requested_order(state["messages"])
    def rank(call_id: str) -> int:  # unknown/empty ids (some providers) go last, stably
        return order.index(call_id) if call_id in order else len(order)

    trace = [t for _, t in sorted(recorder.calls, key=lambda p: rank(p[0]))]
    ai = [m for m in state["messages"] if isinstance(m, AIMessage)]
    answer = _text(ai[-1].content) if ai else ""
    return response.build_result(answer, trace, query, user_history)
