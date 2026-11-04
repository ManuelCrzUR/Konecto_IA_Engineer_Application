"""Unit tests for app.ingestion.normalize (no OCR repair, values as printed)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.domain.models import NUMERIC_FIELDS, Actuator
from app.ingestion.normalize import (
    SUFFIX_BY_TABLE,
    NormalizationError,
    check_suffix,
    normalize_row,
    parse_number,
    split_part_number,
)

GOLDEN = Path(__file__).parent / "fixtures" / "golden_draft.json"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("26,500", 26500.0),
        ("1,234,567", 1234567.0),
        ("1,200.5", 1200.5),
        ("1.2", 1.2),
        ("40", 40.0),
        (" 17 ", 17.0),
        ("N/A", None),
        ("n/a", None),
        ("  N/A ", None),
        ("N/ A", None),
        ("", None),
        ("   ", None),
        (None, None),
    ],
)
def test_parse_number_ok(raw: str | None, expected: float | None) -> None:
    assert parse_number(raw) == expected


@pytest.mark.parametrize(
    "raw",
    [
        "2,65",
        "26.500,0",
        "1,23",
        "1234,567",
        ",500",
        "13Z00000",
        "O5",
        "2%",
        "-5",
        ".5",
        "1.",
        "1.2.3",
        "abc",
        "1 000",
        "N/B",
        "1,2345",
    ],
)
def test_parse_number_rejects(raw: str) -> None:
    with pytest.raises(NormalizationError):
        parse_number(raw)


def test_split_part_number() -> None:
    assert split_part_number("766A00-11320000/A*") == ("766A00-11320000/A", False)
    assert split_part_number(" 761A00-11300000/A ") == ("761A00-11300000/A", True)
    assert split_part_number("761A00 - 11300000/A") == ("761A00-11300000/A", True)


def test_check_suffix() -> None:
    check_suffix("T1_wp_110v_1ph", "761A00-11300000/A")
    check_suffix("T3_wp_220v_3ph", "764A00-11330C00/A")
    with pytest.raises(NormalizationError):
        check_suffix("T1_wp_110v_1ph", "761A00-11320000/A")
    with pytest.raises(NormalizationError):
        check_suffix("T1_wp_110v_1ph", "761A0011300000")
    with pytest.raises(NormalizationError):
        check_suffix("TX", "761A00-11300000/A")


def test_normalize_row_basic() -> None:
    a = normalize_row(
        "T2_wp_220v_1ph",
        "766A00-11320000/A*",
        {"onoff_torque_in_lbs": "1,200", "fla_60hz_a": "N/A", "speed_sec_60hz": None},
        row_index=3,
    )
    assert isinstance(a, Actuator)
    assert a.part_number == "766A00-11320000/A"
    assert a.csa_certified is False
    assert a.enclosure == "weatherproof"
    assert a.voltage == "220V"
    assert a.phase == 1
    assert a.onoff_torque_in_lbs == 1200.0
    assert a.fla_60hz_a is None
    assert a.row_index == 3


def test_normalize_row_errors() -> None:
    with pytest.raises(NormalizationError):
        normalize_row("TX", "761A00-11300000/A", {})
    with pytest.raises(NormalizationError):
        normalize_row("T1_wp_110v_1ph", "761A00-11300000/A", {"bogus": "1"})
    with pytest.raises(NormalizationError):
        normalize_row("T1_wp_110v_1ph", "761A00-11320000/A", {})
    with pytest.raises(NormalizationError):
        normalize_row("T1_wp_110v_1ph", "761A00-11300000/A", {"fla_a": "2,65"})
    with pytest.raises(NormalizationError):
        normalize_row("T1_wp_110v_1ph", "FESA", {})


def _golden_rows() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = json.loads(GOLDEN.read_text())["rows"]
    return rows


def _fmt(value: float | None) -> str:
    if value is None:
        return "N/A"
    if value >= 1000:
        return f"{value:,.0f}" if value == int(value) else f"{value:,}"
    return str(int(value)) if value == int(value) else str(value)


def test_golden_round_trip() -> None:
    rows = _golden_rows()
    assert len(rows) == 68
    assert set(SUFFIX_BY_TABLE) >= {r["table_id"] for r in rows}
    for row in rows:
        cells = {f: _fmt(row[f]) for f in NUMERIC_FIELDS}  # type: ignore[arg-type]
        raw_pn = str(row["part_number"]) + ("" if row["csa_certified"] else "*")
        got = normalize_row(str(row["table_id"]), raw_pn, cells, row["row_index"])  # type: ignore[arg-type]
        expected = Actuator.from_bench_row(row)
        assert got == expected, row["part_number"]
