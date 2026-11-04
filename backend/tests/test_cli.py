"""CLI tests: formatter (pure), one-shot and chat loop. No real LLM, no real DB."""

from __future__ import annotations

from typing import Any, Self

import psycopg
import pytest

import cli
from app.agent import agent as agent_mod
from app.domain.conversation import AgentResult, HistoryTurn
from app.domain.models import Product, ToolTrace
from app.llm import LLMConfigError


def make_product(**overrides: Any) -> Product:
    base: dict[str, Any] = {
        "part_number": "761A01-00000000/A",
        "enclosure": "weatherproof",
        "voltage": "110V",
        "phase": 1,
        "service": "on_off",
        "csa_certified": True,
        "has_data": True,
        "fields": {"onoff_torque_in_lbs": 35.0, "duty_cycle_pct": 50.0},
        "notes": [],
    }
    base.update(overrides)
    return Product(**base)


def make_result(
    answer: str = "Answer text.",
    products: list[Product] | None = None,
    trace: list[ToolTrace] | None = None,
    guard_triggered: bool = False,
) -> AgentResult:
    return AgentResult(
        answer=answer,
        products=products or [],
        trace=trace or [],
        guard_triggered=guard_triggered,
    )


class FakeConn:
    def __init__(self) -> None:
        self.closed = False

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc: object) -> None:
        self.closed = True


