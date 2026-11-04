"""Tests for app/agent/response.py: product building and the number guard (no LLM)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from app.agent import response as R
from app.domain.models import Actuator, ToolTrace

ROWS = json.loads((Path(__file__).parents[1] / "data/processed/actuators.json").read_text())["rows"]
BY_PN = {r["part_number"]: r for r in ROWS}
A761 = Actuator.model_validate(BY_PN["761A00-11300000/A"]).model_dump(mode="json")
A764 = Actuator.model_validate(BY_PN["764A00-11300000/A"]).model_dump(mode="json")
A766 = Actuator.model_validate(BY_PN["766A00-11320000/A"]).model_dump(mode="json")
NODATA = Actuator.model_validate(BY_PN["761A00-11330C00/A"]).model_dump(mode="json")
TOL = "Allowable motor voltage tolerance: +/- 10%"


def tr(tool: str, result: Any, **params: Any) -> ToolTrace:
    return ToolTrace(tool=tool, params=params, result=result)


def found(a: dict[str, Any], status: str = "found") -> ToolTrace:
    res = {"status": status, "query": "x", "normalized": "x", "actuator": a, "notes": [TOL]}
    return tr("get_actuator", res, part_number="x")


def search(matches: list[dict[str, Any]], **params: Any) -> ToolTrace:
    res = {"status": "ok", "matches": matches, "total": len(matches), "filters": params}
    return tr("search_actuators", res, **params)


NO_MATCH = tr(
    "search_actuators",
    {
        "status": "no_match",
        "matches": [],
        "no_match": {
            "message": "Nothing reaches 9000 Nm.",
            "closest": {"min_torque": 3500.0},
            "blocking": ["min_torque"],
            "out_of_catalog": False,
        },
    },
)
NOT_FOUND = tr("get_actuator", {"status": "not_found", "suggestions": ["761A00-11300000/A"]})
AMBIG = tr(
    "get_actuator",
    {
        "status": "ambiguous",
        "candidates": [{"part_number": "761A00-11300000/A"}, {"part_number": "761A00-11320000/A"}],
    },
)
DESCRIBE = tr("describe_catalog", {"combinations": [], "torque_nm_range": [80.0, 3500.0]})


def test_products_found_and_no_data():
    ps = R.products_from_trace([found(A761), found(NODATA, "found_no_data")], "")
    assert [p.part_number for p in ps] == ["761A00-11300000/A", "761A00-11330C00/A"]
    assert ps[0].fields["onoff_torque_nm"] == 80.0
    assert ps[0].notes == [TOL]
    assert not ps[1].has_data


def test_products_search_csa_note_and_dedupe():
    ps = R.products_from_trace([search([A761, A766]), found(A761)], "")
    assert [p.part_number for p in ps] == ["761A00-11300000/A", "766A00-11320000/A"]
    assert ps[0].notes == [TOL]  # the later get_actuator entry carries the table notes
    assert ps[1].notes == ["Sizes 6 and 7 are not CSA Certified"] and not ps[1].csa_certified


@pytest.mark.parametrize("t", [NO_MATCH, NOT_FOUND, AMBIG, DESCRIBE])
def test_no_products_for_other_statuses(t):
    assert R.products_from_trace([t], "anything") == []


def test_mention_filter():
    trace = [search([A761, A764])]
    full = R.products_from_trace(trace, "Use 764A00-11300000/A")
    base = R.products_from_trace(trace, "the 764a00 is best")
    assert [p.part_number for p in full] == [p.part_number for p in base] == ["764A00-11300000/A"]
    assert len(R.products_from_trace(trace, "no part named")) == 2


def test_extract_numbers():
    assert R.extract_numbers("764A00-11300000/A: 1,330 in-lbs, 2.3A, 80Nm, 17-20 s, 40%") == [
        "1,330",
        "2.3",
        "80",
        "17",
        "20",
        "40",
    ]
    assert R.extract_numbers("pn 766A00-11320000/A* and 761A00") == []


@pytest.mark.parametrize(
    ("tok", "vals"),
    [
        ("1,330", {1330.0, 1.33}),
        ("2,3", {2.3}),
        ("1.330", {1.33, 1330.0}),
        ("17", {17.0}),
        ("1,234,567", {1234567.0}),
        ("1,234.5", {1234.5}),
    ],
)
def test_token_values(tok, vals):
    assert R.token_values(tok) == vals


def test_allowed_numbers_sources():
    trace = [found(A761), tr("x", {"a": True, "b": None, "c": ["110V", [3500]]}, n=42)]
    allowed = R.allowed_numbers(trace, "I need 123 Nm")
    assert {80.0, 700.0, 10.0, 110.0, 3500.0, 42.0, 123.0, 7.0, 90.0} <= allowed
    assert 1.0 in allowed  # bool ignored, but 1 is always allowed anyway
    assert 11300000.0 not in allowed


def test_guard_passes_correct_english():
    trace = [found(A764)]
    ans = "764A00-11300000/A gives 750 Nm (6,650 in-lbs), 30 s at 60 Hz, FLA 6.5 A, 180W."
    assert R.unverified_numbers(ans, trace, "x") == []
    res = R.build_result(ans, trace, "what is 764A00?")
    assert res.answer == ans and not res.guard_triggered and len(res.trace) == 1
    assert [p.part_number for p in res.products] == ["764A00-11300000/A"]


def test_guard_passes_spanish_formats():
    trace = [found(A764), found(A766)]
    ans = "Torque de 6.650 in-lbs y corriente de 6,5 A; el otro: 30.975 in-lbs, 3.500 Nm."
    assert R.unverified_numbers(ans, trace, "x") == []


def test_guard_allows_query_numbers_and_small_ints():
    trace = [found(A761)]
    assert R.unverified_numbers("Pediste 500 Nm; opcion 2 de 3.", trace, "necesito 500 Nm") == []
    assert R.unverified_numbers("Pediste 500 Nm.", trace, "algo") == ["500"]


def test_guard_triggers_on_invented_number():
    trace = [found(A761)]
    ans = "761A00-11300000/A delivers 95 Nm."
    assert R.unverified_numbers(ans, trace, "q") == ["95"]
    res = R.build_result(ans, trace, "What is 761A00?")
    assert res.guard_triggered and "95" not in res.answer
    assert "761A00-11300000/A" in res.answer and "80 Nm" in res.answer
    last = res.trace[-1]
    assert last.tool == R.GUARD_TOOL and last.result == "template answer used"
    assert last.params == {"unverified": ["95"], "original_answer": ans}
    assert R.unverified_numbers(res.answer, trace, "q") == []
    assert len(res.products) == 1


def test_detect_lang():
    assert R.detect_lang("¿Qué torque tiene el 761A00?") == "es"
    assert R.detect_lang("necesito un actuador") == "es"
    assert R.detect_lang("which actuator has 80 Nm") == "en"


def test_template_products_and_language():
    en = R.template_answer([found(A761)], "show 761A00")
    assert "761A00-11300000/A" in en and "110V" in en and "weatherproof" in en
    assert "on/off torque 80 Nm" in en and "speed 60 Hz 17 s" in en
    assert "FLA 60 Hz 1.2 A" in en and "motor power 15 W" in en
    assert R.template_answer([found(A761)], "dame el 761A00").startswith("Datos de las tablas")


def test_template_variants():
    assert "no data" in R.template_answer(
        [found(NODATA, "found_no_data")], "q"
    ) or "N/A" in R.template_answer([found(NODATA, "found_no_data")], "q")
    assert "CSA" in R.template_answer([found(A766)], "q")
    assert R.template_answer([NO_MATCH], "q") == "Nothing reaches 9000 Nm."
    assert "761A00-11300000/A" in R.template_answer([NOT_FOUND], "q")
    assert "761A00-11320000/A" in R.template_answer([AMBIG], "q")
    assert "rephrase" in R.template_answer([DESCRIBE], "q")
    assert "reformular" in R.template_answer([], "¿qué hay?")


@pytest.mark.parametrize("text", ["the Series 76 catalog", "series-76 actuators", "SERIES 76"])
def test_family_name_is_not_a_number(text: str) -> None:
    # Found in the real eval: "Series 76" in a correct answer tripped the guard.
    assert R.extract_numbers(text) == []
    assert R.unverified_numbers(f"Not in {text}.", [], "q") == []


# ---- Gate 3 code-review fixes ----------------------------------------------
def test_full_pn_mention_beats_base_siblings():
    sib = [BY_PN["761A00-11300000/A"], BY_PN["761A00-11320000/A"], BY_PN["761A00-11330C00/A"]]
    prods = R.products_from_trace([search(sib)], "Use 761A00-11300000/A.")
    assert [p.part_number for p in prods] == ["761A00-11300000/A"]
    # without '/A' it still counts as the full part number
    prods = R.products_from_trace([search(sib)], "Use 761A00-11320000.")
    assert [p.part_number for p in prods] == ["761A00-11320000/A"]
    # only the base mentioned -> all siblings with that base
    assert len(R.products_from_trace([search(sib)], "The 761A00 family.")) == 3


def test_duplicate_keeps_entry_with_table_notes():
    a = BY_PN["764X30-11320000/A"]
    trace = [search([a]), found(a)]  # search first (no notes), lookup second (notes)
    (p,) = R.products_from_trace(trace, "")
    assert p.notes == [TOL]


def test_invented_part_number_triggers_guard():
    a = BY_PN["764A00-11300000/A"]
    res = R.build_result("Use 769A00-11300000/A instead.", [found(a)], "which one?")
    assert res.guard_triggered
    assert "769A00-11300000" in res.trace[-1].params["unverified"]


def test_known_part_numbers_and_bases_pass():
    a = BY_PN["764A00-11300000/A"]
    assert R.unverified_part_numbers("764A00-11300000/A and the 764A00 base", [found(a)], "q") == []
    assert R.unverified_part_numbers("the 762b00-11330c00*", [], "is 762B00-11330C00 ok?") == []


def test_user_history_numbers_count_as_verified():
    earlier = "Busco algo para una válvula en zona explosiva, 24V"
    answer = f'Lo último que me dijiste fue: "{earlier}"'
    q = "¿Qué fue lo último que te dije?"
    assert R.build_result(answer, [], q).guard_triggered  # without history: rejected
    r = R.build_result(answer, [], q, earlier)
    assert not r.guard_triggered and r.answer == answer


def test_user_history_part_number_passes():
    assert R.unverified_part_numbers("Pediste 764A00", [], "y eso?") == ["764A00"]
    assert R.unverified_part_numbers("Pediste 764A00", [], "y eso?", "dame 764A00-11300000") == []
