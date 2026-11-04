"""Integration tests for db/actuators_repo.py against the real catalog (needs Postgres).

Expected values are derived from data/processed/actuators.json with plain Python,
independently of the SQL under test.
"""

from __future__ import annotations

import pytest

from app.db import actuators_repo as repo
from app.domain.models import Actuator, Catalog
from app.domain.search import SearchFilters
from tests.conftest import PROCESSED_JSON

CATALOG = Catalog.model_validate_json(PROCESSED_JSON.read_text())
ROWS = CATALOG.rows


@pytest.fixture
def db(pg):
    repo.upsert_catalog(pg, CATALOG)
    return pg


def pns(actuators: list[Actuator]) -> list[str]:
    return [a.part_number for a in actuators]


def run(conn, **kw) -> list[str]:
    return pns(repo.search(conn, SearchFilters(**kw), limit=1000))


def torque_of(r: Actuator, service: str | None, unit: str = "nm") -> float | None:
    """Reference rule: family column for the service, else output_*."""
    on, mod, out = (getattr(r, f"{p}_torque_{unit}") for p in ("onoff", "mod", "output"))
    if service == "on_off":
        return on if on is not None else out
    if service == "modulating":
        return mod if mod is not None else out
    vals = [v for v in (on, mod, out) if v is not None]
    return max(vals) if vals else None


def families(r: Actuator, unit: str = "nm") -> list[tuple[float | None, float | None]]:
    """(torque, duty) per operating family: on/off, modulating, output."""
    t = [getattr(r, f"{p}_torque_{unit}") for p in ("onoff", "mod", "output")]
    d = [r.onoff_duty_cycle_pct, r.mod_duty_cycle_pct, r.duty_cycle_pct]
    return list(zip(t, d, strict=True))


def meets_one_family(r: Actuator, torque: float, duty: float, unit: str = "nm") -> bool:
    return any(
        t is not None and d is not None and t >= torque and d >= duty for t, d in families(r, unit)
    )


def test_upsert_is_idempotent(pg):
    assert repo.upsert_catalog(pg, CATALOG) == len(ROWS) == 68
    assert repo.upsert_catalog(pg, CATALOG) == 68
    assert repo.count(pg) == 68
    assert repo.table_notes(pg, ["T1_wp_110v_1ph"])  # tables not duplicated either


def test_upsert_updates_changed_row(db):
    changed = CATALOG.model_copy(deep=True)
    changed.rows[0].onoff_torque_nm = 12345.0
    repo.upsert_catalog(db, changed)
    assert repo.count(db) == 68
    got = repo.get_by_pn(db, changed.rows[0].part_number)
    assert got is not None and got.onoff_torque_nm == 12345.0


def test_delete_all(db):
    repo.delete_all(db)
    assert repo.count(db) == 0
    assert repo.table_notes(db, [t.table_id for t in CATALOG.tables]) == {}


def test_get_by_pn_exact_roundtrip_and_missing(db):
    for row in (
        ROWS[0],
        next(r for r in ROWS if not r.has_data),
        next(r for r in ROWS if not r.csa_certified),
    ):
        assert repo.get_by_pn(db, row.part_number) == row
    assert repo.get_by_pn(db, "999Z99-00000000/A") is None
    assert repo.get_by_pn(db, "764") is None  # exact only


def test_find_like_prefix_ordered_and_limited(db):
    expected = sorted(r.part_number for r in ROWS if r.part_number.startswith("764"))
    assert len(expected) > 1
    assert pns(repo.find_like(db, "764", limit=100)) == expected
    assert pns(repo.find_like(db, "764", limit=2)) == expected[:2]
    assert repo.find_like(db, "%") == []  # wildcard characters are literal
    assert repo.find_like(db, "ZZZ") == []


