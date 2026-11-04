"""Tests for app.ingestion.validate, using the hand-verified golden draft."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.domain.models import Actuator
from app.ingestion.validate import ValidationFailed, assert_valid, validate_rows

GOLDEN = Path(__file__).parent / "fixtures" / "golden_draft.json"


def _golden() -> list[Actuator]:
    data = json.loads(GOLDEN.read_text())
    return [Actuator.from_bench_row(r) for r in data["rows"]]


def _find(rows: list[Actuator], table: str, pn: str) -> int:
    return next(i for i, r in enumerate(rows) if r.table_id == table and r.part_number == pn)


def _mutate(rows: list[Actuator], idx: int, **changes: object) -> list[Actuator]:
    out = list(rows)
    out[idx] = rows[idx].model_copy(update=changes)
    return out


def _checks(rows: list[Actuator], level: str) -> list[str]:
    return [i.check for i in validate_rows(rows) if i.level == level]


def test_golden_has_no_errors() -> None:
    issues = validate_rows(_golden())
    assert [i for i in issues if i.level == "error"] == []


def test_golden_warnings_are_only_known_kinds() -> None:
    warnings = assert_valid(_golden())
    assert {w.check for w in warnings} <= {"speed_60_le_50", "starts_known"}


def test_deterministic_order() -> None:
    rows = _mutate(_golden(), 0, onoff_torque_nm=1.0)
    assert validate_rows(rows) == validate_rows(list(rows))


def test_torque_ratio_known_ocr_error() -> None:
    rows = _golden()
    i = _find(rows, "T7_xp_220v_1ph", "761Y30-11320000/A")
    assert rows[i].onoff_torque_nm == 90
    bad = _mutate(rows, i, onoff_torque_nm=6.0)
    errs = [x for x in validate_rows(bad) if x.check == "torque_ratio"]
    # One issue per cell of the pair: either value may be the misread one.
    assert {e.field for e in errs} == {"onoff_torque_in_lbs", "onoff_torque_nm"}
    for e in errs:
        assert e.level == "error"
        assert e.table_id == "T7_xp_220v_1ph"
        assert e.part_number == "761Y30-11320000/A"
        assert "=6.0" in e.message


def test_starts_known_warning_on_ocr_error() -> None:
    rows = _golden()
    i = _find(rows, "T2_wp_220v_1ph", "767B00-11320000/A")
    assert rows[i].starts_per_hour == 960
    bad = _mutate(rows, i, starts_per_hour=96.0)
    issues = [
        x
        for x in validate_rows(bad)
        if x.check == "starts_known" and x.part_number == rows[i].part_number
    ]
    assert len(issues) == 1
    assert issues[0].level == "warning"
    assert "96.0" in issues[0].message
    # warnings alone do not raise
    assert any(w.check == "starts_known" for w in assert_valid(bad))


def test_row_count_missing_row() -> None:
    rows = _golden()[1:]
    errs = [i for i in validate_rows(rows) if i.check == "row_count"]
    assert len(errs) == 1
    assert errs[0].table_id == "T1_wp_110v_1ph"
    assert "expected 11" in errs[0].message and "found 10" in errs[0].message


def test_unique_pn_duplicate() -> None:
    rows = _golden()
    # Replace a T1 row with a copy of another T1 row: counts stay right, PN duplicates.
    dup = rows[1].model_copy()
    rows[2] = dup
    errs = [i for i in validate_rows(rows) if i.check == "unique_pn"]
    assert len(errs) == 1
    assert errs[0].part_number == dup.part_number


def test_suffix_mismatch() -> None:
    rows = _golden()
    pn = rows[0].part_number.replace("11300000", "11320000")
    bad = _mutate(rows, 0, part_number=pn)
    errs = [i for i in validate_rows(bad) if i.check == "suffix"]
    assert len(errs) == 1
    assert "11320000" in errs[0].message and "11300000" in errs[0].message


def test_fla_le_lra() -> None:
    rows = _golden()
    bad = _mutate(rows, 0, fla_60hz_a=9.9)
    errs = [i for i in validate_rows(bad) if i.check == "fla_le_lra"]
    assert {e.field for e in errs} == {"fla_60hz_a", "lra_60hz_a"}
    assert all("fla_60hz_a=9.9" in e.message for e in errs)


def test_duty_range() -> None:
    rows = _golden()
    bad = _mutate(rows, 0, onoff_duty_cycle_pct=140.0)
    errs = [i for i in validate_rows(bad) if i.check == "duty_range"]
    assert len(errs) == 1
    assert errs[0].field == "onoff_duty_cycle_pct"
    assert "140.0" in errs[0].message


def test_speed_warning() -> None:
    rows = _golden()
    bad = _mutate(rows, 0, speed_sec_60hz=99.0)
    assert "speed_60_le_50" in _checks(bad, "warning")
    assert "speed_60_le_50" not in _checks(bad, "error")


def test_assert_valid_raises_with_only_errors() -> None:
    rows = _mutate(_golden(), 0, speed_sec_60hz=99.0, onoff_torque_nm=1.0)
    with pytest.raises(ValidationFailed) as exc:
        assert_valid(rows)
    assert exc.value.issues
    assert all(i.level == "error" for i in exc.value.issues)
    assert "torque_ratio" in {i.check for i in exc.value.issues}


def test_assert_valid_returns_warnings_when_clean() -> None:
    rows = _mutate(_golden(), 0, speed_sec_60hz=99.0)
    warnings = assert_valid(rows)
    assert warnings
    assert all(w.level == "warning" for w in warnings)
