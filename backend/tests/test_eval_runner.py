"""Eval runner tests: fake run_agent, no LLM, no DB."""

from __future__ import annotations

import threading
import time
from contextlib import nullcontext
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from app.agent import agent as agent_mod
from app.domain.conversation import AgentResult
from app.domain.models import ToolTrace
from eval import run as ev


def _trace(tool: str, **result: Any) -> ToolTrace:
    return ToolTrace(tool=tool, params={}, result=result)


def _prod(pn: str) -> Any:
    return type("P", (), {"part_number": pn})()


def _res(answer: str = "ok", trace: list[ToolTrace] | None = None, pns: list[str] | None = None,
         guard: bool = False) -> AgentResult:  # fmt: skip
    r = AgentResult(answer=answer, trace=trace or [], guard_triggered=guard)
    object.__setattr__(r, "products", [_prod(p) for p in pns or []])
    return r


def _case(**expect: Any) -> ev.Case:
    return ev.Case(id="c", category="lookup", turns=["q"], expect=ev.Expect(**expect))


def test_load_cases_ok_and_errors(tmp_path: Path) -> None:
    f = tmp_path / "c.yaml"
    f.write_text(
        "- {id: a, category: lookup, turns: [hi]}\n- {id: b, category: na, turns: [x, y]}\n"
    )
    assert [c.id for c in ev.load_cases(f)] == ["a", "b"]
    f.write_text("- {id: a, category: lookup, turns: [hi]}\n- {id: a, category: na, turns: [x]}\n")
    with pytest.raises(ValidationError, match="duplicate"):
        ev.load_cases(f)
    f.write_text("- {id: a, category: nope, turns: [hi]}\n")
    with pytest.raises(ValidationError, match="category"):
        ev.load_cases(f)


def test_check_tools_and_status() -> None:
    r = _res(
        trace=[_trace("get_actuator", status="found"), _trace("get_actuator", status="not_found")]
    )
    assert ev.check(_case(tools=["get_actuator"], status="not_found"), r) == []
    assert ev.check(_case(tools=["get_actuator"], status="found"), r)
    assert ev.check(_case(tools=["search_actuators"]), r)


def test_check_products() -> None:
    r = _res(pns=["761A", "762A"])
    assert ev.check(_case(products=["761A"]), r) == []
    assert ev.check(_case(products=["999Z"]), r)
    assert ev.check(_case(no_products=True), r)
    assert ev.check(_case(no_products=True), _res()) == []


def test_check_answer_numbers() -> None:
    assert ev.check(_case(answer_numbers=["1,330"]), _res("Torque is 1330 in-lbs")) == []
    assert ev.check(_case(answer_numbers=["1330"]), _res("Torque is 1,330 in-lbs")) == []
    assert ev.check(_case(answer_numbers=["1,330"]), _res("Torque is 900"))


def test_check_answer_includes() -> None:
    c = _case(answer_includes=["Axel"])
    assert ev.check(c, _res("I am axel, your assistant")) == []
    assert ev.check(c, _res("I am an assistant"))


def test_check_answer_excludes() -> None:
    c = _case(answer_excludes=["9999", "0.75", "System Prompt", "```"])
    assert ev.check(c, _res("Torque is 750 Nm")) == []
    assert ev.check(c, _res("It is 9,999 Nm"))
    assert ev.check(c, _res("It is 0.75 kNm"))
    assert ev.check(c, _res("my SYSTEM PROMPT says"))
    assert ev.check(c, _res("```python\nx\n```"))
    assert ev.check(_case(answer_excludes=["42"]), _res("FLA is 142 A")) == []


def test_injection_category_loads() -> None:
    assert ev.Case(id="i", category="injection", turns=["x"]).category == "injection"


def test_check_out_of_catalog_and_guard() -> None:
    oc = _res(
        trace=[_trace("search_actuators", status="no_match", no_match={"out_of_catalog": True})]
    )
    assert ev.check(_case(out_of_catalog=True), oc) == []
    assert ev.check(_case(out_of_catalog=False), oc)
    assert ev.check(_case(), _res(guard=True))
    assert ev.check(_case(guard_ok=False), _res(guard=True)) == []


