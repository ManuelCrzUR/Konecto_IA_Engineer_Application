"""Tests for agent/agent.py: scripted fake chat model, real test Postgres. No real LLM."""

from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Any

import pytest
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from pydantic import Field

from app.agent import agent as agent_mod
from app.agent.agent import LOOP_ANSWER, AgentError, run_agent
from app.db import actuators_repo as repo
from app.db import connection
from app.domain.conversation import HistoryTurn
from app.domain.models import Catalog
from tests.conftest import DEFAULT_TEST_URL, PROCESSED_JSON

CATALOG = Catalog.model_validate_json(PROCESSED_JSON.read_text())
PN = "764A00-11300000/A"
ROW = next(r for r in CATALOG.rows if r.part_number == PN)


class FakeLLM(GenericFakeChatModel):
    """Scripted replies; records the messages of every call; bind_tools is a no-op."""

    seen: list[list[BaseMessage]] = Field(default_factory=list)

    def bind_tools(self, tools: Any, **kwargs: Any) -> FakeLLM:
        return self

    def _generate(self, messages: list[BaseMessage], *args: Any, **kwargs: Any) -> Any:
        self.seen.append(list(messages))
        return super()._generate(messages, *args, **kwargs)


def fake(*msgs: AIMessage) -> FakeLLM:
    return FakeLLM(messages=iter(msgs), seen=[])


def call(name: str, args: dict, cid: str = "c1") -> AIMessage:
    return AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": cid}])


@pytest.fixture
def factory(pg):
    repo.upsert_catalog(pg, CATALOG)
    return connection.conn_factory(os.environ.get("TEST_DATABASE_URL", DEFAULT_TEST_URL))


def test_get_actuator_trace_and_products(factory):
    llm = fake(call("get_actuator", {"part_number": "764A00-11300000"}), AIMessage(content="ok"))
    r = run_agent("Details of 764A00-11300000", llm=llm, conn_factory=factory)
    assert len(r.trace) == 1
    t = r.trace[0]
    assert t.tool == "get_actuator"
    assert t.params == {"part_number": "764A00-11300000"}
    assert isinstance(t.result, dict) and t.result["status"] == "found"
    assert t.result["actuator"]["part_number"] == PN
    assert t.duration_ms is not None and t.duration_ms >= 0
    assert [p.part_number for p in r.products] == [PN]
    assert r.answer == "ok" and not r.guard_triggered


def test_answer_with_correct_numbers_passes_guard(factory):
    text = f"{PN}: torque {ROW.onoff_torque_nm:g} Nm, motor {ROW.motor_power_w:g} W."
    llm = fake(call("get_actuator", {"part_number": PN}), AIMessage(content=text))
    r = run_agent("torque and power of 764A00-11300000", llm=llm, conn_factory=factory)
    assert r.answer == text and not r.guard_triggered


def test_invented_number_triggers_guard(factory):
    llm = fake(call("get_actuator", {"part_number": PN}), AIMessage(content="Torque is 98765 Nm."))
    r = run_agent("torque of 764A00-11300000", llm=llm, conn_factory=factory)
    assert r.guard_triggered
    assert "98765" not in r.answer
    assert r.trace[-1].tool != "get_actuator"  # guard entry appended
    assert r.trace[0].tool == "get_actuator"


def test_search_actuators_flat_args(factory):
    args = {"min_torque": 100, "torque_unit": "nm", "voltage_v": 110}
    llm = fake(call("search_actuators", args), AIMessage(content="Here you go."))
    r = run_agent("need 100 Nm at 110V", llm=llm, conn_factory=factory)
    t = r.trace[0]
    assert t.tool == "search_actuators"
    assert t.params["min_torque"] == 100 and t.params["voltage_v"] == 110
    assert t.result["status"] == "ok" and t.result["matches"]
    assert r.products


