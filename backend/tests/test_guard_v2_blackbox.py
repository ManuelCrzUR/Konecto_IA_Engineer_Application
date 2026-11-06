"""Black-box tests for the number guard v2 (app.agent.response.build_result).

Written from the public contract only: no test reads the implementation.
Inputs: an answer, a trace of ToolTrace objects, the user query, optional
user_history and optional referent. Output: AgentResult with .answer,
.guard_triggered and .trace.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from app.agent.response import build_result
from app.domain.models import ToolTrace

ROWS = json.loads((Path(__file__).parents[1] / "data/processed/actuators.json").read_text())["rows"]
BY_PN = {r["part_number"]: r for r in ROWS}

PN_761 = "761A00-11300000/A"  # 80 Nm, 700 in-lbs, 17 s @60Hz, FLA 1.2 A, 15 W
PN_764 = "764A00-11300000/A"  # 750 Nm, 6650 in-lbs, 30 s @60Hz, FLA 6.5 A, 180 W
PN_766 = "766A00-11320000/A"  # 3500 Nm, 31000 in-lbs, 33 s @60Hz, FLA 11.2 A, 700 W

TOL = "Allowable motor voltage tolerance: +/- 10%"


def _actuator(pn: str) -> dict[str, Any]:
    return {k: v for k, v in BY_PN[pn].items() if k != "row_index"}


def get_trace(pn: str) -> ToolTrace:
    """A get_actuator call that found `pn` (shape as the real tool returns it)."""
    return ToolTrace(
        tool="get_actuator",
        params={"part_number": pn},
        result={
            "status": "found",
            "query": pn,
            "normalized": pn,
            "actuator": _actuator(pn),
            "notes": [TOL],
        },
    )


def search_trace(pns: list[str]) -> ToolTrace:
    """A search_actuators call whose matches are the given part numbers."""
    return ToolTrace(
        tool="search_actuators",
        params={"min_torque": 10, "torque_unit": "Nm"},
        result={
            "status": "ok",
            "matches": [_actuator(pn) for pn in pns],
            "total": len(pns),
            "filters": {"min_torque": 10, "torque_unit": "Nm"},
        },
    )


ONE_761 = [get_trace(PN_761)]
BOTH = [get_trace(PN_761), get_trace(PN_764)]


# --- Figures from the trace pass -------------------------------------------------


@pytest.mark.parametrize(
    ("answer", "trace"),
    [
        (f"{PN_764} gives 750 Nm and 6,650 in-lbs, 30 s at 60 Hz.", [get_trace(PN_764)]),
        (f"El {PN_764} tiene 750 Nm (6.650 in-lbs) y 180 W.", [get_trace(PN_764)]),
        (f"Corriente FLA 6,5 A en {PN_764}.", [get_trace(PN_764)]),
        (f"Hay siete opciones: {PN_761}.", [get_trace(PN_761)]),
    ],
    ids=["en-thousands", "es-dot-thousands", "es-decimal-comma", "es-word-in-query"],
)
def test_figures_present_in_trace_pass(answer: str, trace: list[ToolTrace]) -> None:
    query = "hay siete opciones?" if "siete" in answer else "tell me about it"
    res = build_result(answer, trace, query)
    assert res.guard_triggered is False
    assert res.answer == answer


def test_passing_answer_keeps_trace_length() -> None:
    res = build_result(f"{PN_761} has 80 Nm.", ONE_761, "what is 761A00?")
    assert res.guard_triggered is False
    assert len(res.trace) == len(ONE_761)


# --- Invented numbers fail ------------------------------------------------------


@pytest.mark.parametrize(
    "answer",
    [
        f"{PN_761} delivers 95 Nm.",
        f"El {PN_761} entrega 95 Nm.",
        f"{PN_761} draws FLA 9 A at startup.",  # no more always-allowed small integers
        f"El {PN_761} tiene doce posiciones.",  # number word not in any source
        f"{PN_761} needs 1,330 in-lbs.",  # thousands token not in the trace
    ],
    ids=[
        "en-invented",
        "es-invented",
        "small-int-not-allowed",
        "word-invented",
        "thousands-invented",
    ],
)
def test_invented_number_triggers_guard(answer: str) -> None:
    res = build_result(answer, ONE_761, "what is 761A00?")
    assert res.guard_triggered is True
    assert res.answer != answer


def test_guard_replaces_answer_with_template_without_invented_number() -> None:
    res = build_result(f"{PN_761} delivers 95 Nm.", ONE_761, "what is 761A00?")
    assert res.guard_triggered is True
    assert "95" not in res.answer


# --- Articles are not numbers ---------------------------------------------------


@pytest.mark.parametrize(
    "answer",
    [
        f"Un actuador, una opcion y uno solo: {PN_761}.",
        f"One actuator fits: {PN_761}, one size.",
    ],
    ids=["es-articles", "en-one"],
)
def test_articles_are_not_numbers(answer: str) -> None:
    res = build_result(answer, ONE_761, "which one?")
    assert res.guard_triggered is False


# --- Exceptions without a source ------------------------------------------------


@pytest.mark.parametrize(
    "answer",
    [
        f"1. {PN_761} is the smallest.\n2) Nothing else fits.",
        f"1. El {PN_761} es el mas pequeno.",
    ],
    ids=["en-list-ordinals", "es-list-ordinal"],
)
def test_line_start_ordinals_are_exempt(answer: str) -> None:
    res = build_result(answer, ONE_761, "options?")
    assert res.guard_triggered is False


@pytest.mark.parametrize(
    "answer",
    [
        f"{PN_761} rotates 90° in 17 s.",
        f"El {PN_761} gira 90 grados.",
        f"{PN_761} turns 90 degrees.",
    ],
    ids=["degree-sign", "es-grados", "en-degrees"],
)
def test_ninety_degrees_is_exempt(answer: str) -> None:
    res = build_result(answer, ONE_761, "how far does it turn?")
    assert res.guard_triggered is False


def test_bare_ninety_without_unit_is_not_exempt() -> None:
    res = build_result(f"{PN_761} draws 90 W.", ONE_761, "power?")
    assert res.guard_triggered is True


# --- Product binding ------------------------------------------------------------


def test_value_of_another_product_does_not_count() -> None:
    # 750 Nm is in the trace, but it belongs to 764A00, not to 761A00.
    res = build_result(f"{PN_761} gives 750 Nm.", BOTH, "compare")
    assert res.guard_triggered is True


def test_value_of_the_same_product_counts() -> None:
    res = build_result(f"{PN_761}: 80 Nm, 17 s, 15 W.", BOTH, "compare")
    assert res.guard_triggered is False


def test_markdown_row_binds_to_its_own_product() -> None:
    good = f"| Part number | Torque |\n|---|---|\n| {PN_761} | 80 Nm |\n| {PN_764} | 750 Nm |"
    bad = f"| Part number | Torque |\n|---|---|\n| {PN_761} | 750 Nm |"
    assert build_result(good, BOTH, "table").guard_triggered is False
    assert build_result(bad, BOTH, "table").guard_triggered is True


# --- Referent -------------------------------------------------------------------


def test_referent_numbers_must_belong_to_referent() -> None:
    res = build_result(
        "El torque es 750 Nm.",
        BOTH,
        "y el torque?",
        referent=PN_761,
    )
    assert res.guard_triggered is True


def test_referent_numbers_from_referent_pass() -> None:
    res = build_result("El torque es 80 Nm.", BOTH, "y el torque?", referent=PN_761)
    assert res.guard_triggered is False


def test_referent_ignored_when_answer_names_a_part_number() -> None:
    # The answer names 764A00 itself, so its own numbers are fine even though the referent is 761A00.
    res = build_result(f"{PN_764} tiene 750 Nm.", BOTH, "y ese?", referent=PN_761)
    assert res.guard_triggered is False


# --- Part numbers and family name are not figures -------------------------------


@pytest.mark.parametrize(
    "answer",
    [
        f"Series 76 offers {PN_764} at 750 Nm.",
        f"Los actuadores Serie 76, como {PN_764}, dan 750 Nm.",
    ],
    ids=["en-series-76", "es-serie-76"],
)
def test_part_numbers_and_family_name_are_not_figures(answer: str) -> None:
    res = build_result(answer, [get_trace(PN_764)], "catalog?")
    assert res.guard_triggered is False


# --- History and query sources ----------------------------------------------------


def test_number_from_user_history_is_a_source() -> None:
    res = build_result(
        "Tu requisito de 500 Nm se cumple con el actuador.",
        ONE_761,
        "y con ese?",
        user_history="necesito 500 Nm",
    )
    assert res.guard_triggered is False


def test_number_from_user_history_missing_still_triggers() -> None:
    res = build_result("Tu requisito de 500 Nm se cumple.", ONE_761, "y con ese?")
    assert res.guard_triggered is True
