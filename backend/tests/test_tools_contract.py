"""Black-box contract tests for app/agent/tools.py (needs Postgres).

Expected values are derived from data/processed/actuators.json with plain Python,
independently of the code under test.
"""

from __future__ import annotations

import json
import re

import pytest
from pydantic import ValidationError

from app.agent import tools
from app.db import actuators_repo as repo
from app.domain.models import Actuator, Catalog
from app.domain.search import SearchFilters
from tests.conftest import PROCESSED_JSON

CATALOG = Catalog.model_validate_json(PROCESSED_JSON.read_text())
ROWS = CATALOG.rows
BY_PN = {r.part_number: r for r in ROWS}
TABLE_NOTES = {t.table_id: t.notes for t in CATALOG.tables}
CSA_NOTE = "Sizes 6 and 7 are not CSA Certified"


@pytest.fixture
def db(pg):
    repo.upsert_catalog(pg, CATALOG)
    return pg


# ---------------------------------------------------------------- normalize


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (" 764a00-11300000/a ", "764A00-11300000/A"),
        ("764A00-11300000", "764A00-11300000/A"),
        ("766A00-11320000/A*", "766A00-11320000/A"),
        ("766A00-11320000*", "766A00-11320000/A"),
        ("764a", "764A"),
        ("764A00", "764A00"),
        ("764", "764"),
        ("764A0011300000", "764A00-11300000/A"),
        ("764a0011300000/a", "764A00-11300000/A"),
        ("  764a00 - 11300000 / a ", "764A00-11300000/A"),
        ("764A00-11300000/A", "764A00-11300000/A"),
        ("", ""),
        ("   ", ""),
    ],
)
def test_normalize_examples(raw, expected):
    assert tools.normalize_part_number(raw) == expected


@pytest.mark.parametrize("raw", ["", "???", "hello world", "\n\t", "-", "/A", "*", "💥", "a" * 500])
def test_normalize_never_raises_and_is_clean(raw):
    out = tools.normalize_part_number(raw)
    assert isinstance(out, str)
    assert out == out.upper()
    assert not re.search(r"\s|\*", out)


@pytest.mark.parametrize("pn", [r.part_number for r in ROWS])
def test_normalize_is_idempotent_on_catalog_pns(pn):
    assert tools.normalize_part_number(pn) == pn
    assert tools.normalize_part_number(pn.lower()) == pn
    assert tools.normalize_part_number(pn.replace("-", "").removesuffix("/A")) == pn


# ------------------------------------------------------------------- lookup


@pytest.mark.parametrize("pn", [r.part_number for r in ROWS])
def test_every_catalog_pn_is_found_exactly(db, pn):
    row = BY_PN[pn]
    res = tools.lookup_actuator(db, pn)
    assert res.status == ("found" if row.has_data else "found_no_data")
    assert res.actuator is not None
    assert res.actuator == row
    assert res.actuator.has_data == row.has_data
    assert res.candidates == []
    assert res.normalized == pn
    assert res.query == pn
    # notes: table notes, then CSA note exactly for csa_certified=False rows
    table = TABLE_NOTES[row.table_id]
    assert res.notes[: len(table)] == table
    extra = res.notes[len(table) :]
    if row.csa_certified:
        assert extra == []
    else:
        assert any(CSA_NOTE in n for n in res.notes)


def test_csa_note_absent_for_other_tables(db):
    for row in ROWS:
        if row.table_id != "T2_wp_220v_1ph":
            res = tools.lookup_actuator(db, row.part_number)
            assert not any(CSA_NOTE in n for n in res.notes), row.part_number


def test_na_rows_are_found_no_data(db):
    na = [r.part_number for r in ROWS if not r.has_data]
    assert len(na) == 4
    for pn in na:
        res = tools.lookup_actuator(db, pn)
        assert res.status == "found_no_data"
        assert res.actuator is not None


