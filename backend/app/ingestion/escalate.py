"""Vision re-read of a whole table (used only for flagged tables).

Contract:
- make_vision_escalator(llm=None) -> Escalator (see pipeline.Escalator).
  The escalator sends the table crop (base64 PNG image block) and a prompt
  listing the table's columns (TABLE_FIELDS[table_id]) to a multimodal chat
  model, asking for JSON: {"rows": [{"part_number": "<as printed>",
  "cells": {"<field>": "<raw text as printed>"}}]}. The model only
  TRANSCRIBES text; every value then goes through normalize.normalize_row
  (strict rules) so the LLM never decides a number's format. Bad JSON or a
  normalize error -> EscalationError.
- llm=None -> app.llm.get_llm("extract") (EXTRACT_LLM_MODEL). Tests inject a
  fake chat model; the real call costs money and needs explicit approval.
"""

from __future__ import annotations

import base64
import json
import re
from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage

from app.domain.models import Actuator
from app.ingestion.normalize import NormalizationError, normalize_row
from app.ingestion.pipeline import Escalator
from app.llm import get_llm

# Columns printed in each table, in reading order (Motor Power last).
# Hard-coded on purpose; tests check it against the verified golden rows.
_WP_DUAL: tuple[str, ...] = (
    "onoff_torque_in_lbs",
    "onoff_torque_nm",
    "onoff_duty_cycle_pct",
    "cycles_per_hour",
    "mod_torque_in_lbs",
    "mod_torque_nm",
    "mod_duty_cycle_pct",
    "starts_per_hour",
    "speed_sec_60hz",
    "speed_sec_50hz",
    "fla_60hz_a",
    "fla_50hz_a",
    "lra_60hz_a",
    "lra_50hz_a",
    "motor_power_w",
)
TABLE_FIELDS: dict[str, tuple[str, ...]] = {
    "T1_wp_110v_1ph": _WP_DUAL,
    "T2_wp_220v_1ph": _WP_DUAL,
    "T3_wp_220v_3ph": (
        "cycles_per_hour",
        "starts_per_hour",
        "output_torque_in_lbs",
        "output_torque_nm",
        "duty_cycle_pct",
        "speed_sec_60hz",
        "speed_sec_50hz",
        "fla_60hz_a",
        "fla_50hz_a",
        "lra_60hz_a",
        "lra_50hz_a",
        "motor_power_w",
    ),
    "T4_xp_24v_onoff": (
        "onoff_torque_in_lbs",
        "onoff_torque_nm",
        "onoff_duty_cycle_pct",
        "cycles_per_hour",
        "speed_sec",
        "fla_a",
        "lra_a",
        "motor_power_w",
    ),
    "T5_xp_24vdc_mod": (
        "mod_torque_in_lbs",
        "mod_torque_nm",
        "mod_duty_cycle_pct",
        "starts_per_hour",
        "speed_sec",
        "fla_a",
        "lra_a",
        "motor_power_w",
    ),
    "T6_xp_110v_1ph": _WP_DUAL,
    "T7_xp_220v_1ph": _WP_DUAL,
}

FIELD_LABELS: dict[str, str] = {
    "onoff_torque_in_lbs": "On/Off torque, in-lbs",
    "onoff_torque_nm": "On/Off torque, Nm",
    "onoff_duty_cycle_pct": "On/Off duty cycle, S4 %",
    "cycles_per_hour": "On/Off cycles per hour",
    "mod_torque_in_lbs": "Modulating torque, in-lbs",
    "mod_torque_nm": "Modulating torque, Nm",
    "mod_duty_cycle_pct": "Modulating duty cycle, S4 %",
    "starts_per_hour": "Modulating starts per hour",
    "output_torque_in_lbs": "Output torque, in-lbs",
    "output_torque_nm": "Output torque, Nm",
    "duty_cycle_pct": "Duty cycle, S4 %",
    "speed_sec_60hz": "Speed for 90 degrees at 60 Hz, seconds",
    "speed_sec_50hz": "Speed for 90 degrees at 50 Hz, seconds",
    "speed_sec": "Speed for 90 degrees, seconds",
    "fla_60hz_a": "FLA at 60 Hz, amps",
    "fla_50hz_a": "FLA at 50 Hz, amps",
    "fla_a": "FLA, amps",
    "lra_60hz_a": "LRA at 60 Hz, amps",
    "lra_50hz_a": "LRA at 50 Hz, amps",
    "lra_a": "LRA, amps",
    "motor_power_w": "Motor power, W",
}

