"""Black-box contract tests for app.ingestion.normalize (written from its docstrings only)."""

from __future__ import annotations

import pytest

from app.domain.models import Actuator
from app.ingestion.normalize import (
    SECTION_META,
    SUFFIX_BY_TABLE,
    NormalizationError,
    check_suffix,
    normalize_row,
    parse_number,
    split_part_number,
)


# ---------------------------------------------------------------- parse_number
@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("26,500", 26500.0),
        ("1,200", 1200.0),
        ("12,345,678", 12345678.0),
        ("1,200.5", 1200.5),
        ("1.2", 1.2),
        ("0.7", 0.7),
        ("07", 7.0),
        ("26.500", 26.5),  # valid plain decimal as printed; no OCR "repair"
        ("42", 42.0),
        ("0", 0.0),
        (" 1.2 ", 1.2),  # surrounding whitespace tolerated
        ("\t300\n", 300.0),
    ],
)
def test_parse_number_valid(raw: str, expected: float) -> None:
    result = parse_number(raw)
    assert isinstance(result, float)
    assert result == pytest.approx(expected)


@pytest.mark.parametrize("raw", ["N/A", "n/a", "N/a", "  N/A  ", "", None])
def test_parse_number_missing_is_none(raw: str | None) -> None:
    assert parse_number(raw) is None


@pytest.mark.parametrize(
    "raw",
    [
        "2,65",  # comma not in a group of three
        "1,20",
        "1,2000",
        ",500",
        "26,50,0",
        "7FE1A00",
        "1.2.3",
        "~5",
        "O",  # letter O is not repaired into 0
        "1O",
        "abc",
        "12 34",
        "5%",
        "1e5x",
    ],
)
def test_parse_number_garbage_raises(raw: str) -> None:
    with pytest.raises(NormalizationError):
        parse_number(raw)


def test_normalization_error_is_value_error() -> None:
    assert issubclass(NormalizationError, ValueError)


# ----------------------------------------------------------- split_part_number
@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("766A00-11320000/A*", ("766A00-11320000/A", False)),
        ("761A00-11300000/A", ("761A00-11300000/A", True)),
        ("761A00 - 11300000/A*", ("761A00-11300000/A", False)),
        (" 761A00-11300000/A ", ("761A00-11300000/A", True)),
        ("761A00-11300000 /A", ("761A00-11300000/A", True)),
        ("767C00-11320000/A *", ("767C00-11320000/A", False)),
    ],
)
def test_split_part_number(raw: str, expected: tuple[str, bool]) -> None:
    assert split_part_number(raw) == expected


# ---------------------------------------------------------------- check_suffix
@pytest.mark.parametrize("table_id", sorted(SUFFIX_BY_TABLE))
def test_check_suffix_accepts_matching_suffix(table_id: str) -> None:
    check_suffix(table_id, f"761A00-{SUFFIX_BY_TABLE[table_id]}/A")


@pytest.mark.parametrize(
    ("table_id", "pn"),
    [
        ("T1_wp_110v_1ph", "761A00-11320000/A"),
        ("T2_wp_220v_1ph", "761A00-11300000/A"),
        ("T3_wp_220v_3ph", "761A00-11320000/A"),
        ("T4_xp_24v_onoff", "761A00-11370000/A"),
        ("T5_xp_24vdc_mod", "761A00-11380000/A"),
        ("T6_xp_110v_1ph", "761A00-11330C00/A"),
    ],
)
def test_check_suffix_mismatch_raises(table_id: str, pn: str) -> None:
    with pytest.raises(NormalizationError):
        check_suffix(table_id, pn)


def test_check_suffix_unknown_table_raises() -> None:
    with pytest.raises(NormalizationError):
        check_suffix("T99_nope", "761A00-11300000/A")


# ---------------------------------------------------------------- normalize_row
def test_normalize_row_t1_full() -> None:
    row = normalize_row(
        "T1_wp_110v_1ph",
        "761A00-11300000/A",
        {
            "onoff_torque_in_lbs": "26,500",
            "onoff_torque_nm": "3,000",
            "onoff_duty_cycle_pct": "50",
            "cycles_per_hour": "1,200",
            "speed_sec_60hz": "10.5",
            "fla_60hz_a": "0.7",
            "lra_60hz_a": "N/A",
            "motor_power_w": "",
            "fla_50hz_a": None,
        },
        row_index=3,
    )
    assert isinstance(row, Actuator)
    assert row.table_id == "T1_wp_110v_1ph"
    assert row.part_number == "761A00-11300000/A"
    assert row.csa_certified is True
    assert row.enclosure == "weatherproof"
    assert row.voltage == "110V"
    assert row.phase == 1
    assert row.service == "on_off_and_modulating"
    assert row.row_index == 3
    assert row.onoff_torque_in_lbs == pytest.approx(26500.0)
    assert row.onoff_torque_nm == pytest.approx(3000.0)
    assert row.cycles_per_hour == pytest.approx(1200.0)
    assert row.speed_sec_60hz == pytest.approx(10.5)
    assert row.fla_60hz_a == pytest.approx(0.7)
    assert row.lra_60hz_a is None
    assert row.motor_power_w is None
    assert row.fla_50hz_a is None
    assert row.has_data is True