@pytest.mark.parametrize(
    "variant",
    [
        "  764a00 - 11300000 / a ",
        "764A00-11300000",
        "764a0011300000",
        "764A0011300000/A",
        "764A00-11300000/A*",
        "764A00-11300000*",
    ],
)
def test_lookup_messy_forms_of_same_pn(db, variant):
    res = tools.lookup_actuator(db, variant)
    assert res.status in {"found", "found_no_data"}
    assert res.actuator is not None
    assert res.actuator.part_number == "764A00-11300000/A"
    assert res.query == variant
    assert res.normalized == "764A00-11300000/A"


def test_asterisk_input_finds_csa_row(db):
    res = tools.lookup_actuator(db, "766A00-11320000/A*")
    assert res.actuator is not None
    assert res.actuator.part_number == "766A00-11320000/A"
    assert res.actuator.csa_certified is False
    assert any(CSA_NOTE in n for n in res.notes)


def _prefix_rows(prefix: str) -> list[Actuator]:
    return sorted(
        (r for r in ROWS if r.part_number.startswith(prefix)), key=lambda r: r.part_number
    )


@pytest.mark.parametrize("prefix", ["764A00", "764a00", " 764A ", "764", "761A00", "76", "7"])
def test_prefix_behaviour(db, prefix):
    norm = tools.normalize_part_number(prefix)
    expected = _prefix_rows(norm)
    res = tools.lookup_actuator(db, prefix)
    if len(norm) < 3:
        assert res.status == "not_found"
        assert res.candidates == []
        return
    assert len(expected) >= 2
    assert res.status == "ambiguous"
    assert res.actuator is None
    assert [c.part_number for c in res.candidates] == [r.part_number for r in expected]
    for c, r in zip(res.candidates, expected, strict=True):
        assert c.enclosure == r.enclosure
        assert c.voltage == r.voltage
        assert c.phase == r.phase
        assert c.service == r.service
        assert c.has_data == r.has_data


def test_prefix_matching_at_most_20_rows(db):
    res = tools.lookup_actuator(db, "76")
    assert res.status == "not_found"  # shorter than 3 chars -> no prefix step


def test_prefix_three_chars_goes_to_prefix_match(db):
    res = tools.lookup_actuator(db, "761")
    assert res.status == "ambiguous"
    assert len(res.candidates) <= 20
    assert all(c.part_number.startswith("761") for c in res.candidates)


def test_prefix_matching_exactly_one_row_behaves_as_found(db):
    # Find a >=3 char prefix that matches exactly one catalog row.
    pns = [r.part_number for r in ROWS]
    chosen = None
    for pn in pns:
        base = pn.split("-")[0]
        for cut in range(len(base) + 1, len(pn)):
            p = pn[:cut]
            if len(p) >= 3 and sum(x.startswith(p) for x in pns) == 1:
                chosen = (pn, p)
                break
        if chosen:
            break
    assert chosen, "catalog has no unique prefix?"
    pn, prefix = chosen
    res = tools.lookup_actuator(db, prefix)
    assert res.status == ("found" if BY_PN[pn].has_data else "found_no_data")
    assert res.actuator is not None
    assert res.actuator.part_number == pn
    assert res.candidates == []


@pytest.mark.parametrize(
    "text",
    [
        "",
        "   ",
        "hello",
        "999Z99-99999999/A",
        "764A00-99999999/A",
        "DROP TABLE actuators;",
        "%",
        "_",
        "76%",
        "\\",
        "' OR 1=1 --",
        "💥",
        "x" * 400,
        "764A00-1130000O/A",
    ],
)
def test_garbage_never_raises_and_not_found(db, text):
    res = tools.lookup_actuator(db, text)
    if res.status == "not_found":
        assert res.actuator is None
        assert res.candidates == []
        assert len(res.suggestions) <= 5
        assert set(res.suggestions) <= set(BY_PN)
    else:  # wildcard-looking prefixes must not match everything silently
        assert res.status in {"ambiguous", "found", "found_no_data"}


@pytest.mark.parametrize("wild", ["%", "_", "76%", "7_4", "%%%", "___"])
def test_like_wildcards_are_literal(db, wild):
    res = tools.lookup_actuator(db, wild)
    assert res.status == "not_found"


