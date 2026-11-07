"""Turns the LLM's text + the tool trace into an AgentResult. Code, not LLM.

Input:  `answer` (LLM text), `trace` (one ToolTrace per tool call), `query` (the
        user's message).
Output: AgentResult(answer, products, trace, guard_triggered).

The pieces live in one module each (contracts in their docstrings):
products.py (products from the trace), guard.py (number and part-number checks,
D-44/D-51), template.py (deterministic fallback answer), persona.py (Axel). This
module only composes them and re-exports their public names.

Contract:
- build_result(answer, trace, query, user_history="", model_id="", *, referent=None,
  candidates=None) -> AgentResult  (`query` alone drives language detection;
  `user_history` is passed to the checks.)
    Empty answer: template answer, EMPTY_TOOL trace entry, guard_triggered True.
    unverified = unverified_numbers(.., referent) + unverified_part_numbers.
    If it is empty: answer unchanged, guard_triggered False.
    Else: answer = template_answer(...), guard_triggered True, and a
    ToolTrace(tool=GUARD_TOOL, params={"unverified": [...], "original_answer":
    answer}, result="template answer used") is appended to the trace.
    Then apply_persona (PERSONA_TOOL entry when something was replaced).
    products = products_from_trace(trace, final answer).
"""

from __future__ import annotations

from app.agent.guard import (
    _product_values,
    allowed_numbers,
    extract_numbers,
    unverified_numbers,
    unverified_part_numbers,
)
from app.agent.numbers import token_values
from app.agent.persona import PERSONA_NAME, _model_name_pattern, apply_persona
from app.agent.products import products_from_trace
from app.agent.template import _TEXT, detect_lang, template_answer
from app.domain.conversation import AgentResult
from app.domain.models import ToolTrace

__all__ = [
    "EMPTY_TOOL", "GUARD_TOOL", "PERSONA_NAME", "PERSONA_TOOL", "_TEXT", "_model_name_pattern",
    "_product_values", "allowed_numbers", "apply_persona", "build_result", "detect_lang",
    "extract_numbers", "products_from_trace", "template_answer", "token_values",
    "unverified_numbers", "unverified_part_numbers",
]  # fmt: skip

GUARD_TOOL = "number_guard"
EMPTY_TOOL = "empty_answer_guard"
PERSONA_TOOL = "persona_guard"


def build_result(
    answer: str,
    trace: list[ToolTrace],
    query: str,
    user_history: str = "",
    model_id: str = "",
    *,
    referent: str | None = None,
    candidates: list[str] | None = None,
) -> AgentResult:
    out = list(trace)
    if not answer.strip():
        # An empty reply (e.g. a reasoning model that spent its token cap) never reaches the
        # user: the deterministic template answers from the trace instead.
        out.append(ToolTrace(tool=EMPTY_TOOL, params={}, result="template answer used"))
        final = template_answer(trace, query, candidates=candidates)
        return AgentResult(
            answer=final, products=products_from_trace(trace, final), trace=out,
            guard_triggered=True,
        )  # fmt: skip
    bad = unverified_numbers(answer, trace, query, user_history, referent=referent)
    bad += unverified_part_numbers(answer, trace, query, user_history)
    triggered = bool(bad)
    final = template_answer(trace, query, candidates=candidates) if triggered else answer
    if triggered:
        params = {"unverified": bad, "original_answer": answer}
        out.append(ToolTrace(tool=GUARD_TOOL, params=params, result="template answer used"))
    final, replaced = apply_persona(final, model_id)
    if replaced:
        result = f"model name replaced with {PERSONA_NAME}"
        out.append(ToolTrace(tool=PERSONA_TOOL, params={"replaced": replaced}, result=result))
    return AgentResult(
        answer=final,
        products=products_from_trace(trace, final),
        trace=out,
        guard_triggered=triggered,
    )
