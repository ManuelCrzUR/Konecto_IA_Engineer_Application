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
    assert {80.0, 700.0, 10.0, 110.0, 3500.0, 42.0, 123.0} <= allowed
    assert 7.0 not in allowed and 90.0 not in allowed  # no blanket small-int list (D-44)
    assert not hasattr(R, "ALWAYS_ALLOWED")
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


def test_guard_allows_query_numbers():
    trace = [found(A761)]
    assert R.unverified_numbers("Pediste 500 Nm; opcion 2 de 3.", trace, "necesito 500 Nm") == [
        "2",
        "3",
    ]
    assert R.unverified_numbers("Pediste 500 Nm.", trace, "necesito 500 Nm") == []
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


@pytest.mark.parametrize(
    "text",
    [
        "the Series 76 catalog",
        "series-76 actuators",
        "SERIES 76",
        "actuadores Serie 76",
        "la série 76",
    ],
)
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


# ---- Gate 5.5: model size named in the answer ---------------------------------
def test_model_size_of_a_returned_part_number_is_not_a_figure() -> None:
    trace = [tr("get_actuator", {"status": "found"}, part_number="764A00-11320000/A")]
    answer = "Of the pair, the 764 is the larger frame."
    assert R.unverified_numbers(answer, trace, "compare them") == []


def test_model_size_without_that_product_in_the_trace_is_flagged() -> None:
    trace = [tr("get_actuator", {"status": "found"}, part_number="763A00-11320000/A")]
    assert R.unverified_numbers("The 765 is larger.", trace, "q") == ["765"]


def test_apply_persona_variants_and_untouched_text() -> None:
    mid = "stealth/crouton-alpha"
    for text in ("I'm Crouton Alpha.", "I'm crouton-alpha.", "CROUTON ALPHA here", "CroutonAlpha"):
        out, found = R.apply_persona(text, mid)
        assert "Axel" in out and found and "routon" not in out
    text = "Torque 750 Nm, part 764A00-11300000/A; a crouton is food."
    assert R.apply_persona(text, mid) == (text, [])


def test_apply_persona_ignores_short_generic_ids() -> None:
    text = "The gpt and chat and free text, 4o, claude."
    for mid in ("openai/gpt-4o", "vendor/chat", "x/free", "x/model-preview", "", "a/b-1.5"):
        assert R.apply_persona(text, mid) == (text, [])


def test_apply_persona_distinctive_single_token_and_suffix() -> None:
    out, found = R.apply_persona("I am Mistral.", "mistralai/mistral:free")
    assert out == "I am Axel." and found == ["Mistral"]
    out, _ = R.apply_persona("I am Claude Sonnet", "anthropic/claude-3.5-sonnet")
    assert out == "I am Axel"
    # word boundary: no rewrite inside a longer word
    assert R.apply_persona("Mistrals", "mistralai/mistral")[1] == []


def test_build_result_persona_trace_only_when_replaced() -> None:
    res = R.build_result("I'm Crouton Alpha.", [], "who?", model_id="stealth/crouton-alpha")
    assert res.answer == "I'm Axel."
    assert [t.tool for t in res.trace] == ["persona_guard"]
    assert res.trace[0].params == {"replaced": ["Crouton Alpha"]}
    assert res.guard_triggered is False
    clean = R.build_result("I'm Axel.", [], "who?", model_id="stealth/crouton-alpha")
    assert clean.trace == []


# ---- Guard v2 (D-44) ------------------------------------------------------------
B764 = "764A00-11300000/A"  # 6.5 A, 30 s; 765B00 below owns 108 s
B765 = Actuator.model_validate(BY_PN["765B00-11300000/A"]).model_dump(mode="json")
PAIR = [found(A764), found(B765)]


def bad(answer: str, trace: list[ToolTrace] | None = None, q: str = "q", **kw: Any) -> list[str]:
    return R.unverified_numbers(answer, PAIR if trace is None else trace, q, **kw)


def test_v2_fixture_sanity() -> None:
    v764 = R._product_values(PAIR)
    assert 108.0 in v764["765B00-11300000"] and 108.0 not in v764["764A00-11300000"]
    assert 6.5 in v764["764A00-11300000"] and 9.0 not in v764["764A00-11300000"]


def test_v2_invented_small_int_fires() -> None:
    ans = f"{B764} has FLA 9 A."
    assert bad(ans) == ["9"]
    assert R.build_result(ans, PAIR, "q").guard_triggered


def test_v2_approximate_seconds_fires() -> None:
    assert bad(f"{B764} takes about 7 seconds.") == ["7"]