@pytest.fixture
def prepared(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """Patch the data chain so main() never touches Postgres."""
    seen: dict[str, Any] = {"ensure_kwargs": None, "conn": FakeConn()}

    def fake_connect(url: str | None = None) -> FakeConn:
        return seen["conn"]

    def fake_ensure(conn: Any, **kwargs: Any) -> None:
        seen["ensure_kwargs"] = kwargs

    monkeypatch.setattr(cli, "connect", fake_connect)
    monkeypatch.setattr(cli, "apply_schema", lambda conn: None)
    monkeypatch.setattr(cli, "ensure_data", fake_ensure)
    return seen


def patch_run_agent(
    monkeypatch: pytest.MonkeyPatch, impl: Any
) -> list[tuple[str, list[HistoryTurn]]]:
    """Replace run_agent; returns the list of (query, history copy) per call."""
    calls: list[tuple[str, list[HistoryTurn]]] = []

    def fake(query: str, history: list[HistoryTurn] | None = None, **kwargs: Any) -> AgentResult:
        calls.append((query, list(history or [])))
        return impl(query)

    monkeypatch.setattr(agent_mod, "run_agent", fake)
    return calls


def feed_inputs(monkeypatch: pytest.MonkeyPatch, lines: list[str]) -> None:
    """Feed lines to input(); an exhausted list raises EOFError (end of input)."""
    iterator = iter(lines)

    def fake_input(prompt: str = "") -> str:
        try:
            return next(iterator)
        except StopIteration:
            raise EOFError from None

    monkeypatch.setattr("builtins.input", fake_input)


# --- format_turn (pure) -------------------------------------------------------


def test_format_turn_without_products_is_answer_only() -> None:
    assert cli.format_turn(make_result("Hello.")) == "Hello."


def test_format_turn_product_line_has_key_fields() -> None:
    out = cli.format_turn(make_result("Two options.", [make_product()]))
    lines = out.splitlines()
    assert lines[0] == "Two options."
    assert lines[1] == (
        "  761A01-00000000/A | 110V | weatherproof | onoff_torque_in_lbs=35 | duty_cycle_pct=50"
    )


def test_format_turn_marks_no_data_and_csa_and_notes() -> None:
    product = make_product(
        has_data=False,
        fields={},
        csa_certified=False,
        notes=["Sizes 6 and 7 are not CSA Certified"],
    )
    line = cli.format_turn(make_result("x", [product])).splitlines()[1]
    assert "no data" in line
    assert "not CSA certified" in line
    assert "Sizes 6 and 7 are not CSA Certified" in line


def test_format_turn_hides_trace_without_debug() -> None:
    trace = [ToolTrace(tool="get_actuator", params={"part_number": "x"}, result={})]
    out = cli.format_turn(make_result("x", trace=trace, guard_triggered=True), debug=False)
    assert "[tool]" not in out
    assert "guard" not in out


def test_format_turn_debug_prints_trace_and_guard_note() -> None:
    trace = [
        ToolTrace(
            tool="search_actuators",
            params={"min_torque": 30, "unit": "in-lbs"},
            result={},
            duration_ms=12.4,
        ),
        ToolTrace(tool="get_actuator", params={"part_number": "y"}, result={}, duration_ms=None),
    ]
    out = cli.format_turn(make_result("x", trace=trace, guard_triggered=True), debug=True)
    assert '[tool] search_actuators({"min_torque": 30, "unit": "in-lbs"}) 12 ms' in out
    assert '[tool] get_actuator({"part_number": "y"}) ? ms' in out
    assert "number guard" in out


def test_format_turn_debug_without_guard_has_no_note() -> None:
    out = cli.format_turn(make_result("x", trace=[]), debug=True)
    assert "number guard" not in out


# --- one-shot (-q) ------------------------------------------------------------


def test_one_shot_prints_answer_and_exits_zero(
    monkeypatch: pytest.MonkeyPatch, prepared: dict[str, Any], capsys: pytest.CaptureFixture[str]
) -> None:
    calls = patch_run_agent(monkeypatch, lambda q: make_result(f"Answer to {q}."))

    code = cli.main(["-q", "what is 761A01?"])

    assert code == 0
    assert "Answer to what is 761A01?." in capsys.readouterr().out
    assert calls == [("what is 761A01?", [])]
    assert prepared["conn"].closed is True


def test_data_chain_runs_with_escalation_off(
    monkeypatch: pytest.MonkeyPatch, prepared: dict[str, Any]
) -> None:
    patch_run_agent(monkeypatch, lambda q: make_result())

    cli.main(["-q", "hi"])

    assert prepared["ensure_kwargs"] == {"escalator": None}


def test_one_shot_debug_flag_prints_trace(
    monkeypatch: pytest.MonkeyPatch, prepared: dict[str, Any], capsys: pytest.CaptureFixture[str]
) -> None:
    trace = [ToolTrace(tool="describe_catalog", params={}, result={}, duration_ms=3.0)]
    patch_run_agent(monkeypatch, lambda q: make_result("ok", trace=trace))

    assert cli.main(["-q", "catalog", "--debug"]) == 0
    assert "[tool] describe_catalog({}) 3 ms" in capsys.readouterr().out


def test_one_shot_agent_error_exits_one(
    monkeypatch: pytest.MonkeyPatch, prepared: dict[str, Any], capsys: pytest.CaptureFixture[str]
) -> None:
    def boom(query: str) -> AgentResult:
        raise agent_mod.AgentError("rate limited")

    patch_run_agent(monkeypatch, boom)

    assert cli.main(["-q", "hi"]) == 1
    assert "rate limited" in capsys.readouterr().err


def test_one_shot_llm_config_error_exits_two(
    monkeypatch: pytest.MonkeyPatch, prepared: dict[str, Any], capsys: pytest.CaptureFixture[str]
) -> None:
    def missing(query: str) -> AgentResult:
        raise LLMConfigError("Missing required environment variable AGENT_MODEL")

    patch_run_agent(monkeypatch, missing)

    assert cli.main(["-q", "hi"]) == 2
    assert "AGENT_MODEL" in capsys.readouterr().err


# --- interactive loop ---------------------------------------------------------


def test_loop_passes_history_between_turns(
    monkeypatch: pytest.MonkeyPatch, prepared: dict[str, Any], capsys: pytest.CaptureFixture[str]
) -> None:
    product = make_product()

    def answer(query: str) -> AgentResult:
        if query == "first":
            return make_result("First answer.", [product])
        return make_result("Second answer.")

    calls = patch_run_agent(monkeypatch, answer)
    feed_inputs(monkeypatch, ["first", "second"])

    assert cli.main([]) == 0

    assert [q for q, _ in calls] == ["first", "second"]
    assert calls[0][1] == []
    assert calls[1][1] == [
        HistoryTurn(role="user", content="first"),
        HistoryTurn(
            role="assistant",
            content="First answer.",
            part_numbers=["761A01-00000000/A"],
        ),
    ]
    out = capsys.readouterr().out
    assert "First answer." in out
    assert "Second answer." in out


def test_loop_ignores_blank_lines(
    monkeypatch: pytest.MonkeyPatch, prepared: dict[str, Any]
) -> None:
    calls = patch_run_agent(monkeypatch, lambda q: make_result("ok"))
    feed_inputs(monkeypatch, ["", "   ", "only"])

    assert cli.main([]) == 0
    assert [q for q, _ in calls] == ["only"]


@pytest.mark.parametrize("word", ["exit", "quit", "EXIT"])
def test_loop_quit_words_stop_without_calling_agent(
    monkeypatch: pytest.MonkeyPatch, prepared: dict[str, Any], word: str
) -> None:
    calls = patch_run_agent(monkeypatch, lambda q: make_result("ok"))
    feed_inputs(monkeypatch, [word, "never reached"])

    assert cli.main([]) == 0
    assert calls == []


def test_loop_eof_exits_zero(monkeypatch: pytest.MonkeyPatch, prepared: dict[str, Any]) -> None:
    calls = patch_run_agent(monkeypatch, lambda q: make_result("ok"))
    feed_inputs(monkeypatch, [])

    assert cli.main([]) == 0
    assert calls == []


def test_loop_agent_error_continues_and_keeps_history_clean(
    monkeypatch: pytest.MonkeyPatch, prepared: dict[str, Any], capsys: pytest.CaptureFixture[str]
) -> None:
    def flaky(query: str) -> AgentResult:
        if query == "fails":
            raise agent_mod.AgentError("timeout")
        return make_result("recovered")

    calls = patch_run_agent(monkeypatch, flaky)
    feed_inputs(monkeypatch, ["fails", "works"])

    assert cli.main([]) == 0
    assert "timeout" in capsys.readouterr().err
    # The failed turn is not recorded: the second call starts with empty history.
    assert calls[1] == ("works", [])


def test_loop_llm_config_error_exits_two(
    monkeypatch: pytest.MonkeyPatch, prepared: dict[str, Any], capsys: pytest.CaptureFixture[str]
) -> None:
    def missing(query: str) -> AgentResult:
        raise LLMConfigError("Missing required environment variable LLM_API_KEY")

    patch_run_agent(monkeypatch, missing)
    feed_inputs(monkeypatch, ["hi", "never reached"])

    assert cli.main([]) == 2
    assert "LLM_API_KEY" in capsys.readouterr().err


# --- database --------------------------------------------------------------------


def test_db_unreachable_exits_one_with_hint(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def down(url: str | None = None) -> None:
        raise psycopg.OperationalError("connection refused")

    monkeypatch.setattr(cli, "connect", down)
    patch_run_agent(monkeypatch, lambda q: make_result("should not run"))

    assert cli.main(["-q", "hi"]) == 1
    err = capsys.readouterr().err
    assert "docker compose up -d db" in err
    assert "connection refused" in err