def test_normalize_row_star_sets_csa_false_and_cleans_pn() -> None:
    row = normalize_row("T2_wp_220v_1ph", "766A00-11320000/A*", {"onoff_torque_in_lbs": "100"})
    assert row.csa_certified is False
    assert row.part_number == "766A00-11320000/A"
    assert "*" not in row.part_number


def test_normalize_row_pn_with_internal_spaces() -> None:
    row = normalize_row("T1_wp_110v_1ph", "761A00 - 11300000/A*", {"onoff_torque_in_lbs": "100"})
    assert row.part_number == "761A00-11300000/A"
    assert row.csa_certified is False


def test_normalize_row_t3_three_phase_unspecified_service() -> None:
    row = normalize_row(
        "T3_wp_220v_3ph",
        "763A00-11330C00/A",
        {"output_torque_in_lbs": "2,650", "duty_cycle_pct": "75", "speed_sec": "15"},
    )
    assert row.phase == 3
    assert row.service == "unspecified"
    assert row.voltage == "220V"
    assert row.enclosure == "weatherproof"
    assert row.output_torque_in_lbs == pytest.approx(2650.0)


def test_normalize_row_t3_all_na_row_has_no_data() -> None:
    row = normalize_row(
        "T3_wp_220v_3ph",
        "761A00-11330C00/A",
        {"output_torque_in_lbs": "N/A", "output_torque_nm": "N/A", "duty_cycle_pct": "n/a"},
    )
    assert row.has_data is False
    assert row.output_torque_in_lbs is None
    assert row.phase == 3


def test_normalize_row_t4_no_phase_ac_dc() -> None:
    row = normalize_row("T4_xp_24v_onoff", "761A00-11380000/A", {"onoff_torque_in_lbs": "150"})
    assert row.phase is None
    assert row.voltage == "24V AC/DC"
    assert row.enclosure == "explosionproof"
    assert row.service == "on_off"
    assert row.current_type == "AC/DC"


def test_normalize_row_empty_cells_dict_has_no_data() -> None:
    row = normalize_row("T5_xp_24vdc_mod", "762B00-11370000/A", {})
    assert row.has_data is False
    assert row.voltage == "24V DC"
    assert row.service == "modulating"


@pytest.mark.parametrize("table_id", sorted(SECTION_META))
def test_normalize_row_meta_matches_section_meta(table_id: str) -> None:
    meta = SECTION_META[table_id]
    row = normalize_row(table_id, f"761A00-{SUFFIX_BY_TABLE[table_id]}/A", {})
    assert row.table_id == table_id
    assert row.enclosure == meta["enclosure"]
    assert row.voltage == meta["voltage"]
    assert row.phase == meta["phase"]
    assert row.service == meta["service"]
    assert row.current_type == meta["current_type"]
    assert row.certifications == meta["certifications"]


def test_normalize_row_unknown_field_raises() -> None:
    with pytest.raises(NormalizationError):
        normalize_row("T1_wp_110v_1ph", "761A00-11300000/A", {"bogus_field": "1"})


def test_normalize_row_unknown_table_raises() -> None:
    with pytest.raises(NormalizationError):
        normalize_row("T99_nope", "761A00-11300000/A", {})


def test_normalize_row_suffix_mismatch_raises() -> None:
    with pytest.raises(NormalizationError):
        normalize_row("T1_wp_110v_1ph", "761A00-11320000/A", {"onoff_torque_in_lbs": "1"})


def test_normalize_row_suffix_mismatch_with_star_raises() -> None:
    with pytest.raises(NormalizationError):
        normalize_row("T1_wp_110v_1ph", "761A00-11320000/A*", {})


@pytest.mark.parametrize("bad", ["2,65", "7FE1A00", "1.2.3", "~5", "O"])
def test_normalize_row_garbage_cell_raises(bad: str) -> None:
    with pytest.raises(NormalizationError):
        normalize_row("T1_wp_110v_1ph", "761A00-11300000/A", {"onoff_torque_in_lbs": bad})


def test_normalize_row_values_not_converted_or_repaired() -> None:
    # '26.500' stays 26.5 (no thousands guess); nm/in-lbs are not cross-computed.
    row = normalize_row(
        "T1_wp_110v_1ph",
        "761A00-11300000/A",
        {"onoff_torque_in_lbs": "26.500", "onoff_torque_nm": "1"},
    )
    assert row.onoff_torque_in_lbs == pytest.approx(26.5)
    assert row.onoff_torque_nm == pytest.approx(1.0)
    assert row.speed_sec_60hz is None