PROMPT = """You are transcribing a table from an image of an actuator catalog page.
Copy the text EXACTLY as printed. Do not convert units, do not calculate, do not
correct anything, and keep thousands commas as printed (for example "26,500").

Return ONLY a JSON object, with no commentary and no markdown, shaped like:
{{"rows": [{{"part_number": "<as printed, including a trailing '*' if present>",
"cells": {{"<field>": "<raw text as printed, or N/A>"}}}}]}}

Rules:
- One entry in "rows" per printed table row, from top to bottom.
- "part_number" is the Base Part Number cell exactly as printed.
- "cells" has one key per field listed below; the value is the raw printed text
  as a string. If the cell shows N/A, use "N/A".
- Motor Power is printed once for a group of rows (merged cell): repeat that
  value in every row of the group.

Fields, in reading order (key: column label):
{fields}
"""

_FENCE = re.compile(r"^\s*```(?:json)?\s*(.*?)\s*```\s*$", re.DOTALL | re.IGNORECASE)


class EscalationError(RuntimeError):
    """The vision model's answer could not be parsed or normalized."""


def build_prompt(table_id: str) -> str:
    fields = TABLE_FIELDS.get(table_id)
    if fields is None:
        raise EscalationError(f"{table_id}: unknown table_id")
    listing = "\n".join(f"- {f}: {FIELD_LABELS[f]}" for f in fields)
    return PROMPT.format(fields=listing)


def build_message(table_id: str, png: bytes) -> HumanMessage:
    b64 = base64.b64encode(png).decode("ascii")
    return HumanMessage(
        content=[
            {"type": "text", "text": build_prompt(table_id)},
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
        ]
    )


def _content_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    parts = []
    for block in content:
        if isinstance(block, str):
            parts.append(block)
        elif isinstance(block, dict) and block.get("type") == "text":
            parts.append(str(block.get("text", "")))
    return "".join(parts)


def parse_response(table_id: str, text: str) -> list[Actuator]:
    if table_id not in TABLE_FIELDS:
        raise EscalationError(f"{table_id}: unknown table_id")
    m = _FENCE.match(text)
    body = m.group(1) if m else text.strip()
    try:
        data = json.loads(body)
    except json.JSONDecodeError as exc:
        raise EscalationError(f"{table_id}: model answer is not valid JSON ({exc})") from exc
    if not isinstance(data, dict) or not isinstance(data.get("rows"), list):
        raise EscalationError(f"{table_id}: JSON must be an object with a 'rows' list")
    out: list[Actuator] = []
    for i, row in enumerate(data["rows"]):
        if (
            not isinstance(row, dict)
            or not isinstance(row.get("part_number"), str)
            or not isinstance(row.get("cells"), dict)
        ):
            raise EscalationError(
                f"{table_id}: row {i + 1} needs a string 'part_number' and a 'cells' object"
            )
        try:
            out.append(normalize_row(table_id, row["part_number"], row["cells"], row_index=i + 1))
        except NormalizationError as exc:
            raise EscalationError(f"{table_id}: row {i + 1}: {exc}") from exc
    return out


def make_vision_escalator(llm: BaseChatModel | None = None) -> Escalator:
    cache: list[BaseChatModel] = [llm] if llm is not None else []

    def escalate(table_id: str, crop_png: bytes) -> list[Actuator]:
        message = build_message(table_id, crop_png)  # validates table_id first
        if not cache:
            cache.append(get_llm("extract"))  # lazy: building needs no key
        reply = cache[0].invoke([message])
        return parse_response(table_id, _content_text(reply.content))

    return escalate
