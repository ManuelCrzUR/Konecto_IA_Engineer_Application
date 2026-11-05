"""Prompt and message building: pure functions, no LLM."""

import re

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from app.agent.prompts import SYSTEM_PROMPT, build_messages, context_line
from app.domain.conversation import HistoryTurn


def turn(role: str, content: str = "x", pns: list[str] | None = None) -> HistoryTurn:
    return HistoryTurn(role=role, content=content, part_numbers=pns or [])  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "key",
    [
        "tool",
        "never",
        "convert",
        "get_actuator",
        "language",
        "describe_catalog",
        "CSA",
        "SQL",
        "N/A",
        "search_actuators",
        "Nm",
        "in-lbs",
        "no_match",
        "out_of_catalog",
    ],
)
def test_prompt_mentions_rule_keys(key: str) -> None:
    assert key in SYSTEM_PROMPT


def test_prompt_introduces_assistant_as_axel() -> None:
    assert "Axel" in SYSTEM_PROMPT


def test_prompt_has_no_catalog_digits() -> None:
    # Only the family name and the printed stroke unit ("per 90°") may contain digits.
    assert "Series 76" in SYSTEM_PROMPT and "per 90°" in SYSTEM_PROMPT
    rest = SYSTEM_PROMPT.replace("Series 76", "").replace("per 90°", "")
    assert not re.search(r"\d", rest)


def test_context_line_none_cases() -> None:
    assert context_line(None) is None
    assert context_line([]) is None
    assert context_line([turn("user", pns=["A1"]), turn("assistant")]) is None


def test_context_line_latest_assistant_deduped() -> None:
    history = [
        turn("assistant", pns=["OLD"]),
        turn("user"),
        turn("assistant", pns=["B", "A", "B"]),
        turn("user", pns=["IGNORED"]),
    ]
    line = context_line(history)
    assert line is not None
    assert "B, A." in line
    assert "OLD" not in line and "IGNORED" not in line
    assert "get_actuator" in line


def test_build_messages_without_history() -> None:
    for h in (None, []):
        msgs = build_messages("hi", h)
        assert [type(m) for m in msgs] == [SystemMessage, HumanMessage]
        assert msgs[0].content == SYSTEM_PROMPT
        assert msgs[1].content == "hi"


def test_build_messages_with_history_and_context() -> None:
    history = [turn("user", "q1"), turn("assistant", "a1", ["P1"])]
    msgs = build_messages("q2", history)
    assert [type(m) for m in msgs] == [SystemMessage, HumanMessage, AIMessage, HumanMessage]
    assert sum(isinstance(m, SystemMessage) for m in msgs) == 1
    assert msgs[1].content == "q1" and msgs[2].content == "a1"
    assert msgs[3].content == f"[Context: {context_line(history)}]\n\nq2"
    assert "P1" in str(msgs[3].content)


def test_build_messages_history_without_products_has_no_context() -> None:
    msgs = build_messages("q", [turn("user", "a"), turn("assistant", "b")])
    assert [type(m) for m in msgs] == [SystemMessage, HumanMessage, AIMessage, HumanMessage]