def test_two_tool_calls_in_one_turn_keep_order(factory):
    both = AIMessage(
        content="",
        tool_calls=[
            {"name": "describe_catalog", "args": {}, "id": "a"},
            {"name": "get_actuator", "args": {"part_number": PN}, "id": "b"},
        ],
    )
    r = run_agent("hi", llm=fake(both, AIMessage(content="done")), conn_factory=factory)
    assert [t.tool for t in r.trace] == ["describe_catalog", "get_actuator"]
    assert all(isinstance(t.result, dict) for t in r.trace)


def test_tool_error_is_recorded_and_run_completes():
    @contextmanager
    def broken():
        raise RuntimeError("db down")
        yield  # pragma: no cover

    llm = fake(call("get_actuator", {"part_number": PN}), AIMessage(content="Sorry, no data."))
    r = run_agent("details of 764A00", llm=llm, conn_factory=broken)
    assert r.trace[0].result == {"error": "db down"}
    assert r.answer  # run completed
    # the model received an error ToolMessage
    tool_msgs = [m for m in llm.seen[-1] if m.type == "tool"]
    assert tool_msgs and tool_msgs[0].status == "error"


def test_llm_exception_becomes_agent_error(factory):
    class Boom(FakeLLM):
        def _generate(self, *a: Any, **k: Any) -> Any:
            raise ConnectionError("network")

    with pytest.raises(AgentError) as ei:
        run_agent("hi", llm=Boom(messages=iter([]), seen=[]), conn_factory=factory)
    assert isinstance(ei.value.__cause__, ConnectionError)


def test_endless_tool_calls_hit_loop_answer(factory, monkeypatch):
    monkeypatch.setattr(agent_mod, "RECURSION_LIMIT", 6)
    llm = fake(*[call("describe_catalog", {}, f"c{i}") for i in range(30)])
    r = run_agent("loop forever", llm=llm, conn_factory=factory)
    assert r.answer  # no exception
    assert len(r.trace) >= 1
    # guard may swap the text for the template; otherwise it is the loop answer
    assert r.guard_triggered or r.answer == LOOP_ANSWER


def test_history_context_line_reaches_model(factory):
    hist = [
        HistoryTurn(role="user", content="show 764A00-11300000"),
        HistoryTurn(role="assistant", content="Here.", part_numbers=[PN]),
    ]
    llm = fake(AIMessage(content="ok"))
    run_agent("and its power?", hist, llm=llm, conn_factory=factory)
    msgs = llm.seen[0]
    assert sum(isinstance(m, SystemMessage) for m in msgs) == 1
    assert isinstance(msgs[0], SystemMessage)
    last = msgs[-1]
    assert isinstance(last, HumanMessage)
    assert PN in str(last.content) and "and its power?" in str(last.content)


def test_recorder_not_shared_between_runs(factory):
    for _ in range(2):
        llm = fake(call("describe_catalog", {}), AIMessage(content="ok"))
        r = run_agent("what do you have?", llm=llm, conn_factory=factory)
        assert len(r.trace) == 1


def test_non_provider_exception_propagates(factory):
    class Bug(FakeLLM):
        def _generate(self, *a: Any, **k: Any) -> Any:
            raise ValueError("bug in our code")

    with pytest.raises(ValueError):
        run_agent("hi", llm=Bug(messages=iter([]), seen=[]), conn_factory=factory)


def test_parallel_trace_entries_stay_paired(factory):
    both = AIMessage(
        content="",
        tool_calls=[
            {"name": "get_actuator", "args": {"part_number": "761A00-11300000/A"}, "id": "x1"},
            {"name": "get_actuator", "args": {"part_number": "762A00-11300000/A"}, "id": "x2"},
        ],
    )
    r = run_agent("both", llm=fake(both, AIMessage(content="ok")), conn_factory=factory)
    for t in r.trace:  # each entry's result is for its own params
        assert t.result["actuator"]["part_number"] == t.params["part_number"]
    assert [t.params["part_number"] for t in r.trace] == ["761A00-11300000/A", "762A00-11300000/A"]