def test_typo_gets_close_suggestions(db):
    res = tools.lookup_actuator(db, "764A00-1130000O/A")
    # one char off from a real PN: must suggest it
    assert res.status == "not_found"
    assert "764A00-11300000/A" in res.suggestions
    assert len(res.suggestions) <= 5
    assert set(res.suggestions) <= set(BY_PN)


def test_nonexistent_but_well_formed_pn_has_real_suggestions(db):
    res = tools.lookup_actuator(db, "764A00-11300001/A")
    assert res.status == "not_found"
    assert 1 <= len(res.suggestions) <= 5
    assert set(res.suggestions) <= set(BY_PN)
    assert len(set(res.suggestions)) == len(res.suggestions)


def test_far_input_gives_empty_suggestions(db):
    res = tools.lookup_actuator(db, "zzzzzzzzzzzzzzzz")
    assert res.status == "not_found"
    assert res.suggestions == []


def test_lookup_does_not_commit_or_change_data(db):
    before = db.execute("SELECT count(*) FROM actuators").fetchone()[0]
    tools.lookup_actuator(db, "764A00-11300000/A")
    tools.search(db, SearchFilters(min_torque=10))
    assert db.execute("SELECT count(*) FROM actuators").fetchone()[0] == before == 68


# ------------------------------------------------------------------- search


def _fam(r: Actuator, f: SearchFilters, service: str | None):
    """Reference: list of (torque, duty) families that apply for this service."""
    u = "nm" if f.torque_unit == "nm" else "in_lbs"
    on = (getattr(r, f"onoff_torque_{u}"), r.onoff_duty_cycle_pct)
    mod = (getattr(r, f"mod_torque_{u}"), r.mod_duty_cycle_pct)
    out = (getattr(r, f"output_torque_{u}"), r.duty_cycle_pct)
    if service == "on_off":
        return [on if on[0] is not None or on[1] is not None else out]
    if service == "modulating":
        return [mod if mod[0] is not None or mod[1] is not None else out]
    return [on, mod, out]


def ref_matches(f: SearchFilters, unspecified_matches_service: bool = True) -> list[Actuator]:
    out = []
    for r in ROWS:
        if f.enclosure and r.enclosure != f.enclosure:
            continue
        if f.phase is not None and r.phase != f.phase:
            continue
        if f.voltage_v is not None and not r.voltage.startswith(f"{f.voltage_v}V"):
            continue
        if f.service:
            allowed = {"on_off_and_modulating", f.service}
            if unspecified_matches_service:
                allowed.add("unspecified")
            if r.service not in allowed:
                continue
        numeric = (f.min_torque, f.max_speed_sec, f.min_duty_cycle_pct)
        if any(v is not None for v in numeric) and not r.has_data:
            continue
        if f.max_speed_sec is not None:
            s = getattr(r, f"speed_sec_{f.speed_hz}hz")
            s = s if s is not None else r.speed_sec
            if s is None or s > f.max_speed_sec:
                continue
        if f.min_torque is not None or f.min_duty_cycle_pct is not None:
            ok = False
            for t, d in _fam(r, f, f.service):
                if f.min_torque is not None and (t is None or t < f.min_torque):
                    continue
                if f.min_duty_cycle_pct is not None and (d is None or d < f.min_duty_cycle_pct):
                    continue
                ok = True
            if not ok:
                continue
        out.append(r)
    return out


def _assert_search(db, f: SearchFilters, limit: int | None = None):
    res = tools.search(db, f) if limit is None else tools.search(db, f, limit=limit)
    lo = {r.part_number for r in ref_matches(f, unspecified_matches_service=False)}
    hi = {r.part_number for r in ref_matches(f, unspecified_matches_service=True)}
    got = [a.part_number for a in res.matches]
    assert len(got) == len(set(got))
    assert set(got) <= hi
    eff_limit = 5 if limit is None else limit
    assert len(got) == min(eff_limit, res.total)
    assert len(lo) <= res.total <= len(hi)
    assert res.filters == f
    assert (res.status == "ok") == (res.total > 0)
    if res.status == "ok":
        assert res.no_match is None
    else:
        assert res.no_match is not None
        assert res.matches == []
        assert res.no_match.message
    return res, lo, hi


