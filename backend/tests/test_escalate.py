"""Vision escalator with a recording fake chat model (no network, no real LLM)."""

import base64
import json
from pathlib import Path
from typing import Any

import pytest
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from pydantic import Field

import app.llm as llm_mod
from app.domain.models import NUMERIC_FIELDS, TABLE_IDS, Actuator
from app.ingestion.escalate import TABLE_FIELDS, EscalationError, make_vision_escalator
from app.llm import LLMConfigError

GOLDEN = json.loads((Path(__file__).parent / "fixtures" / "golden_draft.json").read_text())["rows"]
PNG = b"\x89PNG\r\n\x1a\nfake-bytes"


class RecordingFake(BaseChatModel):
    reply: str
    seen: list[list[BaseMessage]] = Field(default_factory=list)

    @property
    def _llm_type(self) -> str:
        return "recording-fake"

    def _generate(
        self, messages: list[BaseMessage], stop: Any = None, run_manager: Any = None, **kwargs: Any
    ) -> ChatResult:
        self.seen.append(messages)
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content=self.reply))])


def fake(reply: str) -> RecordingFake:
    return RecordingFake(reply=reply, seen=[])


def printed(v: float) -> str:
    return f"{v:,.0f}" if float(v).is_integer() else str(v)


def golden_reply(table_id: str) -> str:
    rows = []
    for r in [g for g in GOLDEN if g["table_id"] == table_id]:
        cells = {f: ("N/A" if r[f] is None else printed(r[f])) for f in TABLE_FIELDS[table_id]}
        pn = r["part_number"] + ("" if r["csa_certified"] else "*")
        rows.append({"part_number": pn, "cells": cells})
    return json.dumps({"rows": rows})


def test_table_fields_match_golden():
    assert set(TABLE_FIELDS) == set(TABLE_IDS)
    for tid, fields in TABLE_FIELDS.items():
        rows = [g for g in GOLDEN if g["table_id"] == tid]
        implied = tuple(f for f in NUMERIC_FIELDS if any(r[f] is not None for r in rows))
        assert fields == implied, tid


def test_happy_path_equals_golden():
    tid = "T4_xp_24v_onoff"
    out = make_vision_escalator(fake(golden_reply(tid)))(tid, PNG)
    expected = [Actuator.from_bench_row(g) for g in GOLDEN if g["table_id"] == tid]
    assert out == expected


@pytest.mark.parametrize("tid", TABLE_IDS)
def test_every_table_roundtrips(tid):
    out = make_vision_escalator(fake(golden_reply(tid)))(tid, PNG)
    expected = [Actuator.from_bench_row(g) for g in GOLDEN if g["table_id"] == tid]
    assert [a.model_dump() for a in out] == [a.model_dump() for a in expected]


def test_message_has_prompt_and_image():
    tid = "T5_xp_24vdc_mod"
    f = fake(golden_reply(tid))
    make_vision_escalator(f)(tid, PNG)
    (msgs,) = f.seen
    content = msgs[0].content
    text = next(b for b in content if b["type"] == "text")["text"]
    for field in TABLE_FIELDS[tid]:
        assert field in text
    img = next(b for b in content if b["type"] == "image_url")["image_url"]["url"]
    assert img == "data:image/png;base64," + base64.b64encode(PNG).decode()


def test_fenced_json_accepted():
    tid = "T4_xp_24v_onoff"
    out = make_vision_escalator(fake("```json\n" + golden_reply(tid) + "\n```"))(tid, PNG)
    assert len(out) == 5


def test_csa_asterisk():
    reply = json.dumps(
        {"rows": [{"part_number": "766A00-11320000/A*", "cells": {"onoff_torque_in_lbs": "1,000"}}]}
    )
    (a,) = make_vision_escalator(fake(reply))("T2_wp_220v_1ph", PNG)
    assert a.csa_certified is False
    assert a.part_number == "766A00-11320000/A"
    assert a.onoff_torque_in_lbs == 1000


@pytest.mark.parametrize(
    "reply",
    [
        "not json at all",
        json.dumps({"data": []}),
        json.dumps({"rows": [{"part_number": "764A00-11380000/A", "cells": {"fla_a": "2,65"}}]}),
        json.dumps({"rows": [{"part_number": "764A00-11300000/A", "cells": {}}]}),
        json.dumps({"rows": [{"part_number": "764A00-11380000/A"}]}),
    ],
)
def test_bad_answers_raise(reply):
    with pytest.raises(EscalationError, match="T4_xp_24v_onoff"):
        make_vision_escalator(fake(reply))("T4_xp_24v_onoff", PNG)


def test_unknown_table():
    with pytest.raises(EscalationError, match="T9"):
        make_vision_escalator(fake("{}"))("T9", PNG)


def test_lazy_llm_needs_key_only_when_called(monkeypatch):
    monkeypatch.setattr(llm_mod, "load_dotenv", lambda *a, **k: False)
    for v in ("LLM_API_KEY", "AGENT_MODEL", "EXTRACT_LLM_MODEL", "LLM_BASE_URL"):
        monkeypatch.delenv(v, raising=False)
    esc = make_vision_escalator()  # fine without env
    with pytest.raises(LLMConfigError, match="LLM_API_KEY"):
        esc("T4_xp_24v_onoff", PNG)
