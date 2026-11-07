"""Black-box tests for D-51: the number guard binds a figure to its field.

Written from the public contract only (docs/DECISIONS.md D-51 and the docstring
of app.agent.response). No test reads the implementation. Inputs: an answer, a
trace of ToolTrace objects, the user query, optional user_history and optional
referent. Output: AgentResult with .answer, .guard_triggered and .trace.

Values are copied as printed in backend/data/processed/actuators.json:
  764A00-11300000/A: torque 750 Nm / 6650 in-lbs, duty 25 %, cycles 12/h,
                     starts 840/h, speed 30 s (60 Hz) / 36 s (50 Hz),
                     FLA 6.5 A, LRA 7.3 A, power 180 W.
  761A00-11300000/A: torque 80 Nm / 700 in-lbs, duty 40 %, cycles 36/h,
                     starts 960/h, speed 17 s (60 Hz) / 20 s (50 Hz),
                     FLA 1.2 A, LRA 1.4 A, power 15 W.
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

PN_761 = "761A00-11300000/A"
PN_764 = "764A00-11300000/A"

TOL = "Allowable motor voltage tolerance: +/- 10%"


def _actuator(pn: str, **overrides: Any) -> dict[str, Any]:
    data = {k: v for k, v in BY_PN[pn].items() if k != "row_index"}
    data.update(overrides)
    return data


def get_trace(pn: str, **overrides: Any) -> ToolTrace:
    """A get_actuator call that found `pn` (shape as the real tool returns it)."""
    return ToolTrace(
        tool="get_actuator",
        params={"part_number": pn},
        result={
            "status": "found",
            "query": pn,
            "normalized": pn,
            "actuator": _actuator(pn, **overrides),
            "notes": [TOL],
        },
    )


ONE_761 = [get_trace(PN_761)]
ONE_764 = [get_trace(PN_764)]
BOTH = [get_trace(PN_761), get_trace(PN_764)]


# --- Wrong column of the right product ----------------------------------------------


@pytest.mark.parametrize(
    "answer",
    [
        f"{PN_764}: FLA 750 A.",  # 750 is torque in Nm
        f"{PN_764}: torque 6650 Nm.",  # 6650 is torque in in-lbs
        f"{PN_764}: duty cycle 12%.",  # 12 is cycles/h
        f"{PN_764}: power 30 W.",  # 30 is the speed in seconds
    ],
    ids=["amps-from-torque", "nm-from-inlbs", "percent-from-cycles", "watts-from-speed"],
)
def test_wrong_column_of_the_right_product_is_flagged(answer: str) -> None:
    # The figure exists somewhere in the trace, so only the field binding can catch it.
    res = build_result(answer, ONE_764, "datos del 764?")
    assert res.guard_triggered is True


def test_wrong_inlbs_unit_on_same_product_is_flagged() -> None:
    # 80 is the Nm torque of 761A00, the in-lbs torque is 700; 80 is not an in-lbs value.
    res = build_result(f"{PN_761}: 80 in-lbs.", ONE_761, "torque?")
    assert res.guard_triggered is True


# --- Right value with each unit family passes ---------------------------------------


@pytest.mark.parametrize(
    "figure",
    [
        "750 Nm",  # Nm -> *_nm
        "6,650 in-lbs",  # in-lbs -> *_in_lbs
        "6,5 A",  # A -> fla_* / lra_*
        "180 W",  # W -> motor_power_w
        "25%",  # % -> duty cycle
        "30 s",  # s -> speed
        "12 cycles/h",  # cycles/h -> cycles_per_hour
        "840 starts/h",  # starts/h -> starts_per_hour
    ],
    ids=["nm", "in-lbs", "amps", "watts", "percent", "seconds", "cycles-per-h", "starts-per-h"],
)
def test_right_value_with_each_unit_family_passes(figure: str) -> None:
    res = build_result(f"{PN_764}: {figure}.", ONE_764, "datos del 764?")
    assert res.guard_triggered is False


# --- English and Spanish unit words -------------------------------------------------


@pytest.mark.parametrize(
    "answer",
    [
        f"{PN_764}: FLA 6.5 amps.",
        f"{PN_764}: FLA 6,5 amperios.",
        f"{PN_764}: 30 seconds to 90 degrees.",
        f"{PN_764}: 30 segundos.",
        f"{PN_764}: 180 watts.",
        f"{PN_764}: 180 vatios.",
    ],
    ids=["amps-en", "amperios-es", "seconds-en", "segundos-es", "watts-en", "vatios-es"],
)
def test_english_and_spanish_unit_words_pass_for_right_values(answer: str) -> None:
    res = build_result(answer, ONE_764, "datos?")
    assert res.guard_triggered is False


@pytest.mark.parametrize(
    "answer",
    [
        f"{PN_764}: FLA 30 amperios.",  # 30 is a speed, not an amp value
        f"{PN_764}: 6.5 seconds.",  # 6.5 is an amp value, not a speed
        f"{PN_764}: 180 segundos.",  # 180 is watts, not a speed
    ],
    ids=["amperios-from-speed", "seconds-from-fla", "segundos-from-power"],
)
def test_unit_words_flag_a_value_from_the_wrong_field(answer: str) -> None:
    res = build_result(answer, ONE_764, "datos?")
    assert res.guard_triggered is True


# --- Another product's value, bound to this product ---------------------------------


def test_value_of_another_product_with_unit_is_flagged() -> None:
    # 80 Nm belongs to 761A00; the sentence binds it to 764A00.
    res = build_result(f"{PN_764}: 80 Nm.", BOTH, "compare")
    assert res.guard_triggered is True


# --- Figure with Hz or with no unit keeps the per-product rule ----------------------


def test_figure_without_unit_that_is_a_product_value_passes() -> None:
    res = build_result(f"{PN_761}: 17.", BOTH, "velocidad?")
    assert res.guard_triggered is False


def test_figure_without_unit_from_another_product_is_flagged() -> None:
    # 750 is a value of 764A00 only; with no unit, the per-product rule still applies.
    res = build_result(f"{PN_761}: 750.", BOTH, "compare")
    assert res.guard_triggered is True


def test_hz_figure_found_in_query_passes() -> None:
    res = build_result(f"{PN_761} works at 60 Hz.", ONE_761, "a 60 Hz?")
    assert res.guard_triggered is False


def test_hz_figure_not_in_product_or_query_is_flagged() -> None:
    res = build_result(f"{PN_761} works at 45 Hz.", ONE_761, "velocidad?")
    assert res.guard_triggered is True


# --- User-typed figures and table-note tolerances -----------------------------------


def test_figure_the_user_typed_with_unit_passes() -> None:
    res = build_result(
        f"{PN_764}: 500 Nm.",
        ONE_764,
        "y ese?",
        user_history="necesito 500 Nm",
    )
    assert res.guard_triggered is False


def test_table_note_tolerance_passes() -> None:
    res = build_result(f"{PN_764}: tolerance ±10%.", ONE_764, "tolerancia?")
    assert res.guard_triggered is False


# --- Binding through referent ----------------------------------------------------------


def test_referent_with_matching_field_value_passes() -> None:
    res = build_result("El FLA es 6,5 A.", BOTH, "y el FLA?", referent=PN_764)
    assert res.guard_triggered is False


def test_referent_figure_from_another_product_is_flagged() -> None:
    # 1.2 A is the FLA of 761A00, not of the referent 764A00.
    res = build_result("El FLA es 1,2 A.", BOTH, "y el FLA?", referent=PN_764)
    assert res.guard_triggered is True


def test_referent_wrong_column_is_flagged() -> None:
    # 80 Nm is in the trace, but it is not a torque value of the referent 764A00.
    res = build_result("El torque es 80 Nm.", BOTH, "y el torque?", referent=PN_764)
    assert res.guard_triggered is True


# --- Unbound figures keep the global rule ----------------------------------------------


def test_unbound_figure_present_anywhere_in_trace_passes() -> None:
    res = build_result("El FLA es 750 A.", BOTH, "y el FLA?")
    assert res.guard_triggered is False


def test_unbound_invented_figure_is_flagged() -> None:
    res = build_result("El FLA es 9 A.", BOTH, "y el FLA?")
    assert res.guard_triggered is True


# --- Spanish decimal comma -------------------------------------------------------------


def test_spanish_decimal_comma_seconds_passes_when_field_is_six_point_five() -> None:
    # Synthetic trace: the speed field is set to 6.5 so that "6,5 s" binds to it.
    trace = [get_trace(PN_764, speed_sec_60hz=6.5)]
    res = build_result(f"{PN_764} gira en 6,5 s.", trace, "velocidad?")
    assert res.guard_triggered is False


def test_english_decimal_point_seconds_passes_when_field_is_six_point_five() -> None:
    trace = [get_trace(PN_764, speed_sec_60hz=6.5)]
    res = build_result(f"{PN_764} turns in 6.5 seconds.", trace, "speed?")
    assert res.guard_triggered is False


# --- build_result replaces the answer with the template ---------------------------------


def test_build_result_replaces_wrong_column_answer_with_template() -> None:
    original = f"{PN_764}: FLA 750 A."
    res = build_result(original, ONE_764, "FLA?")
    assert res.guard_triggered is True
    assert res.answer != original
    assert any(t.tool == "number_guard" for t in res.trace)