@pytest.mark.parametrize(
    "kw",
    [
        {"min_torque": 100},
        {"min_torque": 100, "voltage_v": 220},
        {"min_torque": 1000, "torque_unit": "in_lbs", "voltage_v": 110},
        {"min_torque": 50, "service": "on_off", "enclosure": "weatherproof"},
        {"min_torque": 50, "service": "modulating", "voltage_v": 110},
        {"voltage_v": 24},
        {"voltage_v": 24, "service": "modulating"},
        {"voltage_v": 24, "service": "on_off", "min_torque": 20},
        {"phase": 3},
        {"phase": 3, "min_torque": 100},
        {"phase": 1, "enclosure": "explosionproof"},
        {"max_speed_sec": 20},
        {"max_speed_sec": 20, "speed_hz": 50},
        {"max_speed_sec": 30, "voltage_v": 24},
        {"min_duty_cycle_pct": 50},
        {"min_duty_cycle_pct": 40, "min_torque": 50, "voltage_v": 220, "phase": 1},
        {"enclosure": "explosionproof", "min_torque": 30, "max_speed_sec": 60},
        {"voltage_v": 110, "enclosure": "weatherproof"},
        {},
    ],
)
def test_search_matches_reference(db, kw):
    f = SearchFilters(**kw)
    res, lo, hi = _assert_search(db, f)
    ref_all = {r.part_number for r in ref_matches(f)}
    # every returned match must satisfy the reference rule
    assert {a.part_number for a in res.matches} <= hi
    if lo == hi:
        assert res.total == len(ref_all)
        # when result is not truncated it must equal the reference exactly
        if res.total <= 5:
            assert {a.part_number for a in res.matches} == ref_all


def test_search_unfiltered_total_is_catalog_size(db):
    res = tools.search(db, SearchFilters())
    assert res.total == 68
    assert len(res.matches) == 5


def test_search_default_limit_and_custom_limit(db):
    f = SearchFilters(voltage_v=220)
    assert len(tools.search(db, f).matches) == 5
    r2 = tools.search(db, f, limit=2)
    assert len(r2.matches) == 2
    assert r2.total == len({r.part_number for r in ROWS if r.voltage.startswith("220V")})
    r3 = tools.search(db, f, limit=1000)
    assert len(r3.matches) == r3.total


def test_search_total_independent_of_limit(db):
    f = SearchFilters(min_torque=100, voltage_v=220)
    assert tools.search(db, f, limit=1).total == tools.search(db, f, limit=50).total


def test_search_filters_echo_defaults(db):
    f = SearchFilters(min_torque=100, torque_unit="in_lbs")
    res = tools.search(db, f)
    assert res.filters.torque_unit == "in_lbs"
    assert res.filters.speed_hz == 60
    assert res.filters.min_torque == 100


def test_search_torque_unit_changes_column(db):
    # 100 Nm vs 100 in-lbs must give different totals (no conversion, printed column)
    nm = tools.search(db, SearchFilters(min_torque=100, voltage_v=220, phase=1))
    il = tools.search(
        db, SearchFilters(min_torque=100, torque_unit="in_lbs", voltage_v=220, phase=1)
    )
    assert nm.total < il.total


def test_search_na_rows_never_match_numeric_filters(db):
    na = {r.part_number for r in ROWS if not r.has_data}
    for kw in ({"min_torque": 0.1}, {"max_speed_sec": 1000}, {"min_duty_cycle_pct": 0}):
        res = tools.search(db, SearchFilters(**kw), limit=1000)
        assert not na & {a.part_number for a in res.matches}, kw


def test_search_phase_filter_excludes_24v(db):
    for ph in (1, 3):
        res = tools.search(db, SearchFilters(phase=ph, voltage_v=24))
        assert res.status == "no_match"
        assert res.total == 0


def test_search_matches_are_ordered_tightest_fit_first(db):
    f = SearchFilters(min_torque=100, voltage_v=220, phase=1, service="on_off")
    res = tools.search(db, f, limit=1000)
    ts = []
    for a in res.matches:
        t = a.onoff_torque_nm if a.onoff_torque_nm is not None else a.output_torque_nm
        assert t is not None
        ts.append(t)
    assert ts == sorted(ts)
    assert ts[0] >= 100


