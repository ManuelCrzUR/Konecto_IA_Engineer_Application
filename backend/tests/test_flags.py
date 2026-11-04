"""flags.py: which OCR cells are doubtful. Fast, no OCR."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from app.ingestion.flags import CONF_MIN, flag_cells, tables_to_escalate
from app.ingestion.ocr import OcrCell
from app.ingestion.validate import Issue

CELLS_JSON = Path(__file__).parent.parent / "app/ingestion/_reference/cells.json"


def cell(
    raw: str = "40",
    conf: float = 0.99,
    field: str = "onoff_duty_cycle_pct",
    pn: str = "761A00-11300000/A",
    table: str = "T1_wp_110v_1ph",
    err: str | None = None,
) -> OcrCell:
    return OcrCell(table_id=table, part_number=pn, field=field, raw=raw, conf=conf, parse_error=err)


def issue(
    pn: str = "761A00-11300000/A",
    field: str | None = "onoff_duty_cycle_pct",
    level: Literal["error", "warning"] = "error",
) -> Issue:
    return Issue(
        level=level,
        check="x",
        table_id="T1_wp_110v_1ph",
        part_number=pn,
        field=field,
        message="m",
    )


def test_clean_cell_not_flagged() -> None:
    assert flag_cells([cell()], []) == []


def test_low_conf_threshold() -> None:
    assert flag_cells([cell(conf=CONF_MIN)], []) == []
    (f,) = flag_cells([cell(conf=0.89)], [])
    assert f.reasons == ["low_conf"]


def test_leading_zero() -> None:
    assert flag_cells([cell(raw="0.7")], []) == []
    assert flag_cells([cell(raw="0")], []) == []
    assert flag_cells([cell(raw="096")], [])[0].reasons == ["leading_zero"]
    assert flag_cells([cell(raw="0 6")], [])[0].reasons == ["leading_zero"]


def test_unparsable() -> None:
    (f,) = flag_cells([cell(raw="1x", err="not a plain number")], [])
    assert f.reasons == ["unparsable"]


def test_validator_matches_pn_and_field_with_error_level() -> None:
    assert flag_cells([cell()], [issue()])[0].reasons == ["validator"]
    assert flag_cells([cell()], [issue(field="other")]) == []
    assert flag_cells([cell()], [issue(pn="999")]) == []
    assert flag_cells([cell()], [issue(level="warning")]) == []
    assert flag_cells([cell()], [issue(field=None)]) == []


def test_combined_reasons_and_order() -> None:
    cells = [cell(raw="06", conf=0.5, err="bad"), cell(raw="1", conf=0.1, field="a")]
    flags = flag_cells(cells, [issue()])
    assert flags[0].reasons == ["low_conf", "leading_zero", "validator", "unparsable"]
    assert [f.field for f in flags] == ["onoff_duty_cycle_pct", "a"]


def test_tables_to_escalate_sorted_distinct() -> None:
    cells = [
        cell(conf=0.1, table="T7_xp_220v_1ph"),
        cell(conf=0.1, table="T2_wp_220v_1ph"),
        cell(conf=0.1, table="T7_xp_220v_1ph"),
        cell(table="T4_xp_24v_onoff"),
    ]
    assert tables_to_escalate(flag_cells(cells, [])) == ["T2_wp_220v_1ph", "T7_xp_220v_1ph"]
    assert tables_to_escalate([]) == []


def test_benchmark_regression() -> None:
    cells = [
        OcrCell(**{k: v for k, v in d.items() if k != "refill"})
        for d in json.loads(CELLS_JSON.read_text())
    ]
    tables = tables_to_escalate(flag_cells(cells, []))
    for t in ("T1_wp_110v_1ph", "T2_wp_220v_1ph", "T3_wp_220v_3ph", "T7_xp_220v_1ph"):
        assert t in tables
    for t in ("T4_xp_24v_onoff", "T5_xp_24vdc_mod", "T6_xp_110v_1ph"):
        assert t not in tables


def table_issue(check: str, table: str, pn: str | None = None, field: str | None = None) -> Issue:
    return Issue(
        level="error", check=check, table_id=table, part_number=pn, field=field, message="m"
    )


def test_table_level_errors_escalate_without_flags() -> None:
    cells = [cell()]
    issues = [
        table_issue("row_count", "T5_xp_24vdc_mod"),
        table_issue("unique_pn", "T3_wp_220v_3ph", "764A00-11330C00/A", "part_number"),
    ]
    assert tables_to_escalate([], issues, cells) == ["T3_wp_220v_3ph", "T5_xp_24vdc_mod"]


def test_cell_mapped_or_warning_issues_do_not_add_tables() -> None:
    cells = [cell()]
    mapped = table_issue(
        "duty_range", "T1_wp_110v_1ph", "761A00-11300000/A", "onoff_duty_cycle_pct"
    )
    warn = Issue(level="warning", check="row_count", table_id="T4_xp_24v_onoff", message="m")
    assert tables_to_escalate([], [mapped, warn], cells) == []
