"""run_agent(query, history): the single entry point to the LangChain agent.

Built with langchain.agents.create_agent (no checkpointer: history is ours,
stored in Postgres and passed in). Steps:
1. Build messages from `history` (+ a context line with the part numbers
   shown in the previous turn) and `query`.
2. Invoke the agent with make_tools(conn_factory); a middleware records a
   ToolTrace per tool call.
3. response.build_result(): products from tool outputs (code, not LLM) and the
   number guard on the answer text.
`llm` and `conn_factory` are injectable for tests (fake chat model, test DB).
"""

from __future__ import annotations

from langchain_core.language_models import BaseChatModel

from app.db.connection import ConnFactory
from app.domain.conversation import AgentResult, HistoryTurn


def run_agent(
    query: str,
    history: list[HistoryTurn] | None = None,
    *,
    llm: BaseChatModel | None = None,
    conn_factory: ConnFactory | None = None,
) -> AgentResult:
    raise NotImplementedError