@pytest.mark.parametrize(
    ("kw", "pred"),
    [
        ({"voltage_v": 24}, lambda r: r.voltage.startswith("24V")),
        ({"voltage_v": 110}, lambda r: r.voltage == "110V"),
        ({"voltage_v": 220}, lambda r: r.voltage == "220V"),
        ({"phase": 3}, lambda r: r.phase == 3),
        ({"phase": 1}, lambda r: r.phase == 1),
        ({"enclosure": "explosionproof"}, lambda r: r.enclosure == "explosionproof"),
        ({"enclosure": "weatherproof"}, lambda r: r.enclosure == "weatherproof"),
        (
            {"service": "on_off"},
            lambda r: r.service in ("on_off", "on_off_and_modulating", "unspecified"),
        ),
        (
            {"service": "modulating"},
            lambda r: r.service in ("modulating", "on_off_and_modulating", "unspecified"),
        ),
    ],
)
def test_non_numeric_filter_alone(db, kw, pred):
    assert sorted(run(db, **kw)) == sorted(r.part_number for r in ROWS if pred(r))
    assert repo.count_matches(db, SearchFilters(**kw)) == len([r for r in ROWS if pred(r)])


def test_no_filters_returns_everything_and_limit_applies(db):
    assert repo.count_matches(db, SearchFilters()) == 68
    assert len(repo.search(db, SearchFilters(), limit=5)) == 5


