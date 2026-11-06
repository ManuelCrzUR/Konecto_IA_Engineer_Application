"""Prompt and message building: pure functions, no LLM."""

import re

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from app.agent.prompts import (
    ONGOING_NOTE,
    SYSTEM_PROMPT,
    build_messages,
    context_line,
    history_window,
)
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


def test_prompt_hides_model_and_handles_small_talk() -> None:
    assert "never name" in SYSTEM_PROMPT
    assert "greetings" in SYSTEM_PROMPT and "off-topic" in SYSTEM_PROMPT


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
    assert msgs[3].content == f"[Context: {context_line(history, 'q2')} {ONGOING_NOTE}]\n\nq2"
    assert str(msgs[3].content).count("[Context:") == 1
    assert "P1" in str(msgs[3].content)


def test_history_without_products_only_has_ongoing_note() -> None:
    msgs = build_messages("q", [turn("user", "a"), turn("assistant", "b")])
    assert [type(m) for m in msgs] == [SystemMessage, HumanMessage, AIMessage, HumanMessage]
    assert msgs[-1].content == f"[Context: {ONGOING_NOTE}]\n\nq"


def test_empty_history_has_no_ongoing_note() -> None:
    assert build_messages("hola", [])[-1].content == "hola"


def test_window_limits_sent_turns_but_context_scans_all() -> None:
    history = [turn("assistant", "old", ["761A00-11300000/A"])]
    for i in range(29):
        history.append(turn("user" if i % 2 == 0 else "assistant", f"m{i}"))
    msgs = build_messages("and its power?", history, window=10)
    assert len(msgs) == 1 + 10 + 1
    assert sum(isinstance(m, SystemMessage) for m in msgs) == 1
    assert msgs[1].content == "m19"
    assert "761A00-11300000/A" in str(msgs[-1].content)


def test_history_window_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("HISTORY_TURNS", raising=False)
    assert history_window() == 10
    monkeypatch.setenv("HISTORY_TURNS", "4")
    assert history_window() == 4
    history = [turn("user", f"m{i}") for i in range(8)]
    assert len(build_messages("q", history)) == 1 + 4 + 1
    for bad in ("0", "-2", "abc"):
        monkeypatch.setenv("HISTORY_TURNS", bad)
        with pytest.raises(ValueError, match="HISTORY_TURNS"):
            history_window()


def test_context_line_referent_single_product() -> None:
    line = context_line([turn("assistant", pns=["P1"])], "and its power?")
    assert line is not None
    assert "asking about P1" in line and "get_actuator" in line


def test_context_line_several_products_asks_which() -> None:
    line = context_line([turn("assistant", pns=["P1", "P2"])], "and its power?")
    assert line is not None
    assert "P1, P2" in line and "ask the user which product" in line


def test_small_talk_section_not_forced_intro() -> None:
    assert "only when the conversation has no previous turns" in SYSTEM_PROMPT
