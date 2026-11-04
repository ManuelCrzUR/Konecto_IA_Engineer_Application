"""Black-box contract tests for app/agent/response.py (number guard + products).

Only the module docstring contract is exercised; no DB, no LLM.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.agent import response as R
from app.domain.conversation import AgentResult
from app.domain.models import Actuator, ToolTrace
from app.domain.search import (
    ActuatorLookup,
    Candidate,
    CatalogSummary,
    NoMatchReport,
    SearchFilters,
    SearchResult,
)

DATA = Path(__file__).resolve().parents[1] / "data" / "processed" / "actuators.json"
ROWS = {r["part_number"]: Actuator(**r) for r in json.loads(DATA.read_text())["rows"]}
RAW = {r["part_number"]: r for r in json.loads(DATA.read_text())["rows"]}

PN_764 = "764A00-11320000/A"  # 220V 1ph, torque 750 Nm / 6,650 in-lbs
PN_762 = "762B00-11320000/A"
PN_761_110 = "761A00-11300000/A"
PN_NODATA = "761A00-11330C00/A"
PN_CSA = "766A00-11320000/A"
CSA_NOTE = "Sizes 6 and 7 are not CSA Certified"

BAD = "4321"  # not present anywhere in the real rows used below


def lookup_trace(pn: str, status: str = "found", notes: list[str] | None = None) -> ToolTrace:
    res = ActuatorLookup(
        status=status, query=pn, normalized=pn, actuator=ROWS[pn], notes=notes or []
    ).model_dump(mode="json")
    return ToolTrace(tool="get_actuator", params={"part_number": pn}, result=res)


def search_trace(pns: list[str], **filters) -> ToolTrace:
    f = SearchFilters(**filters)
    res = SearchResult(
        status="ok", filters=f, matches=[ROWS[p] for p in pns], total=len(pns)
    ).model_dump(mode="json")
    return ToolTrace(tool="search_actuators", params=f.model_dump(mode="json"), result=res)


def no_match_trace(message: str = "No actuator reaches 9000 Nm. Closest: 3500 Nm.") -> ToolTrace:
    rep = NoMatchReport(blocking=["min_torque"], closest={"min_torque": 3500.0}, message=message)
    f = SearchFilters(min_torque=9000)
    res = SearchResult(status="no_match", filters=f, no_match=rep).model_dump(mode="json")
    return ToolTrace(tool="search_actuators", params=f.model_dump(mode="json"), result=res)


def not_found_trace() -> ToolTrace:
    res = ActuatorLookup(
        status="not_found", query="999Z", normalized="999Z", suggestions=[PN_764, PN_762]
    ).model_dump(mode="json")
    return ToolTrace(tool="get_actuator", params={"part_number": "999Z"}, result=res)


def ambiguous_trace() -> ToolTrace:
    cands = [
        Candidate(
            part_number=p,
            enclosure=ROWS[p].enclosure,
            voltage=ROWS[p].voltage,
            phase=ROWS[p].phase,
            service=ROWS[p].service,
            has_data=ROWS[p].has_data,
        )
        for p in (PN_761_110, "761A00-11320000/A")
    ]
    res = ActuatorLookup(
        status="ambiguous", query="761A", normalized="761A", candidates=cands
    ).model_dump(mode="json")
    return ToolTrace(tool="get_actuator", params={"part_number": "761A"}, result=res)


def describe_trace() -> ToolTrace:
    res = CatalogSummary(
        combinations=[{"enclosure": "weatherproof", "voltage": "110V", "phase": 1, "rows": 11}],
        torque_nm_range=(8.0, 3500.0),
        torque_in_lbs_range=(70.0, 31000.0),
        total_rows=68,
        rows_without_data=4,
    ).model_dump(mode="json")
    return ToolTrace(tool="describe_catalog", params={}, result=res)


def nodata_trace() -> ToolTrace:
    return lookup_trace(PN_NODATA, status="found_no_data")


ALL_KINDS = {
    "found": lambda: [lookup_trace(PN_764)],
    "found_no_data": lambda: [nodata_trace()],
    "search_ok": lambda: [search_trace([PN_762, PN_764], min_torque=100)],
    "no_match": lambda: [no_match_trace()],
    "not_found": lambda: [not_found_trace()],
    "ambiguous": lambda: [ambiguous_trace()],
    "describe": lambda: [describe_trace()],
    "empty": list,
}


# ---------------------------------------------------------------- token helpers


def test_token_values_docstring_examples():
    assert R.token_values("1,330") == {1330.0, 1.33}
    assert R.token_values("2,3") == {2.3}
    assert R.token_values("1.330") == {1.33, 1330.0}
    assert R.token_values("17") == {17.0}
    assert R.token_values("1,234,567") == {1234567.0}
    assert R.token_values("2.3") == {2.3}


def test_extract_numbers_basic_forms():
    nums = R.extract_numbers("Torque 1,330 in-lbs, 2.3 A, 2,3 A, 17 s, 40%, 80Nm")
    assert nums == ["1,330", "2.3", "2,3", "17", "40", "80"]


def test_extract_numbers_range():
    assert R.extract_numbers("speed 17-20 s") == ["17", "20"]


@pytest.mark.parametrize(
    "text",
    [
        "Use 764A00 here",
        "Use 764a00 here",
        f"Use {PN_764} here",
        f"Use {PN_CSA}* here",
        "Use 766A00-11320000/A* here",
        "Use 761A00-11330C00/A here",
    ],
)
def test_part_number_digits_are_not_numbers(text):
    assert R.extract_numbers(text) == []


def test_part_number_removed_but_other_numbers_kept():
    assert R.extract_numbers(f"{PN_764} gives 750 Nm") == ["750"]


def test_allowed_numbers_includes_trace_params_query_and_always():
    tr = [lookup_trace(PN_764), search_trace([PN_764], min_torque=123.0)]
    allowed = R.allowed_numbers(tr, "I need 4567 Nm")
    assert {750.0, 6650.0, 27.0, 33.0, 123.0, 4567.0} <= allowed
    assert set(R.ALWAYS_ALLOWED) <= allowed
    assert 4321.0 not in allowed


def test_allowed_numbers_reads_strings_recursively():
    tr = [ToolTrace(tool="x", params={}, result={"a": [{"b": "range 88 to 99"}]})]
    assert {88.0, 99.0} <= R.allowed_numbers(tr, "")


def test_allowed_numbers_includes_thousands_reading():
    tr = [ToolTrace(tool="x", params={}, result={"v": 1330.0})]
    assert 1330.0 in R.allowed_numbers(tr, "")


# ------------------------------------------------------- unverified_numbers


@pytest.mark.parametrize(
    "answer",
    [
        "The 764A00 delivers 750 Nm.",
        "Torque is 6,650 in-lbs.",
        "Torque is 6650 in-lbs.",
        "Speed is 27.0 s.",
        "Speed is 27 s.",
        "Torque 750Nm.",
        "Duty cycle 25%.",
        "FLA 3,2 A and LRA 3.8 A.",
        "FLA 3.20 A.",
        "Speed 27-33 s.",
        "Motor power 180 W.",
    ],
)
def test_correct_numbers_accepted(answer):
    tr = [lookup_trace(PN_764)]
    assert R.unverified_numbers(answer, tr, "tell me about 764A00") == []


def test_spanish_decimal_comma_accepted():
    tr = [lookup_trace(PN_762)]  # fla 1.1, lra 1.2
    assert R.unverified_numbers("Corriente 1,1 A y 1,2 A.", tr, "x") == []


def test_thousands_with_comma_accepted_from_float_trace():
    tr = [lookup_trace(PN_762)]  # mod torque 1330 in-lbs
    assert R.unverified_numbers("1,330 in-lbs", tr, "") == []
    assert R.unverified_numbers("1330 in-lbs", tr, "") == []


def test_range_from_trace_accepted():
    tr = [lookup_trace(PN_761_110)]  # 17 and 20
    assert R.unverified_numbers("17-20 s", tr, "") == []


@pytest.mark.parametrize("bad", [BAD, "99.7", "31.4", "987"])
def test_invented_number_detected(bad):
    tr = [lookup_trace(PN_764)]
    out = R.unverified_numbers(f"The 764A00 gives 750 Nm and {bad} A.", tr, "")
    assert out == [bad]


def test_invented_number_not_masked_by_other_valid():
    tr = [lookup_trace(PN_764)]
    out = R.unverified_numbers("750 Nm, 6,650 in-lbs, 28 s", tr, "")
    assert out == ["28"]


def test_query_numbers_allowed():
    tr = [no_match_trace()]
    q = "I need 200 Nm of torque"
    assert R.unverified_numbers("You asked for 200 Nm.", tr, q) == []
    assert R.unverified_numbers("You asked for 200 Nm.", tr, "I need a motor") == ["200"]


def test_always_allowed_small_ints():
    assert R.unverified_numbers("Step 1, 2 and 3. Rotation 90 degrees.", [], "") == []


def test_no_numbers_no_unverified():
    assert R.unverified_numbers("Nothing numeric here.", [], "") == []


def test_part_number_digits_do_not_trigger_guard():
    tr = [lookup_trace(PN_764)]
    ans = f"{PN_764} and 764A00 and 766A00-11320000/A* are fine; 750 Nm."
    assert R.unverified_numbers(ans, tr, "") == []


def test_part_number_in_answer_not_in_trace_does_not_trigger():
    # digits of PNs never count, even if the PN was never looked up
    assert R.unverified_numbers("Try 765B00-11320000/A.", [], "") == []


# ------------------------------------------------------------- detect_lang


@pytest.mark.parametrize(
    "q", ["¿Cuál es el torque del 764A00?", "Necesito un actuador de 220V", "qué velocidad tiene"]
)
def test_detect_lang_es(q):
    assert R.detect_lang(q) == "es"


@pytest.mark.parametrize("q", ["What is the torque of 764A00?", "I need an actuator for 220V"])
def test_detect_lang_en(q):
    assert R.detect_lang(q) == "en"


# --------------------------------------------------------- template_answer


@pytest.mark.parametrize("kind", sorted(ALL_KINDS))
@pytest.mark.parametrize("query", ["What about this one?", "¿Qué me recomiendas para esto?"])
def test_template_passes_guard_for_every_trace_kind(kind, query):
    trace = ALL_KINDS[kind]()
    text = R.template_answer(trace, query)
    assert isinstance(text, str) and text.strip()
    assert R.unverified_numbers(text, trace, query) == []


def test_template_mentions_product_data():
    trace = [lookup_trace(PN_764)]
    text = R.template_answer(trace, "torque of 764A00")
    assert "764A00" in text
    assert "220V" in text
    assert "weatherproof" in text.lower()
    assert "750" in text  # printed Nm torque


def test_template_search_lists_matches():
    trace = [search_trace([PN_762, PN_764], min_torque=100)]
    text = R.template_answer(trace, "need 100 Nm")
    assert "762B00" in text and "764A00" in text


def test_template_language_follows_query():
    trace = [lookup_trace(PN_764)]
    es = R.template_answer(trace, "¿Cuál es el torque del 764A00?")
    en = R.template_answer(trace, "What is the torque of the 764A00?")
    assert es != en
    es_markers = ("el ", "de ", "torque", "velocidad", "voltaje", "tensión")
    assert any(m in es.lower() for m in es_markers)
    assert " the " not in f" {es.lower()} "
    assert not any(w in f" {en.lower()} " for w in (" del ", " velocidad ", " tensión "))


def test_template_empty_trace_fallback_language():
    es = R.template_answer([], "¿Qué actuador me recomiendas?")
    en = R.template_answer([], "Which actuator do you recommend?")
    assert es != en and es.strip() and en.strip()


def test_template_no_match_uses_message():
    text = R.template_answer([no_match_trace("Nothing reaches 9000 Nm.")], "need 9000 Nm")
    assert "9000" in text


def test_template_not_found_shows_suggestions():
    text = R.template_answer([not_found_trace()], "999Z")
    assert "764A00" in text or "762B00" in text


def test_template_ambiguous_shows_candidates():
    text = R.template_answer([ambiguous_trace()], "761A")
    assert "761A00" in text


# ------------------------------------------------------------ build_result


def test_build_result_clean_answer_unchanged():
    tr = [lookup_trace(PN_764)]
    ans = "The 764A00 delivers 750 Nm."
    res = R.build_result(ans, tr, "torque of 764A00")
    assert isinstance(res, AgentResult)
    assert res.answer == ans
    assert res.guard_triggered is False
    assert len(res.trace) == 1 and res.trace[0].tool == "get_actuator"


@pytest.mark.parametrize("query", ["torque of 764A00?", "¿torque del 764A00?"])
def test_build_result_invented_number_triggers_guard(query):
    tr = [lookup_trace(PN_764)]
    ans = f"The 764A00 delivers 750 Nm and draws {BAD} A."
    res = R.build_result(ans, tr, query)
    assert res.guard_triggered is True
    assert res.answer != ans
    assert BAD not in res.answer
    assert R.unverified_numbers(res.answer, tr, query) == []
    assert len(res.trace) == 2
    g = res.trace[-1]
    assert g.tool == R.GUARD_TOOL
    assert BAD in g.params["unverified"]
    assert g.params["original_answer"] == ans
    assert res.trace[0].tool == "get_actuator"


def test_build_result_does_not_mutate_input_trace_semantics():
    tr = [lookup_trace(PN_764)]
    res = R.build_result(f"gives {BAD} Nm", tr, "q")
    assert res.trace[0] == tr[0]
    assert res.trace[-1].tool == R.GUARD_TOOL


def test_build_result_guard_products_from_template():
    tr = [lookup_trace(PN_764)]
    res = R.build_result(f"gives {BAD} Nm", tr, "q")
    assert [p.part_number for p in res.products] == [PN_764]


def test_build_result_empty_trace_no_numbers_unchanged():
    res = R.build_result("I could not find that; please rephrase.", [], "hi")
    assert res.answer == "I could not find that; please rephrase."
    assert res.guard_triggered is False
    assert res.products == [] and res.trace == []


def test_build_result_empty_trace_with_number_triggers():
    res = R.build_result("The torque is 150 Nm.", [], "hello")
    assert res.guard_triggered is True
    assert "150" not in res.answer
    assert len(res.trace) == 1 and res.trace[0].tool == R.GUARD_TOOL
    assert res.trace[0].params["unverified"] == ["150"]
    assert res.products == []


def test_build_result_wrong_unit_variant_of_real_number_rejected():
    # 7500 is not any printed value for 764A00 (750 / 6650)
    tr = [lookup_trace(PN_764)]
    res = R.build_result("Torque is 7,500 Nm", tr, "")
    assert res.guard_triggered is True


def test_build_result_query_number_echo_ok():
    tr = [no_match_trace("Nothing reaches the requested torque.")]
    q = "I need 9500 Nm"
    res = R.build_result("No actuator reaches 9500 Nm.", tr, q)
    assert res.guard_triggered is False


def test_build_result_spanish_template_on_guard():
    tr = [lookup_trace(PN_764)]
    res = R.build_result(f"Entrega {BAD} Nm", tr, "¿Qué torque tiene el 764A00?")
    assert res.guard_triggered
    assert " the " not in f" {res.answer.lower()} "


# ---------------------------------------------------------------- products


def pns(products):
    return [p.part_number for p in products]


def test_products_found():
    ps = R.products_from_trace([lookup_trace(PN_764)], "764A00 info")
    assert pns(ps) == [PN_764]


def test_products_trace_order():
    tr = [lookup_trace(PN_764), lookup_trace(PN_762)]
    assert pns(R.products_from_trace(tr, "no mention")) == [PN_764, PN_762]


def test_products_search_order_and_all_kept_when_none_mentioned():
    tr = [search_trace([PN_762, PN_764, PN_761_110], min_torque=50)]
    assert pns(R.products_from_trace(tr, "here are some")) == [PN_762, PN_764, PN_761_110]


def test_products_dedupe_across_tools():
    tr = [
        lookup_trace(PN_764),
        search_trace([PN_764, PN_762], min_torque=100),
        lookup_trace(PN_762),
    ]
    assert pns(R.products_from_trace(tr, "x")) == [PN_764, PN_762]


def test_products_mention_filter_by_base_case_insensitive():
    tr = [search_trace([PN_762, PN_764], min_torque=100)]
    assert pns(R.products_from_trace(tr, "I suggest the 764a00.")) == [PN_764]


def test_products_mention_filter_by_full_pn_case_insensitive():
    tr = [search_trace([PN_762, PN_764], min_torque=100)]
    assert pns(R.products_from_trace(tr, f"Pick {PN_762.lower()} today")) == [PN_762]


def test_products_mention_filter_multiple():
    tr = [search_trace([PN_762, PN_764, PN_761_110], min_torque=50)]
    got = R.products_from_trace(tr, "762B00 or 764A00 will do")
    assert pns(got) == [PN_762, PN_764]


def test_products_mention_of_unrelated_pn_keeps_all():
    tr = [search_trace([PN_762, PN_764], min_torque=100)]
    assert pns(R.products_from_trace(tr, "not 999Z00 at all")) == [PN_762, PN_764]


@pytest.mark.parametrize("kind", ["no_match", "not_found", "ambiguous", "describe", "empty"])
def test_no_products_for_non_product_results(kind):
    tr = ALL_KINDS[kind]()
    assert R.products_from_trace(tr, f"{PN_764} 764A00") == []


def test_found_no_data_gives_product_without_data():
    ps = R.products_from_trace([nodata_trace()], "761A00")
    assert len(ps) == 1
    assert ps[0].has_data is False
    assert ps[0].fields == {}


def test_notes_from_get_actuator_copied():
    tr = [lookup_trace(PN_764, notes=["Voltage tolerance +/-10%", "Duty per IEC 60034-1"])]
    ps = R.products_from_trace(tr, "x")
    assert ps[0].notes == ["Voltage tolerance +/-10%", "Duty per IEC 60034-1"]


def test_csa_note_in_search_for_uncertified():
    tr = [search_trace([PN_CSA, PN_764], min_torque=3000)]
    ps = {p.part_number: p for p in R.products_from_trace(tr, "x")}
    assert ps[PN_CSA].csa_certified is False
    assert any("CSA" in n for n in ps[PN_CSA].notes)
    assert ps[PN_764].notes == []


def test_csa_note_from_lookup_passes_through():
    tr = [lookup_trace(PN_CSA, notes=[CSA_NOTE])]
    ps = R.products_from_trace(tr, "x")
    assert ps[0].csa_certified is False
    assert CSA_NOTE in ps[0].notes


@pytest.mark.parametrize("pn", [PN_764, PN_762, PN_761_110, PN_CSA, "764A00-11330C00/A"])
def test_product_fields_equal_row_numeric_fields(pn):
    ps = R.products_from_trace([lookup_trace(pn)], "x")
    assert len(ps) == 1
    expected = {
        k: v for k, v in RAW[pn].items() if isinstance(v, float) and k not in ("row_index",)
    }
    assert ps[0].fields == expected
    assert ps[0].part_number == pn
    assert ps[0].voltage == RAW[pn]["voltage"]
    assert ps[0].enclosure == RAW[pn]["enclosure"]
    assert ps[0].phase == RAW[pn]["phase"]


def test_product_fields_from_search_equal_row():
    ps = R.products_from_trace([search_trace([PN_762], min_torque=100)], "x")
    assert ps[0].fields["mod_torque_nm"] == 150.0
    assert ps[0].fields["onoff_torque_in_lbs"] == 1750.0


def test_build_result_products_filtered_by_final_answer():
    tr = [search_trace([PN_762, PN_764], min_torque=100)]
    res = R.build_result("Choose the 764A00 (750 Nm).", tr, "need 100 Nm")
    assert res.guard_triggered is False
    assert pns(res.products) == [PN_764]