@pytest.mark.parametrize("service", [None, "on_off", "modulating"])
@pytest.mark.parametrize("unit", ["nm", "in_lbs"])
def test_min_torque_families_and_units(db, service, unit):
    values = sorted({v for r in ROWS if (v := torque_of(r, service, unit)) is not None})
    threshold = values[len(values) // 2]
    expected = {
        r.part_number
        for r in ROWS
        if (v := torque_of(r, service, unit)) is not None and v >= threshold
    }
    got = run(db, min_torque=threshold, torque_unit=unit, service=service)
    assert set(got) == expected and expected


def test_nm_and_in_lbs_use_different_columns(db):
    r = ROWS[0]  # onoff 80 Nm / 700 in-lbs
    assert r.onoff_torque_nm is not None and r.onoff_torque_in_lbs is not None
    nm_hit = run(db, min_torque=r.onoff_torque_nm, torque_unit="nm", service="on_off")
    lbs_hit = run(db, min_torque=r.onoff_torque_nm, torque_unit="in_lbs", service="on_off")
    assert r.part_number in nm_hit
    assert len(lbs_hit) > len(nm_hit)  # same number against the larger in-lbs scale


def test_three_phase_uses_output_columns(db):
    r = next(r for r in ROWS if r.phase == 3 and r.has_data)
    assert r.onoff_torque_nm is None and r.output_torque_nm is not None
    for service in ("on_off", "modulating", None):
        got = run(db, min_torque=r.output_torque_nm, service=service, phase=3)
        assert r.part_number in got


def test_tightest_fit_order(db):
    threshold = sorted({r.onoff_torque_nm for r in ROWS if r.onoff_torque_nm})[3]
    f = SearchFilters(
        min_torque=threshold, service="on_off", voltage_v=110, enclosure="weatherproof"
    )
    got = repo.search(db, f, limit=100)
    keys = [(torque_of(a, "on_off"), a.speed_sec_60hz, a.part_number) for a in got]
    assert keys == sorted(keys)
    assert keys[0][0] is not None and keys[0][0] >= threshold
    assert len(got) > 1 and set(pns(got)) == {
        r.part_number
        for r in ROWS
        if r.voltage == "110V"
        and r.enclosure == "weatherproof"
        and r.service in ("on_off", "on_off_and_modulating", "unspecified")
        and (torque_of(r, "on_off") or 0) >= threshold
    }


def test_speed_filter_60_50_and_24v_fallback(db):
    t = 20.0
    for hz, col in ((60, "speed_sec_60hz"), (50, "speed_sec_50hz")):
        expected = {
            r.part_number
            for r in ROWS
            if (getattr(r, col) if getattr(r, col) is not None else r.speed_sec) is not None
            and (getattr(r, col) if getattr(r, col) is not None else r.speed_sec) <= t
        }
        assert set(run(db, max_speed_sec=t, speed_hz=hz)) == expected
    v24 = [r for r in ROWS if r.voltage.startswith("24V") and r.speed_sec is not None]
    assert v24 and all(r.speed_sec_60hz is None for r in v24)
    limit = max(r.speed_sec for r in v24 if r.speed_sec is not None)
    got = run(db, max_speed_sec=limit, voltage_v=24, speed_hz=50)
    assert sorted(got) == sorted(r.part_number for r in v24)


def test_min_duty_cycle_family(db):
    expected = {
        r.part_number
        for r in ROWS
        if (r.onoff_duty_cycle_pct if r.onoff_duty_cycle_pct is not None else r.duty_cycle_pct)
        is not None
        and (r.onoff_duty_cycle_pct if r.onoff_duty_cycle_pct is not None else r.duty_cycle_pct)
        >= 50
    }
    assert set(run(db, min_duty_cycle_pct=50, service="on_off")) == expected


@pytest.mark.parametrize("unit", ["nm", "in_lbs"])
def test_torque_and_duty_must_hold_in_one_family_catalog(db, unit):
    torques = sorted({v for r in ROWS for v, _ in families(r, unit) if v is not None})
    torque = torques[len(torques) // 3]
    duty = 50.0
    expected = {r.part_number for r in ROWS if meets_one_family(r, torque, duty, unit)}
    got = run(db, min_torque=torque, min_duty_cycle_pct=duty, torque_unit=unit)
    assert set(got) == expected and expected
    # Tightest fit: smallest torque among the families meeting BOTH constraints.
    f = SearchFilters(min_torque=torque, min_duty_cycle_pct=duty, torque_unit=unit)
    quals = [
        min(t for t, d in families(a, unit) if t is not None and t >= torque and (d or -1) >= duty)
        for a in repo.search(db, f, limit=1000)
    ]
    assert quals == sorted(quals)


def _synthetic(pn: str, **cols: float | None) -> Actuator:
    """Catalog-shaped row with only the given family columns set."""
    base = next(r for r in ROWS if r.has_data and r.voltage == "110V").model_dump()
    for k in base:
        if k.startswith(("onoff_", "mod_", "output_")) or k == "duty_cycle_pct":
            base[k] = None
    return Actuator.model_construct(**{**base, "part_number": pn, **cols})


def test_split_families_do_not_combine_regression(pg):
    """on/off meets torque but not duty; modulating meets duty but not torque -> no match.
    A row where one family meets both does match."""
    split = _synthetic(
        "769A00-11300000/A",
        onoff_torque_nm=500.0,
        onoff_duty_cycle_pct=10.0,
        mod_torque_nm=50.0,
        mod_duty_cycle_pct=90.0,
    )
    both = _synthetic(
        "769B00-11300000/A",
        onoff_torque_nm=500.0,
        onoff_duty_cycle_pct=80.0,
        mod_torque_nm=700.0,
        mod_duty_cycle_pct=20.0,
    )
    tables = [t for t in CATALOG.tables if t.table_id == split.table_id]
    repo.upsert_catalog(pg, Catalog.model_construct(tables=tables, rows=[split, both]))
    f = SearchFilters(min_torque=400, min_duty_cycle_pct=70)
    assert pns(repo.search(pg, f)) == ["769B00-11300000/A"]
    assert repo.count_matches(pg, f) == 1
    # Each constraint alone matches both rows.
    assert repo.count_matches(pg, SearchFilters(min_torque=400)) == 2
    assert repo.count_matches(pg, SearchFilters(min_duty_cycle_pct=70)) == 2
    # With service set, only that family counts.
    assert run(pg, min_torque=400, min_duty_cycle_pct=70, service="on_off") == ["769B00-11300000/A"]
    assert run(pg, min_torque=400, min_duty_cycle_pct=15, service="modulating") == [
        "769B00-11300000/A"
    ]
    # Closest values keep the same-family rule (torque 700 is only on a 20% family).
    rep = repo.diagnose_no_match(pg, SearchFilters(min_torque=900, min_duty_cycle_pct=70))
    assert rep.closest["min_torque"] == 500.0
    rep = repo.diagnose_no_match(pg, SearchFilters(min_torque=600, min_duty_cycle_pct=70))
    assert rep.closest["min_duty_cycle_pct"] == 20.0


def test_na_rows_excluded_from_numeric_filters(db):
    na = {r.part_number for r in ROWS if not r.has_data}
    assert len(na) == 4
    assert na <= set(run(db, phase=3))  # present without numeric filters
    assert not na & set(run(db, phase=3, max_speed_sec=10_000))
    assert not na & set(run(db, min_torque=0.001))
    assert not na & set(run(db, min_duty_cycle_pct=0))


def test_combination_filters(db):
    got = run(db, voltage_v=220, phase=1, enclosure="explosionproof", service="modulating")
    assert got and set(got) == {
        r.part_number
        for r in ROWS
        if r.voltage == "220V" and r.phase == 1 and r.enclosure == "explosionproof"
    }
    assert run(db, voltage_v=24, phase=1) == []  # 24V tables have no phase


def test_diagnose_torque_too_high(db):
    best = max(v for r in ROWS if (v := torque_of(r, None)) is not None)
    report = repo.diagnose_no_match(db, SearchFilters(min_torque=best + 1))
    assert report.blocking == ["min_torque"]
    assert report.out_of_catalog is False
    assert report.closest == {"min_torque": best}
    assert str(best) in report.message


def test_diagnose_closest_respects_other_filters_and_unit(db):
    f = SearchFilters(min_torque=1e9, torque_unit="in_lbs", voltage_v=24)
    best = max(
        v
        for r in ROWS
        if r.voltage.startswith("24V") and (v := torque_of(r, None, "in_lbs")) is not None
    )
    assert repo.diagnose_no_match(db, f).closest == {"min_torque": best}


def test_diagnose_speed_and_duty(db):
    fastest = min(
        r.speed_sec_60hz if r.speed_sec_60hz is not None else r.speed_sec
        for r in ROWS
        if r.has_data and (r.speed_sec_60hz is not None or r.speed_sec is not None)
    )
    rep = repo.diagnose_no_match(db, SearchFilters(max_speed_sec=fastest / 2))
    assert rep.blocking == ["max_speed_sec"] and rep.closest == {"max_speed_sec": fastest}
    duties = [
        r.onoff_duty_cycle_pct if r.onoff_duty_cycle_pct is not None else r.duty_cycle_pct
        for r in ROWS
        if r.enclosure == "explosionproof" and r.voltage == "110V"
    ]
    top = max(d for d in duties if d is not None)
    f = SearchFilters(
        min_duty_cycle_pct=top + 1, enclosure="explosionproof", voltage_v=110, service="on_off"
    )
    rep = repo.diagnose_no_match(db, f)
    assert rep.blocking == ["min_duty_cycle_pct"] and rep.closest == {"min_duty_cycle_pct": top}


def test_diagnose_24v_weatherproof_out_of_catalog(db):
    assert not any(r.voltage.startswith("24V") and r.enclosure == "weatherproof" for r in ROWS)
    rep = repo.diagnose_no_match(db, SearchFilters(voltage_v=24, enclosure="weatherproof"))
    assert rep.out_of_catalog is True
    assert set(rep.blocking) == {"voltage_v", "enclosure"}
    assert rep.closest == {}


def test_diagnose_three_phase_explosionproof_out_of_catalog(db):
    rep = repo.diagnose_no_match(db, SearchFilters(phase=3, enclosure="explosionproof"))
    assert rep.out_of_catalog is True


def test_catalog_summary_totals(db):
    s = repo.catalog_summary(db)
    assert s.total_rows == len(ROWS) == 68
    assert s.rows_without_data == sum(not r.has_data for r in ROWS) == 4
    assert sum(int(c["rows"] or 0) for c in s.combinations) == 68
    assert {c["table_id"] for c in s.combinations} == {t.table_id for t in CATALOG.tables}
    for nm, lbs in ((s.torque_nm_range, s.torque_in_lbs_range),):
        nm_vals = [
            v
            for r in ROWS
            for v in (r.onoff_torque_nm, r.mod_torque_nm, r.output_torque_nm)
            if v is not None
        ]
        lbs_vals = [
            v
            for r in ROWS
            for v in (r.onoff_torque_in_lbs, r.mod_torque_in_lbs, r.output_torque_in_lbs)
            if v is not None
        ]
        assert nm == (min(nm_vals), max(nm_vals))
        assert lbs == (min(lbs_vals), max(lbs_vals))


def test_catalog_summary_empty_db(pg):
    s = repo.catalog_summary(pg)
    assert (s.total_rows, s.rows_without_data, s.combinations) == (0, 0, [])
    assert s.torque_nm_range is None and s.torque_in_lbs_range is None


def test_table_notes(db):
    ids = [t.table_id for t in CATALOG.tables]
    got = repo.table_notes(db, ids)
    assert got == {t.table_id: t.notes for t in CATALOG.tables}
    assert any("IEC 60034-1" in n for n in got["T1_wp_110v_1ph"])
    assert repo.table_notes(db, ["nope"]) == {}
    assert repo.table_notes(db, []) == {}
