"""Black-box contract tests for app.ingestion.validate (written from its docstring only)."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import pytest

from app.domain.models import EXPECTED_ROWS, Actuator
from app.ingestion.normalize import SUFFIX_BY_TABLE
from app.ingestion.validate import (
    KNOWN_STARTS,
    TORQUE_RATIO,
    TORQUE_TOLERANCE,
    Issue,
    ValidationFailed,
    assert_valid,
    validate_rows,
)

GOLDEN = Path(__file__).parent / "fixtures" / "golden_draft.json"


@pytest.fixture
def golden() -> list[Actuator]:
    raw = json.loads(GOLDEN.read_text())["rows"]
    return [Actuator.from_bench_row(r) for r in raw]


def _first(rows: list[Actuator], table: str, field: str | None = None) -> int:
    """Index of the first row of `table` (having `field` populated, if given)."""
    for i, r in enumerate(rows):
        if r.table_id == table and (field is None or getattr(r, field) is not None):
            return i
    raise AssertionError(f"no row in {table} with {field}")


def _mutate(rows: list[Actuator], idx: int, **update: object) -> list[Actuator]:
    out = list(rows)
    out[idx] = rows[idx].model_copy(update=update)
    return out


def _errors(issues: list[Issue]) -> list[Issue]:
    return [i for i in issues if i.level == "error"]


def _warnings(issues: list[Issue]) -> list[Issue]:
    return [i for i in issues if i.level == "warning"]


def _by_check(issues: list[Issue], check: str) -> list[Issue]:
    return [i for i in issues if i.check == check]


# --------------------------------------------------------------------------- golden


def test_golden_fixture_shape(golden: list[Actuator]) -> None:
    assert len(golden) == 68
    assert Counter(r.table_id for r in golden) == EXPECTED_ROWS


def test_golden_has_no_errors(golden: list[Actuator]) -> None:
    assert _errors(validate_rows(golden)) == []


def test_golden_assert_valid_returns_only_warnings(golden: list[Actuator]) -> None:
    result = assert_valid(golden)
    assert all(i.level == "warning" for i in result)
    assert result == _warnings(validate_rows(golden))


def test_result_order_is_deterministic(golden: list[Actuator]) -> None:
    # Mutate to produce several issues so ordering is actually exercised.
    rows = _mutate(golden, 0, onoff_duty_cycle_pct=150.0)
    rows = _mutate(rows, 5, starts_per_hour=96.0)
    rows = rows + [rows[3]]
    assert validate_rows(rows) == validate_rows(rows)
    assert validate_rows(list(reversed(rows))) == validate_rows(list(reversed(rows)))


# --------------------------------------------------------------------------- row_count


def test_empty_list_yields_row_count_error_for_every_table() -> None:
    issues = _by_check(validate_rows([]), "row_count")
    assert all(i.level == "error" for i in issues)
    assert {i.table_id for i in issues} == set(EXPECTED_ROWS)
    assert len(issues) == len(EXPECTED_ROWS) == 7


@pytest.mark.parametrize("table", sorted(EXPECTED_ROWS))
def test_missing_row_flags_only_that_table(golden: list[Actuator], table: str) -> None:
    idx = _first(golden, table)
    rows = golden[:idx] + golden[idx + 1 :]
    issues = _by_check(validate_rows(rows), "row_count")
    assert [i.table_id for i in issues] == [table]
    assert issues[0].level == "error"


def test_extra_row_flags_row_count(golden: list[Actuator]) -> None:
    extra = golden[0].model_copy(update={"part_number": "999Z99-11300000/A"})
    issues = _by_check(validate_rows(golden + [extra]), "row_count")
    assert [i.table_id for i in issues] == [golden[0].table_id]


# --------------------------------------------------------------------------- unique_pn


def test_duplicate_part_number_flagged(golden: list[Actuator]) -> None:
    # Replace a T1 row's PN by the PN of another T1 row: counts stay correct.
    t1 = [i for i, r in enumerate(golden) if r.table_id == "T1_wp_110v_1ph"]
    rows = _mutate(golden, t1[1], part_number=golden[t1[0]].part_number)
    issues = _by_check(validate_rows(rows), "unique_pn")
    assert issues, "expected unique_pn issue"
    assert all(i.level == "error" for i in issues)
    assert {i.part_number for i in issues} == {golden[t1[0]].part_number}


# --------------------------------------------------------------------------- suffix


@pytest.mark.parametrize("table", sorted(SUFFIX_BY_TABLE))
def test_wrong_suffix_flagged(golden: list[Actuator], table: str) -> None:
    idx = _first(golden, table)
    row = golden[idx]
    good = SUFFIX_BY_TABLE[table]
    bad = "11380000" if good != "11380000" else "11300000"
    assert good in row.part_number
    new_pn = row.part_number.replace(good, bad)
    rows = _mutate(golden, idx, part_number=new_pn)
    issues = _by_check(validate_rows(rows), "suffix")
    assert [i.part_number for i in issues] == [new_pn]
    assert issues[0].level == "error"
    assert issues[0].table_id == table


# --------------------------------------------------------------------------- torque_ratio

TORQUE_PAIRS = [
    ("T1_wp_110v_1ph", "onoff_torque_in_lbs", "onoff_torque_nm"),
    ("T1_wp_110v_1ph", "mod_torque_in_lbs", "mod_torque_nm"),
    ("T3_wp_220v_3ph", "output_torque_in_lbs", "output_torque_nm"),
]
_EPS = 1e-9


@pytest.mark.parametrize(("table", "in_f", "nm_f"), TORQUE_PAIRS)
@pytest.mark.parametrize(
    ("factor", "ok"),
    [
        (1.0, True),
        # Boundaries derived from the constants; tiny epsilon avoids float noise.
        (1 + TORQUE_TOLERANCE - _EPS, True),
        (1 - TORQUE_TOLERANCE + _EPS, True),
        (1 + TORQUE_TOLERANCE + 1e-4, False),
        (1 - TORQUE_TOLERANCE - 1e-4, False),
        (2.0, False),
    ],
)
def test_torque_ratio_boundaries(
    golden: list[Actuator], table: str, in_f: str, nm_f: str, factor: float, ok: bool
) -> None:
    idx = _first(golden, table, in_f)
    nm = 100.0
    rows = _mutate(golden, idx, **{nm_f: nm, in_f: nm * TORQUE_RATIO * factor})
    pn = golden[idx].part_number
    issues = _by_check(validate_rows(rows), "torque_ratio")
    mine = [i for i in issues if i.part_number == pn]
    if ok:
        assert mine == []
    else:
        assert len(mine) >= 1
        assert all(i.level == "error" and i.table_id == table for i in mine)
        assert all(i.field in (None, in_f, nm_f) for i in mine)


def test_torque_ratio_skipped_when_one_side_missing(golden: list[Actuator]) -> None:
    idx = _first(golden, "T1_wp_110v_1ph", "onoff_torque_in_lbs")
    rows = _mutate(golden, idx, onoff_torque_nm=None, onoff_torque_in_lbs=5000.0)
    pn = golden[idx].part_number
    assert [i for i in _by_check(validate_rows(rows), "torque_ratio") if i.part_number == pn] == []


# --------------------------------------------------------------------------- fla_le_lra

FLA_PAIRS = [
    ("T1_wp_110v_1ph", "fla_60hz_a", "lra_60hz_a"),
    ("T1_wp_110v_1ph", "fla_50hz_a", "lra_50hz_a"),
    ("T4_xp_24v_onoff", "fla_a", "lra_a"),
]


@pytest.mark.parametrize(("table", "fla_f", "lra_f"), FLA_PAIRS)
@pytest.mark.parametrize(
    ("fla", "lra", "ok"), [(2.0, 2.0, True), (2.0, 2.1, True), (2.1, 2.0, False)]
)
def test_fla_le_lra(
    golden: list[Actuator], table: str, fla_f: str, lra_f: str, fla: float, lra: float, ok: bool
) -> None:
    idx = _first(golden, table, fla_f)
    rows = _mutate(golden, idx, **{fla_f: fla, lra_f: lra})
    pn = golden[idx].part_number
    mine = [i for i in _by_check(validate_rows(rows), "fla_le_lra") if i.part_number == pn]
    if ok:
        assert mine == []
    else:
        assert len(mine) >= 1
        assert all(i.level == "error" and i.table_id == table for i in mine)
        assert all(i.field in (None, fla_f, lra_f) for i in mine)


# --------------------------------------------------------------------------- duty_range

DUTY_FIELDS = [
    ("T1_wp_110v_1ph", "onoff_duty_cycle_pct"),
    ("T1_wp_110v_1ph", "mod_duty_cycle_pct"),
    ("T3_wp_220v_3ph", "duty_cycle_pct"),
]


@pytest.mark.parametrize(("table", "field"), DUTY_FIELDS)
@pytest.mark.parametrize(
    ("value", "ok"),
    [(0.0, True), (100.0, True), (50.0, True), (100.1, False), (-0.1, False), (250.0, False)],
)
def test_duty_range(golden: list[Actuator], table: str, field: str, value: float, ok: bool) -> None:
    idx = _first(golden, table, field)
    rows = _mutate(golden, idx, **{field: value})
    pn = golden[idx].part_number
    mine = [i for i in _by_check(validate_rows(rows), "duty_range") if i.part_number == pn]
    if ok:
        assert mine == []
    else:
        assert [i.field for i in mine] == [field]
        assert mine[0].level == "error"
        assert mine[0].table_id == table


# --------------------------------------------------------------------------- warnings


def test_speed_60_greater_than_50_is_warning_only(golden: list[Actuator]) -> None:
    idx = _first(golden, "T1_wp_110v_1ph", "speed_sec_60hz")
    rows = _mutate(golden, idx, speed_sec_60hz=30.0, speed_sec_50hz=20.0)
    issues = validate_rows(rows)
    pn = golden[idx].part_number
    mine = [i for i in _by_check(issues, "speed_60_le_50") if i.part_number == pn]
    # Pair check: one issue per cell (decision D-17).
    assert {i.field for i in mine} == {"speed_sec_60hz", "speed_sec_50hz"}
    assert all(i.level == "warning" for i in mine)
    assert _errors(issues) == []
    assert_valid(rows)  # must not raise


def test_speed_equal_is_fine(golden: list[Actuator]) -> None:
    idx = _first(golden, "T1_wp_110v_1ph", "speed_sec_60hz")
    rows = _mutate(golden, idx, speed_sec_60hz=20.0, speed_sec_50hz=20.0)
    pn = golden[idx].part_number
    assert [
        i for i in _by_check(validate_rows(rows), "speed_60_le_50") if i.part_number == pn
    ] == []


def test_known_starts_constant() -> None:
    assert KNOWN_STARTS == frozenset({720.0, 840.0, 960.0, 1200.0})


@pytest.mark.parametrize("starts", [96.0, 1000.0, 0.0])
def test_unknown_starts_is_warning_not_error(golden: list[Actuator], starts: float) -> None:
    idx = _first(golden, "T1_wp_110v_1ph", "starts_per_hour")
    rows = _mutate(golden, idx, starts_per_hour=starts)
    issues = validate_rows(rows)
    pn = golden[idx].part_number
    mine = [i for i in _by_check(issues, "starts_known") if i.part_number == pn]
    assert len(mine) == 1
    assert mine[0].level == "warning"
    assert _errors(issues) == []
    assert_valid(rows)


@pytest.mark.parametrize("starts", sorted(KNOWN_STARTS))
def test_known_starts_no_issue(golden: list[Actuator], starts: float) -> None:
    idx = _first(golden, "T1_wp_110v_1ph", "starts_per_hour")
    rows = _mutate(golden, idx, starts_per_hour=starts)
    pn = golden[idx].part_number
    assert [i for i in _by_check(validate_rows(rows), "starts_known") if i.part_number == pn] == []


# --------------------------------------------------------------------------- assert_valid


def test_assert_valid_raises_with_only_error_issues(golden: list[Actuator]) -> None:
    rows = _mutate(golden, 0, onoff_duty_cycle_pct=150.0)
    rows = _mutate(rows, 1, speed_sec_60hz=99.0, speed_sec_50hz=1.0)  # warning-only mutation
    with pytest.raises(ValidationFailed) as exc:
        assert_valid(rows)
    assert exc.value.issues
    assert all(i.level == "error" for i in exc.value.issues)
    assert any(i.check == "duty_range" for i in exc.value.issues)
    assert isinstance(exc.value, RuntimeError)


def test_assert_valid_raises_on_empty() -> None:
    with pytest.raises(ValidationFailed) as exc:
        assert_valid([])
    assert {i.table_id for i in exc.value.issues} == set(EXPECTED_ROWS)


def test_assert_valid_returns_warnings_when_only_warnings(golden: list[Actuator]) -> None:
    rows = _mutate(golden, 0, starts_per_hour=96.0)
    result = assert_valid(rows)
    assert result and all(i.level == "warning" for i in result)
    assert any(i.check == "starts_known" for i in result)
