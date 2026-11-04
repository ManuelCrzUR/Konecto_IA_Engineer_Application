# ruff: noqa: C408
"""Black-box contract tests for app.db.actuators_repo.

Written from the documented contract only (function docstrings, SearchFilters
docstring, schema.sql and data/processed/actuators.json). Expected answers come
from an independent Python "oracle" that applies the documented SearchFilters
semantics to the JSON rows; the repository (SQL) must agree with it.

Needs the `pg` fixture (a reachable Postgres, see conftest.py).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.db import actuators_repo
from app.domain.models import Actuator, Catalog
from app.domain.search import SearchFilters

CATALOG_PATH = Path(__file__).resolve().parent.parent / "data" / "processed" / "actuators.json"
CATALOG = Catalog.model_validate_json(CATALOG_PATH.read_text())
ROWS: list[Actuator] = CATALOG.rows
BY_PN = {r.part_number: r for r in ROWS}
BIG = 1000  # limit large enough to fetch every row

NUMERIC_FILTERS = ("min_torque", "max_speed_sec", "min_duty_cycle_pct")


# --------------------------------------------------------------------------- oracle
def _first(*values: float | None) -> float | None:
    """COALESCE."""
    return next((v for v in values if v is not None), None)


def _service_ok(row: Actuator, service: str | None) -> bool:
    if service is None:
        return True
    if service == "on_off":
        return row.service in ("on_off", "on_off_and_modulating", "unspecified")
    return row.service in ("modulating", "on_off_and_modulating", "unspecified")


def _family_values(
    row: Actuator, service: str | None, unit: str
) -> list[tuple[float | None, float | None]]:
    """(torque, duty) pairs per operating family selected by `service`.

    service set: one pair, COALESCE(family, output). service None: three pairs
    (on/off, modulating, output); a constraint must hold within ONE pair."""
    ot, mt, pt = (getattr(row, f"{p}_torque_{unit}") for p in ("onoff", "mod", "output"))
    od, md, pd = row.onoff_duty_cycle_pct, row.mod_duty_cycle_pct, row.duty_cycle_pct
    if service == "on_off":
        return [(_first(ot, pt), _first(od, pd))]
    if service == "modulating":
        return [(_first(mt, pt), _first(md, pd))]
    return [(ot, od), (mt, md), (pt, pd)]


def _qualifying_pairs(row: Actuator, f: SearchFilters) -> list[tuple[float | None, float | None]]:
    """Pairs that meet every SET family constraint (torque and duty together)."""
    unit = "nm" if f.torque_unit == "nm" else "in_lbs"
    out = []
    for t, d in _family_values(row, f.service, unit):
        if f.min_torque is not None and (t is None or t < f.min_torque):
            continue
        if f.min_duty_cycle_pct is not None and (d is None or d < f.min_duty_cycle_pct):
            continue
        out.append((t, d))
    return out


def torque_candidates(row: Actuator, f: SearchFilters) -> list[float]:
    unit = "nm" if f.torque_unit == "nm" else "in_lbs"
    return [t for t, _ in _family_values(row, f.service, unit) if t is not None]


def qualifying_torque(row: Actuator, f: SearchFilters) -> float:
    """Smallest torque among the families that satisfy ALL family constraints."""
    assert f.min_torque is not None
    return min(t for t, _ in _qualifying_pairs(row, f) if t is not None)


def oracle_rows(f: SearchFilters) -> list[Actuator]:
    """Rows with data meeting every filter, per the SearchFilters docstring."""
    out = []
    for r in ROWS:
        if not r.has_data:
            continue
        if f.voltage_v is not None:
            ok = (
                r.voltage.startswith("24V") if f.voltage_v == 24 else r.voltage == f"{f.voltage_v}V"
            )
            if not ok:
                continue
        if f.phase is not None and r.phase != f.phase:
            continue
        if f.enclosure is not None and r.enclosure != f.enclosure:
            continue
        if not _service_ok(r, f.service):
            continue
        if (f.min_torque is not None or f.min_duty_cycle_pct is not None) and not _qualifying_pairs(
            r, f
        ):
            continue
        if f.max_speed_sec is not None:
            hz = getattr(r, f"speed_sec_{f.speed_hz}hz")
            speed = _first(hz, r.speed_sec)
            if speed is None or speed > f.max_speed_sec:
                continue
        out.append(r)
    return out


def has_numeric_filter(f: SearchFilters) -> bool:
    return any(getattr(f, name) is not None for name in NUMERIC_FILTERS)


def n_a_rows_matching_non_numeric(f: SearchFilters) -> int:
    """N/A rows that pass the non-numeric filters (ambiguous whether they are returned)."""
    loose = f.model_copy(update={n: None for n in NUMERIC_FILTERS})
    count = 0
    for r in ROWS:
        if r.has_data:
            continue
        if loose.voltage_v is not None and r.voltage != f"{loose.voltage_v}V":
            continue
        if loose.phase is not None and r.phase != loose.phase:
            continue
        if loose.enclosure is not None and r.enclosure != loose.enclosure:
            continue
        if not _service_ok(r, loose.service):
            continue
        count += 1
    return count


def max_torque(rows: list[Actuator], f: SearchFilters) -> float:
    return max(v for r in rows for v in torque_candidates(r, f))


# --------------------------------------------------------------------------- fixtures
@pytest.fixture
def seeded(pg):
    actuators_repo.upsert_catalog(pg, CATALOG)
    return pg


def _pns(rows: list[Actuator]) -> set[str]:
    return {r.part_number for r in rows}


# --------------------------------------------------------------------------- filter cases
FILTER_CASES = {
    "torque_nm": dict(min_torque=200),
    "torque_in_lbs": dict(min_torque=2000, torque_unit="in_lbs"),
    "torque_nm_small": dict(min_torque=1),
    "voltage_24": dict(voltage_v=24, min_torque=1),
    "voltage_110": dict(voltage_v=110, min_torque=1),
    "voltage_220": dict(voltage_v=220, min_torque=1),
    "phase_1_torque": dict(phase=1, min_torque=100),
    "phase_3_torque": dict(phase=3, min_torque=1),
    "enclosure_wp": dict(enclosure="weatherproof", min_torque=100),
    "enclosure_xp": dict(enclosure="explosionproof", min_torque=100),
    "service_on_off": dict(service="on_off", min_torque=100),
    "service_modulating": dict(service="modulating", min_torque=100),
    "service_modulating_in_lbs": dict(service="modulating", min_torque=1000, torque_unit="in_lbs"),
    "speed_60": dict(max_speed_sec=30),
    "speed_50_220v": dict(max_speed_sec=30, speed_hz=50, voltage_v=220),
    "speed_24v": dict(max_speed_sec=40, voltage_v=24),
    "duty": dict(min_duty_cycle_pct=50),
    "torque_and_duty_no_service": dict(min_torque=50, min_duty_cycle_pct=50),
    "torque_and_duty_high": dict(min_torque=100, min_duty_cycle_pct=70),
    "torque_and_duty_in_lbs": dict(min_torque=1000, min_duty_cycle_pct=40, torque_unit="in_lbs"),
    "torque_and_duty_modulating": dict(min_torque=50, min_duty_cycle_pct=50, service="modulating"),
    "duty_service_modulating": dict(min_duty_cycle_pct=50, service="modulating"),
    "combo_110_wp_on_off": dict(
        voltage_v=110, enclosure="weatherproof", service="on_off", min_torque=50, max_speed_sec=40
    ),
    "combo_220_1ph_xp_nm_duty": dict(
        voltage_v=220, phase=1, enclosure="explosionproof", min_torque=100, min_duty_cycle_pct=30
    ),
    "combo_3ph_speed_duty": dict(phase=3, max_speed_sec=60, min_duty_cycle_pct=10, min_torque=1),
    "impossible_torque": dict(min_torque=1_000_000),
    "impossible_24v_wp": dict(voltage_v=24, enclosure="weatherproof", min_torque=1),
    "impossible_24v_phase1": dict(voltage_v=24, phase=1, min_torque=1),
    "impossible_3ph_xp": dict(phase=3, enclosure="explosionproof", min_torque=1),
    "impossible_speed": dict(max_speed_sec=0.1),
    "impossible_24v_on_off_modulating_duty": dict(
        voltage_v=24, min_duty_cycle_pct=100, min_torque=1_000
    ),
}


def test_oracle_sanity():
    """Guard the oracle itself: it must find something for the plain cases."""
    assert len(ROWS) == 68
    assert oracle_rows(SearchFilters(min_torque=1)), "oracle returns nothing for trivial filter"
    assert oracle_rows(SearchFilters(min_torque=1_000_000)) == []


@pytest.mark.parametrize("kwargs", FILTER_CASES.values(), ids=FILTER_CASES.keys())
def test_search_matches_oracle(seeded, kwargs):
    f = SearchFilters(**kwargs)
    expected = _pns(oracle_rows(f))

    results = actuators_repo.search(seeded, f, limit=BIG)
    if has_numeric_filter(f):
        got = _pns(results)
        assert got == expected
        assert all(r.has_data for r in results)
        assert actuators_repo.count_matches(seeded, f) == len(expected)
    else:
        # Whether N/A rows appear for purely non-numeric filters is not specified;
        # only the rows with data are compared.
        assert {r.part_number for r in results if r.has_data} == expected
        total = actuators_repo.count_matches(seeded, f)
        assert len(expected) <= total <= len(expected) + n_a_rows_matching_non_numeric(f)
    assert len(results) == len({r.part_number for r in results}), "duplicate rows returned"


@pytest.mark.parametrize("kwargs", FILTER_CASES.values(), ids=FILTER_CASES.keys())
def test_search_returns_stored_values_untouched(seeded, kwargs):
    f = SearchFilters(**kwargs)
    for r in actuators_repo.search(seeded, f, limit=BIG):
        assert r.model_dump() == BY_PN[r.part_number].model_dump()


def test_torque_units_are_not_converted(seeded):
    """The unit only selects the printed column: 100 nm and 100 in-lbs differ."""
    nm = actuators_repo.count_matches(seeded, SearchFilters(min_torque=300, torque_unit="nm"))
    lbs = actuators_repo.count_matches(seeded, SearchFilters(min_torque=300, torque_unit="in_lbs"))
    assert nm == len(oracle_rows(SearchFilters(min_torque=300, torque_unit="nm")))
    assert lbs == len(oracle_rows(SearchFilters(min_torque=300, torque_unit="in_lbs")))
    assert lbs > nm  # in-lbs figures are ~8.85x larger than Nm for the same actuator


# --------------------------------------------------------------------------- ordering / limit
ORDER_CASES = {
    "on_off_nm": dict(service="on_off", min_torque=100),
    "modulating_nm": dict(service="modulating", min_torque=50),
    "on_off_in_lbs": dict(service="on_off", min_torque=500, torque_unit="in_lbs"),
    "three_phase": dict(phase=3, min_torque=1),
    "torque_only": dict(min_torque=200),
    "torque_and_duty": dict(min_torque=50, min_duty_cycle_pct=50),
}


@pytest.mark.parametrize("kwargs", ORDER_CASES.values(), ids=ORDER_CASES.keys())
def test_tightest_fit_first(seeded, kwargs):
    f = SearchFilters(**kwargs)
    results = actuators_repo.search(seeded, f, limit=BIG)
    quals = [qualifying_torque(r, f) for r in results]
    assert quals, "case should have matches"
    assert quals[0] == min(quals)
    assert quals == sorted(quals), "results must be ordered by ascending qualifying torque"


@pytest.mark.parametrize("kwargs", ORDER_CASES.values(), ids=ORDER_CASES.keys())
def test_limit_returns_the_tightest_prefix(seeded, kwargs):
    f = SearchFilters(**kwargs)
    expected_quals = sorted(qualifying_torque(r, f) for r in oracle_rows(f))
    top = actuators_repo.search(seeded, f, limit=3)
    assert [qualifying_torque(r, f) for r in top] == expected_quals[:3]


def test_limit_respected_and_count_is_total(seeded):
    f = SearchFilters(min_torque=1)
    total = len(oracle_rows(f))
    assert total > 10
    assert len(actuators_repo.search(seeded, f, limit=5)) == 5
    assert len(actuators_repo.search(seeded, f, limit=1)) == 1
    assert len(actuators_repo.search(seeded, f)) == 10  # documented default limit
    assert len(actuators_repo.search(seeded, f, limit=BIG)) == total
    assert actuators_repo.count_matches(seeded, f) == total
    limited = _pns(actuators_repo.search(seeded, f, limit=5))
    assert limited <= _pns(oracle_rows(f))


def test_search_without_matches_is_empty_list(seeded):
    assert actuators_repo.search(seeded, SearchFilters(min_torque=1_000_000)) == []
    assert actuators_repo.count_matches(seeded, SearchFilters(min_torque=1_000_000)) == 0


# --------------------------------------------------------------------------- N/A rows
NA_PNS = [r.part_number for r in ROWS if not r.has_data]


def test_fixture_data_has_four_na_rows():
    assert len(NA_PNS) == 4
    assert {pn[:4] for pn in NA_PNS} == {"761A", "761B", "762A", "762B"}


@pytest.mark.parametrize("pn", NA_PNS)
def test_get_by_pn_returns_na_rows_without_data(seeded, pn):
    row = actuators_repo.get_by_pn(seeded, pn)
    assert row is not None
    assert row.part_number == pn
    assert row.has_data is False
    assert row.output_torque_nm is None and row.output_torque_in_lbs is None
    assert row.duty_cycle_pct is None


@pytest.mark.parametrize("kwargs", FILTER_CASES.values(), ids=FILTER_CASES.keys())
def test_na_rows_never_match_numeric_filters(seeded, kwargs):
    f = SearchFilters(**kwargs)
    if not has_numeric_filter(f):
        pytest.skip("only numeric filters are specified to exclude N/A rows")
    assert not _pns(actuators_repo.search(seeded, f, limit=BIG)) & set(NA_PNS)


def test_three_phase_filter_yields_only_the_seven_rows_with_data(seeded):
    got = actuators_repo.search(seeded, SearchFilters(phase=3, min_torque=0.1), limit=BIG)
    assert len(got) == 7
    assert not _pns(got) & set(NA_PNS)


def test_get_by_pn_round_trips_every_row(seeded):
    for r in ROWS:
        got = actuators_repo.get_by_pn(seeded, r.part_number)
        assert got is not None
        assert got.model_dump() == r.model_dump()


def test_get_by_pn_non_csa_flag_and_24v_nulls(seeded):
    non_csa = [r for r in ROWS if not r.csa_certified]
    assert len(non_csa) == 5
    for r in non_csa:
        got = actuators_repo.get_by_pn(seeded, r.part_number)
        assert got is not None and got.csa_certified is False
    t4 = next(r for r in ROWS if r.table_id == "T4_xp_24v_onoff")
    got = actuators_repo.get_by_pn(seeded, t4.part_number)
    assert got.phase is None
    assert got.speed_sec == t4.speed_sec and got.fla_a == t4.fla_a and got.lra_a == t4.lra_a
    assert got.speed_sec_60hz is None


def test_get_by_pn_is_exact_match_only(seeded):
    assert actuators_repo.get_by_pn(seeded, "DOES-NOT-EXIST") is None
    assert actuators_repo.get_by_pn(seeded, "764") is None  # prefix is not enough
    assert actuators_repo.get_by_pn(seeded, "") is None


# --------------------------------------------------------------------------- upsert / delete
def test_upsert_returns_rows_written_and_count(pg):
    assert actuators_repo.count(pg) == 0
    assert actuators_repo.upsert_catalog(pg, CATALOG) == 68
    assert actuators_repo.count(pg) == 68


def test_upsert_is_idempotent(pg):
    actuators_repo.upsert_catalog(pg, CATALOG)
    snapshot = {
        r.part_number: r.model_dump()
        for r in actuators_repo.search(pg, SearchFilters(min_torque=0.1), BIG)
    }
    actuators_repo.upsert_catalog(pg, CATALOG)
    assert actuators_repo.count(pg) == 68
    again = {
        r.part_number: r.model_dump()
        for r in actuators_repo.search(pg, SearchFilters(min_torque=0.1), BIG)
    }
    assert again == snapshot
    for r in ROWS:
        assert actuators_repo.get_by_pn(pg, r.part_number).model_dump() == r.model_dump()


def test_upsert_updates_changed_values_in_place(pg):
    actuators_repo.upsert_catalog(pg, CATALOG)
    target = next(r for r in ROWS if r.has_data and r.onoff_torque_nm is not None)
    changed = target.model_copy(update={"onoff_torque_nm": 12345.0})
    rows = [changed if r.part_number == target.part_number else r for r in ROWS]
    actuators_repo.upsert_catalog(pg, Catalog(tables=CATALOG.tables, rows=rows))
    assert actuators_repo.count(pg) == 68
    assert actuators_repo.get_by_pn(pg, target.part_number).onoff_torque_nm == 12345.0


def _invalid_last_catalog(first_value: float | None = None) -> Catalog:
    rows = list(ROWS)
    if first_value is not None:
        rows[0] = rows[0].model_copy(update={"onoff_torque_nm": first_value})
    # Violates CHECK (duty BETWEEN 0 AND 100); model_copy/construct skip pydantic validation.
    rows[-1] = Actuator.model_construct(**{**rows[-1].model_dump(), "onoff_duty_cycle_pct": 150.0})
    return Catalog.model_construct(tables=CATALOG.tables, rows=rows)


def test_upsert_is_transactional_on_empty_db(pg):
    with pytest.raises(Exception):  # noqa: B017 - exact exception type is not in the contract
        actuators_repo.upsert_catalog(pg, _invalid_last_catalog())
    assert actuators_repo.count(pg) == 0
    n_tables = pg.execute("SELECT count(*) FROM catalog_tables").fetchone()[0]
    assert n_tables == 0
    # Connection must remain usable after the failure.
    assert actuators_repo.upsert_catalog(pg, CATALOG) == 68


def test_upsert_is_transactional_on_populated_db(pg):
    actuators_repo.upsert_catalog(pg, CATALOG)
    before = {
        r.part_number: r.model_dump()
        for r in actuators_repo.search(pg, SearchFilters(min_torque=0.1), BIG)
    }
    with pytest.raises(Exception):  # noqa: B017
        actuators_repo.upsert_catalog(pg, _invalid_last_catalog(first_value=99999.0))
    assert actuators_repo.count(pg) == 68
    after = {
        r.part_number: r.model_dump()
        for r in actuators_repo.search(pg, SearchFilters(min_torque=0.1), BIG)
    }
    assert after == before
    assert (
        actuators_repo.get_by_pn(pg, ROWS[0].part_number).onoff_torque_nm == ROWS[0].onoff_torque_nm
    )


def test_delete_all(seeded):
    assert actuators_repo.count(seeded) == 68
    actuators_repo.delete_all(seeded)
    assert actuators_repo.count(seeded) == 0
    assert seeded.execute("SELECT count(*) FROM catalog_tables").fetchone()[0] == 0
    assert actuators_repo.get_by_pn(seeded, ROWS[0].part_number) is None
    # delete_all on an empty DB is harmless, and the catalog can be reloaded.
    actuators_repo.delete_all(seeded)
    assert actuators_repo.upsert_catalog(seeded, CATALOG) == 68


def test_count_on_empty_db(pg):
    assert actuators_repo.count(pg) == 0


# --------------------------------------------------------------------------- diagnose_no_match
def test_diagnose_torque_above_catalog_max(seeded):
    base = SearchFilters(min_torque=1)
    top = max_torque(oracle_rows(base), base)
    f = SearchFilters(min_torque=top + 1000)
    assert actuators_repo.search(seeded, f) == []
    report = actuators_repo.diagnose_no_match(seeded, f)
    assert "min_torque" in report.blocking
    assert report.out_of_catalog is False
    assert report.closest["min_torque"] == top
    assert report.message


def test_diagnose_torque_in_lbs_closest_uses_printed_in_lbs(seeded):
    base = SearchFilters(min_torque=1, torque_unit="in_lbs")
    top = max_torque(oracle_rows(base), base)
    f = SearchFilters(min_torque=top + 1000, torque_unit="in_lbs")
    report = actuators_repo.diagnose_no_match(seeded, f)
    assert "min_torque" in report.blocking
    assert report.closest["min_torque"] == top


def test_diagnose_closest_respects_other_filters(seeded):
    """Closest value is computed among rows satisfying all *other* filters."""
    others = SearchFilters(
        voltage_v=110, enclosure="explosionproof", service="on_off", min_torque=1
    )
    top = max_torque(oracle_rows(others), others)
    f = others.model_copy(update={"min_torque": top + 500})
    report = actuators_repo.diagnose_no_match(seeded, f)
    assert report.blocking == ["min_torque"]
    assert report.closest["min_torque"] == top
    assert report.out_of_catalog is False


def test_diagnose_speed_closest_is_fastest_available(seeded):
    base = SearchFilters(voltage_v=110, max_speed_sec=1000)
    fastest = min(_first(r.speed_sec_60hz, r.speed_sec) for r in oracle_rows(base))
    f = SearchFilters(voltage_v=110, max_speed_sec=fastest / 2)
    assert actuators_repo.search(seeded, f) == []
    report = actuators_repo.diagnose_no_match(seeded, f)
    assert "max_speed_sec" in report.blocking
    assert report.closest["max_speed_sec"] == fastest


def test_diagnose_duty_closest_is_highest_available(seeded):
    base = SearchFilters(voltage_v=110, service="on_off", min_duty_cycle_pct=0)
    best = max(
        _first(r.onoff_duty_cycle_pct, r.duty_cycle_pct)
        for r in oracle_rows(base)
        if _first(r.onoff_duty_cycle_pct, r.duty_cycle_pct) is not None
    )
    if best >= 100:
        pytest.skip("no duty headroom above the catalog maximum")
    f = SearchFilters(voltage_v=110, service="on_off", min_duty_cycle_pct=100)
    assert actuators_repo.search(seeded, f) == []
    report = actuators_repo.diagnose_no_match(seeded, f)
    assert "min_duty_cycle_pct" in report.blocking
    assert report.closest["min_duty_cycle_pct"] == best


@pytest.mark.parametrize(
    "kwargs",
    [
        dict(voltage_v=24, enclosure="weatherproof"),
        dict(voltage_v=24, enclosure="weatherproof", min_torque=10),
        dict(phase=3, enclosure="explosionproof"),
        dict(phase=3, enclosure="explosionproof", min_torque=10),
    ],
    ids=["24v_wp", "24v_wp_torque", "3ph_xp", "3ph_xp_torque"],
)
def test_diagnose_out_of_catalog(seeded, kwargs):
    f = SearchFilters(**kwargs)
    assert actuators_repo.search(seeded, f) == []
    report = actuators_repo.diagnose_no_match(seeded, f)
    assert report.out_of_catalog is True
    assert report.message


def test_diagnose_in_catalog_combination_is_not_out_of_catalog(seeded):
    f = SearchFilters(voltage_v=24, enclosure="explosionproof", min_torque=1_000_000)
    report = actuators_repo.diagnose_no_match(seeded, f)
    assert report.out_of_catalog is False
    assert "min_torque" in report.blocking


# --------------------------------------------------------------------------- find_like
def test_find_like_prefix(seeded):
    expected = sorted(r.part_number for r in ROWS if r.part_number.startswith("764"))
    assert expected
    got = actuators_repo.find_like(seeded, "764")
    assert [r.part_number for r in got] == expected
    assert all(isinstance(r, Actuator) for r in got)


def test_find_like_longer_fragment(seeded):
    pn = ROWS[0].part_number
    got = actuators_repo.find_like(seeded, pn[:6])
    expected = {r.part_number for r in ROWS if r.part_number.startswith(pn[:6])}
    assert _pns(got) == expected
    assert pn in _pns(got)


def test_find_like_is_prefix_not_substring(seeded):
    assert actuators_repo.find_like(seeded, "11300000") == []
    assert actuators_repo.find_like(seeded, "NOPE") == []


def test_find_like_limit_and_default(seeded):
    all_76 = {r.part_number for r in ROWS if r.part_number.startswith("76")}
    assert len(all_76) > 10
    assert len(actuators_repo.find_like(seeded, "76")) == 10  # documented default
    assert len(actuators_repo.find_like(seeded, "76", limit=3)) == 3
    assert _pns(actuators_repo.find_like(seeded, "76", limit=BIG)) == all_76


def test_find_like_ordered_by_part_number(seeded):
    got = [r.part_number for r in actuators_repo.find_like(seeded, "76", limit=BIG)]
    assert len(got) == len(set(got))
    # first 3 of a limited call equal the head of the full ordered call
    assert [r.part_number for r in actuators_repo.find_like(seeded, "76", limit=3)] == got[:3]


@pytest.mark.parametrize("fragment", ["%", "_", "7_4", "76%"])
def test_find_like_treats_wildcards_literally(seeded, fragment):
    """Assumption: '%' and '_' are literal characters, not LIKE wildcards."""
    assert actuators_repo.find_like(seeded, fragment) == []


# --------------------------------------------------------------------------- table_notes / summary
def test_table_notes_returns_lists_for_requested_ids(seeded):
    ids = ["T1_wp_110v_1ph", "T4_xp_24v_onoff"]
    notes = actuators_repo.table_notes(seeded, ids)
    assert set(notes) == set(ids)
    for t in CATALOG.tables:
        if t.table_id in ids:
            assert isinstance(notes[t.table_id], list)
            assert notes[t.table_id] == t.notes
            assert notes[t.table_id], "fixture tables carry notes"


def test_table_notes_only_requested_ids(seeded):
    notes = actuators_repo.table_notes(seeded, ["T3_wp_220v_3ph"])
    assert set(notes) == {"T3_wp_220v_3ph"}


def test_catalog_summary(seeded):
    s = actuators_repo.catalog_summary(seeded)
    assert s.total_rows == 68
    assert s.rows_without_data == 4
    assert sum(int(c["rows"]) for c in s.combinations) == 68
    assert len(s.combinations) == 7  # one per source table (assumption)
    nm = [
        v
        for r in ROWS
        for v in (r.onoff_torque_nm, r.mod_torque_nm, r.output_torque_nm)
        if v is not None
    ]
    lbs = [
        v
        for r in ROWS
        for v in (r.onoff_torque_in_lbs, r.mod_torque_in_lbs, r.output_torque_in_lbs)
        if v is not None
    ]
    assert s.torque_nm_range == (min(nm), max(nm))
    assert s.torque_in_lbs_range == (min(lbs), max(lbs))


def test_catalog_summary_empty_db(pg):
    s = actuators_repo.catalog_summary(pg)
    assert s.total_rows == 0
    assert s.combinations == []


# --------------------------------------------------------------------------- one-family rule
def _synthetic(pn: str, **cols: float | None) -> Actuator:
    base = BY_PN[next(r.part_number for r in ROWS if r.has_data and r.voltage == "110V")]
    data = {k: None for k in Actuator.model_fields if k.startswith(("onoff_", "mod_", "output_"))}
    data.update(base.model_dump())
    for k in list(data):
        if k.startswith(("onoff_", "mod_", "output_")) or k == "duty_cycle_pct":
            data[k] = None
    data.update(part_number=pn, **cols)
    return Actuator.model_construct(**data)


def test_torque_and_duty_must_come_from_the_same_family(pg):
    """Regression: on/off meets torque only, modulating meets duty only -> no match."""
    split = _synthetic(
        "769A00-11300000/A",
        onoff_torque_nm=500.0,
        onoff_torque_in_lbs=4425.0,
        onoff_duty_cycle_pct=10.0,
        mod_torque_nm=50.0,
        mod_torque_in_lbs=442.0,
        mod_duty_cycle_pct=90.0,
    )
    same = _synthetic(
        "769B00-11300000/A",
        onoff_torque_nm=500.0,
        onoff_torque_in_lbs=4425.0,
        onoff_duty_cycle_pct=80.0,
        mod_torque_nm=50.0,
        mod_torque_in_lbs=442.0,
        mod_duty_cycle_pct=90.0,
    )
    tables = [t for t in CATALOG.tables if t.table_id == split.table_id]
    actuators_repo.upsert_catalog(pg, Catalog.model_construct(tables=tables, rows=[split, same]))
    f = SearchFilters(min_torque=400, min_duty_cycle_pct=70)
    got = [r.part_number for r in actuators_repo.search(pg, f, limit=BIG)]
    assert got == ["769B00-11300000/A"]
    assert actuators_repo.count_matches(pg, f) == 1
    # Either constraint alone still matches both rows.
    assert actuators_repo.count_matches(pg, SearchFilters(min_torque=400)) == 2
    assert actuators_repo.count_matches(pg, SearchFilters(min_duty_cycle_pct=70)) == 2
    # With service set, the chosen family alone decides.
    on = SearchFilters(min_torque=400, min_duty_cycle_pct=70, service="on_off")
    assert [r.part_number for r in actuators_repo.search(pg, on)] == ["769B00-11300000/A"]
    mod = SearchFilters(min_torque=40, min_duty_cycle_pct=70, service="modulating")
    assert {r.part_number for r in actuators_repo.search(pg, mod)} == {
        "769A00-11300000/A",
        "769B00-11300000/A",
    }
    # Closest torque honours the duty requirement within the same family.
    rep = actuators_repo.diagnose_no_match(pg, SearchFilters(min_torque=600, min_duty_cycle_pct=70))
    assert rep.closest["min_torque"] == 500.0  # 769B00-11300000/A on/off (duty 80 >= 70)
    rep = actuators_repo.diagnose_no_match(pg, SearchFilters(min_torque=400, min_duty_cycle_pct=95))
    assert rep.closest["min_duty_cycle_pct"] == 80.0  # on/off families with torque >= 400