def test_search_no_match_impossible_torque(db):
    res = tools.search(db, SearchFilters(min_torque=1_000_000))
    assert res.status == "no_match"
    assert res.matches == [] and res.total == 0
    nm = res.no_match
    assert nm is not None
    assert "min_torque" in nm.blocking
    assert nm.out_of_catalog is False
    max_t = max(
        t
        for r in ROWS
        for t in (r.onoff_torque_nm, r.mod_torque_nm, r.output_torque_nm)
        if t is not None
    )
    assert nm.closest["min_torque"] == pytest.approx(max_t)


def test_search_no_match_closest_respects_other_filters(db):
    res = tools.search(
        db, SearchFilters(min_torque=1_000_000, voltage_v=110, enclosure="weatherproof")
    )
    assert res.no_match is not None
    cands = [
        t
        for r in ROWS
        if r.voltage == "110V" and r.enclosure == "weatherproof"
        for t in (r.onoff_torque_nm, r.mod_torque_nm, r.output_torque_nm)
        if t is not None
    ]
    assert res.no_match.closest["min_torque"] == pytest.approx(max(cands))


@pytest.mark.parametrize(
    "kw",
    [
        {"voltage_v": 24, "enclosure": "weatherproof"},
        {"phase": 3, "enclosure": "explosionproof"},
        {"phase": 3, "enclosure": "explosionproof", "min_torque": 10},
        {"voltage_v": 24, "enclosure": "weatherproof", "min_torque": 10},
    ],
)
def test_search_out_of_catalog(db, kw):
    res = tools.search(db, SearchFilters(**kw))
    assert res.status == "no_match"
    assert res.no_match is not None
    assert res.no_match.out_of_catalog is True
    assert res.no_match.message


def test_search_no_match_not_out_of_catalog_when_combination_exists(db):
    res = tools.search(db, SearchFilters(voltage_v=110, enclosure="weatherproof", min_torque=99999))
    assert res.no_match is not None
    assert res.no_match.out_of_catalog is False


def test_search_no_match_diagnosis_only_for_no_match(db):
    ok = tools.search(db, SearchFilters(voltage_v=220))
    assert ok.status == "ok" and ok.no_match is None


# ----------------------------------------------------------------- describe


def test_describe_totals(db):
    s = tools.describe(db)
    assert s.total_rows == 68
    assert s.rows_without_data == 4
    nms = [
        t
        for r in ROWS
        for t in (r.onoff_torque_nm, r.mod_torque_nm, r.output_torque_nm)
        if t is not None
    ]
    ils = [
        t
        for r in ROWS
        for t in (r.onoff_torque_in_lbs, r.mod_torque_in_lbs, r.output_torque_in_lbs)
        if t is not None
    ]
    assert s.torque_nm_range == (min(nms), max(nms))
    assert s.torque_in_lbs_range == (min(ils), max(ils))


def test_describe_combinations_cover_all_tables(db):
    s = tools.describe(db)
    assert sum(int(c["rows"]) for c in s.combinations) == 68
    assert {c["table_id"] for c in s.combinations} == {t.table_id for t in CATALOG.tables}
    by_table = {c["table_id"]: int(c["rows"]) for c in s.combinations}
    for tid, n in by_table.items():
        assert n == sum(r.table_id == tid for r in ROWS)


# --------------------------------------------------------------- make_tools


@pytest.fixture
def lc_tools(db, pg_conn):

    import psycopg

    from tests.conftest import get_test_db_url

    url = get_test_db_url()

    def factory():
        return psycopg.connect(url, autocommit=True)

    return {t.name: t for t in tools.make_tools(factory)}, tools.make_tools(factory)


def test_make_tools_names_and_order(lc_tools):
    _, ordered = lc_tools
    assert tuple(t.name for t in ordered) == tools.TOOL_NAMES
    assert tools.TOOL_NAMES == ("get_actuator", "search_actuators", "describe_catalog")