def test_v2_number_words_fire_in_both_languages() -> None:
    assert bad("Tarda siete segundos.", [found(A764)]) == ["siete"]
    assert bad("It takes seven seconds.", [found(A764)]) == ["seven"]
    assert bad("Dieciséis y dieciseis y twelve y diez.", []) == [
        "Dieciséis", "dieciseis", "twelve", "diez",
    ]  # fmt: skip
    assert R.token_values("Dieciséis") == {16.0} and R.token_values("seven") == {7.0}


def test_v2_number_word_matching_trace_value_passes() -> None:
    trace = [tr("x", {"count": 7})]
    assert bad("There are seven.", trace) == []
    assert bad("Hay siete.", [], "dame siete") == []  # typed by the user


def test_v2_wrong_product_binding_fires() -> None:
    # 108 s exists in the trace, but only on 765B00.
    assert bad("764A00 has 108 s.") == ["108"]
    assert bad("765B00 has 108 s.") == []


def test_v2_correct_number_next_to_its_product_passes() -> None:
    assert bad(f"{B764} has 6.5 A and 765B00 has 108 s.") == []
    assert bad("764A00 has 6,5 A; 765B00 has 108 s.") == []


def test_v2_binding_uses_nearest_preceding_mention_in_the_sentence() -> None:
    assert bad("764A00 has 108 s. Meanwhile 108 s is common.") == ["108"]
    # new sentence: no mention before the figure, so the global rule applies
    assert bad("764A00 is fine. The other has 108 s.") == []


def test_v2_markdown_table_row_binding() -> None:
    ok = "| PN | FLA |\n|---|---|\n| 764A00 | 6.5 |\n| 765B00 | 108 |"
    assert bad(ok) == []
    swapped = "| PN | FLA |\n|---|---|\n| 764A00 | 108 |\n| 765B00 | 6.5 |"
    assert bad(swapped) == ["108", "6.5"]


def test_v2_ordinals_and_stroke_are_free() -> None:
    assert bad("1. 764A00 is good\n2) 765B00 too\n3. last one", []) == []
    assert bad("Rotates 90° and 90 degrees and 90 grados.", []) == []
    assert bad("It has 1. Not an ordinal here, 2) neither", []) == ["1", "2"]


def test_v2_ninety_nm_is_not_the_stroke() -> None:
    assert bad("It delivers 90 Nm.", [found(A764)]) == ["90"]
    assert bad("It delivers 90 Nm, and 90 degrees.", [found(A764)]) == ["90"]


def test_v2_referent_binds_when_no_part_number_is_mentioned() -> None:
    trace = [found(A764), found(B765)]
    # 108 is in the trace (on 765B00) but the conversation is about 764A00
    assert bad("It has 108 s.", trace, referent=B764) == ["108"]
    assert bad("It has 6.5 A.", trace, referent=B764) == []
    assert bad("It has 108 s.", trace) == []  # no referent: global rule
    # a mention in the answer disables the referent
    assert bad("765B00 has 108 s.", trace, referent=B764) == []
    # referent not in the trace: fall back to the global rule
    assert bad("It has 108 s.", trace, referent="761A00-11300000/A") == []
    res = R.build_result("It has 108 s.", trace, "and its FLA?", referent=B764)
    assert res.guard_triggered


def test_v2_articles_are_not_numbers() -> None:
    assert bad("Tengo un actuador y una duda, uno solo.", []) == []
    assert bad("A single one, once more: a good fit.", []) == []
    assert R.extract_numbers("un una uno one once") == []


def test_v2_small_talk_with_figures_falls_back_to_template() -> None:
    res = R.build_result("Hello! I know 3 actuators.", [], "hi")
    assert res.guard_triggered
    assert "could not verify" in res.answer
    assert R.build_result("Hello! How can I help?", [], "hi").guard_triggered is False
    assert R.build_result("Hola, tengo cinco ideas.", [], "hola").guard_triggered
    assert not R.build_result("Hola, dices tres.", [], "dame tres").guard_triggered


def test_v2_user_history_still_trusted() -> None:
    assert bad("You said 42 A for 764A00.", [found(A764)], "q", user_history="FLA is 42 A") == []


def test_counts_of_tool_results_are_verified():
    """'I found 2 options' is a count of what search_actuators returned, not an invented figure."""
    matches = [r for r in ROWS if r["part_number"][:6] in ("764A00", "765A00")][:2]
    assert len(matches) == 2
    names = " y ".join(m["part_number"] for m in matches)
    trace = [
        ToolTrace(tool="search_actuators", params={}, result={"status": "ok", "matches": matches})
    ]
    ok = R.build_result(f"Encontré 2 opciones: {names}.", trace, "busco un actuador")
    assert not ok.guard_triggered
    allowed = R.allowed_numbers(trace, "busco un actuador")
    assert 2.0 in allowed
    absent = next(n for n in range(3, 100) if float(n) not in allowed)
    bad = R.build_result(f"Encontré {absent} opciones: {names}.", trace, "busco un actuador")
    assert bad.guard_triggered