def test_multi_turn_history_and_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, list[Any]]] = []

    def fake(query: str, history: Any = None, **_: Any) -> AgentResult:
        calls.append((query, list(history)))
        if query == "boom":
            raise RuntimeError("down")
        return _res(f"a:{query}", pns=["761A"])

    monkeypatch.setattr(agent_mod, "run_agent", fake)
    case = ev.Case(id="m", category="multi_turn", turns=["one", "two"])
    out = ev.run_case(case, llm=None, conn_factory=None)
    assert out.passed and calls[0][1] == []
    h = calls[1][1]
    assert [(t.role, t.content) for t in h] == [("user", "one"), ("assistant", "a:one")]
    assert h[1].part_numbers == ["761A"]

    bad = ev.run_case(ev.Case(id="e", category="na", turns=["boom"]), llm=None, conn_factory=None)
    assert not bad.passed and bad.error == "down"


def test_run_all_preserves_order(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake(query: str, history: Any = None, **_: Any) -> AgentResult:
        time.sleep(0.05 if query == "0" else 0)
        return _res(query)

    monkeypatch.setattr(agent_mod, "run_agent", fake)
    cases = [ev.Case(id=str(i), category="lookup", turns=[str(i)]) for i in range(6)]
    got = ev.run_all(cases, llm_factory=lambda: None, conn_factory=None, workers=3)
    assert [r.id for r in got] == [str(i) for i in range(6)]
    assert threading.active_count() >= 1


def test_render_report() -> None:
    rs = [
        ev.CaseResult(id="a", category="lookup", passed=True, tools=["get_actuator"], seconds=1.5),
        ev.CaseResult(id="b", category="na", passed=False, failures=["x | y"]),
    ]
    md = ev.render_report(rs, "m-1")
    assert "m-1" in md and "1/2" in md and "| lookup | 1/1 | 100% |" in md
    assert "| b | na | FAIL |" in md and "x / y" in md


@pytest.mark.parametrize(
    ("ok", "min_pass", "code"), [(True, "0.9", 0), (False, "0.9", 1), (False, "0", 0)]
)
def test_main_exit_code(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, ok: bool, min_pass: str, code: int
) -> None:
    import app.bootstrap as boot
    import app.db.connection as dbc
    from app import llm

    cases = tmp_path / "c.yaml"
    cases.write_text("- {id: a, category: lookup, turns: [q], expect: {products: [761A]}}\n")
    monkeypatch.setattr(boot, "ensure_data", lambda conn, **k: None)
    monkeypatch.setattr(dbc, "connect", lambda *a, **k: nullcontext())
    monkeypatch.setattr(dbc, "conn_factory", lambda *a, **k: None)
    monkeypatch.setattr(llm, "get_llm", lambda task="agent": None)
    monkeypatch.setattr(
        agent_mod, "run_agent", lambda q, h=None, **k: _res(pns=["761A"] if ok else [])
    )
    out = tmp_path / "r.md"
    argv = ["--cases", str(cases), "--out", str(out), "--min-pass", min_pass]
    assert ev.main(argv) == code
    assert "lookup" in out.read_text()


def test_render_report_includes_transcripts() -> None:
    from eval.run import CaseResult, render_report

    r = CaseResult(
        id="lookup-01", category="lookup", passed=True, tools=["get_actuator"],
        turns=[("torque of 761A00?", "It is 80 Nm.\nSecond line")],
        products=["761A00-11300000/A"], expect={"status": "found"},
    )  # fmt: skip
    md = render_report([r], "m")
    assert "## Transcripts" in md and "**User:** torque of 761A00?" in md
    assert "> It is 80 Nm." in md and "> Second line" in md
    assert "761A00-11300000/A" in md and "'status': 'found'" in md