def test_tool_descriptions_exist_and_have_no_catalog_numbers(lc_tools):
    _, ordered = lc_tools
    torques = set()
    for r in ROWS:
        for v in (
            r.onoff_torque_nm,
            r.mod_torque_nm,
            r.output_torque_nm,
            r.onoff_torque_in_lbs,
            r.mod_torque_in_lbs,
            r.output_torque_in_lbs,
        ):
            if v is not None and v >= 100:
                torques.add(f"{v:g}")
    for t in ordered:
        assert len(t.description) > 40
        words = set(re.findall(r"\d[\d,.]*\d|\d", t.description))
        words = {w.rstrip(".,") for w in words}
        assert not words & torques, (t.name, words & torques)


def test_get_actuator_tool_returns_json_dict(lc_tools):
    by_name, _ = lc_tools
    out = by_name["get_actuator"].invoke({"part_number": " 764a00-11300000 "})
    assert isinstance(out, dict)
    json.dumps(out)
    assert out["status"] in {"found", "found_no_data"}
    assert out["actuator"]["part_number"] == "764A00-11300000/A"
    assert out["actuator"] == BY_PN["764A00-11300000/A"].model_dump(mode="json")


def test_get_actuator_tool_handles_garbage(lc_tools):
    by_name, _ = lc_tools
    for text in ("", "???", "%", "999"):
        out = by_name["get_actuator"].invoke({"part_number": text})
        json.dumps(out)
        assert out["status"] in {"not_found", "ambiguous"}


def test_search_tool_flat_args(lc_tools):
    by_name, _ = lc_tools
    out = by_name["search_actuators"].invoke({"min_torque": 100, "voltage_v": 220})
    assert isinstance(out, dict)
    json.dumps(out)
    assert out["status"] in {"ok", "no_match"}
    assert out["filters"]["min_torque"] == 100
    assert out["filters"]["voltage_v"] == 220
    exp = ref_matches(SearchFilters(min_torque=100, voltage_v=220))
    assert out["total"] == len(exp)


def test_search_tool_no_args_allowed(lc_tools):
    by_name, _ = lc_tools
    out = by_name["search_actuators"].invoke({})
    assert out["total"] == 68


@pytest.mark.parametrize(
    "bad",
    [
        {"voltage_v": 48},
        {"min_torque": -5},
        {"min_torque": 0},
        {"phase": 2},
        {"enclosure": "waterproof"},
        {"service": "both"},
        {"torque_unit": "ft_lbs"},
        {"speed_hz": 55},
        {"min_duty_cycle_pct": 101},
        {"min_torque": "lots"},
    ],
)
def test_search_tool_rejects_invalid_args(lc_tools, bad):
    by_name, _ = lc_tools
    with pytest.raises(ValidationError):
        by_name["search_actuators"].invoke(bad)


def test_search_tool_args_schema_is_search_filters(lc_tools):
    by_name, _ = lc_tools
    assert by_name["search_actuators"].args_schema is SearchFilters


def test_describe_tool(lc_tools):
    by_name, _ = lc_tools
    out = by_name["describe_catalog"].invoke({})
    json.dumps(out)
    assert out["total_rows"] == 68
    assert out["rows_without_data"] == 4


def test_tools_open_and_close_connection_via_context_manager(db):
    events: list[str] = []

    class Ctx:
        def __enter__(self):
            events.append("enter")
            return db

        def __exit__(self, *a):
            events.append("exit")
            return False

    ts = {t.name: t for t in tools.make_tools(lambda: Ctx())}
    ts["describe_catalog"].invoke({})
    ts["get_actuator"].invoke({"part_number": "764A00-11300000/A"})
    ts["search_actuators"].invoke({"voltage_v": 24})
    assert events == ["enter", "exit"] * 3


def test_db_errors_propagate(db):
    class Boom:
        def __enter__(self):
            raise RuntimeError("db down")

        def __exit__(self, *a):
            return False

    ts = {t.name: t for t in tools.make_tools(lambda: Boom())}
    with pytest.raises(Exception, match="db down"):
        ts["describe_catalog"].invoke({})
