"""ocr.py: real RapidOCR over the 7 table crops (slow) + fast error cases."""

from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np
import pytest

from app.domain.models import NUMERIC_FIELDS
from app.ingestion import ocr as ocr_mod
from app.ingestion.crops import crop_tables
from app.ingestion.flags import flag_cells, tables_to_escalate
from app.ingestion.ocr import OcrError, OcrResult, ocr_table, ocr_tables
from app.ingestion.table_meta import TABLE_FIELDS
from app.ingestion.validate import validate_rows

ROOT = Path(__file__).parent.parent
PDF = ROOT / "data/raw/series_76_electric_data.pdf"
GOLDEN = ROOT / "tests/fixtures/golden_draft.json"
CellKey = tuple[str, str, str]


def test_blank_png_raises() -> None:
    blank = cv2.imencode(".png", np.full((80, 200, 3), 255, np.uint8))[1].tobytes()
    with pytest.raises(OcrError):
        ocr_table("T1_wp_110v_1ph", blank)


def test_garbage_bytes_and_unknown_table_raise() -> None:
    with pytest.raises(OcrError):
        ocr_table("T1_wp_110v_1ph", b"not a png")
    with pytest.raises(OcrError):
        ocr_table("nope", b"")


def test_missed_cells_become_missing_cells_not_omitted(monkeypatch: pytest.MonkeyPatch) -> None:
    table = "T4_xp_24v_onoff"
    pn = ocr_mod._Box(0, 0, 100, 20, "761A00-11380000/A", 0.99)
    lay = ocr_mod._Layout(
        pns=[pn],
        pn_right=100,
        mx0=900,
        pitch=30,
        cuts=[200.0 + 50 * i for i in range(6)],
        rules=[],
        data=[],
        power=[],
    )
    monkeypatch.setattr(ocr_mod, "_refill", lambda *a, **k: None)
    gray = np.full((50, 1000), 255, np.uint8)
    cells = ocr_mod._row_cells(table, gray, lay, pn)
    assert [c[0] for c in cells] == list(TABLE_FIELDS[table])
    assert all(c[1] == "" for c in cells)
    assert ocr_mod._parse_error("") == "missing"


@pytest.fixture(scope="module")
def result(tmp_path_factory: pytest.TempPathFactory) -> OcrResult:
    crops = crop_tables(PDF, tmp_path_factory.mktemp("crops"))
    return ocr_tables(crops)


def _mismatches(result: OcrResult) -> tuple[list[CellKey], int]:
    gold = {(r["table_id"], r["part_number"]): r for r in json.loads(GOLDEN.read_text())["rows"]}
    bad: list[CellKey] = []
    total = 0
    for r in result.rows:
        g = gold.get((r.table_id, r.part_number))
        if g is None:
            continue
        for f in NUMERIC_FIELDS:
            a, b = getattr(r, f), g.get(f)
            if a is None and b is None:
                continue
            total += 1
            if a is None or b is None or round(a, 3) != round(b, 3):
                bad.append((r.table_id, r.part_number, f))
    return bad, total


@pytest.mark.slow
def test_rows_and_part_numbers(result: OcrResult) -> None:
    gold = {(r["table_id"], r["part_number"]) for r in json.loads(GOLDEN.read_text())["rows"]}
    got = {(r.table_id, r.part_number) for r in result.rows}
    print(f"rows: {len(result.rows)}; missing: {sorted(gold - got)}")
    assert got <= gold
    assert len(result.rows) == 68 - len(gold - got)


@pytest.mark.slow
def test_cell_accuracy_vs_golden(result: OcrResult) -> None:
    bad, total = _mismatches(result)
    # Cells the strict parser rejected (value None, parse_error set) are "detected", not
    # misread: they are escalated. Accuracy is measured over cells that got a value.
    rejected = {(c.table_id, c.part_number, c.field) for c in result.cells if c.parse_error}
    wrong = [m for m in bad if m not in rejected]
    print(
        f"raw accuracy {1 - len(bad) / total:.4f} ({len(bad)}/{total}); "
        f"rejected by strict parse: {len(bad) - len(wrong)}"
    )
    for m in bad:
        print("MISMATCH", m, "(rejected)" if m in rejected else "(misread)")
    assert 1 - len(wrong) / (total - len(bad) + len(wrong)) >= 0.99
    assert not [m for m in bad if m[0] in ("T4_xp_24v_onoff", "T5_xp_24vdc_mod", "T6_xp_110v_1ph")]


@pytest.mark.slow
def test_every_wrong_cell_is_flagged(result: OcrResult) -> None:
    bad, _ = _mismatches(result)
    flags = flag_cells(result.cells, validate_rows(result.rows))
    flagged = {(f.table_id, f.part_number, f.field) for f in flags}
    print("flagged tables:", tables_to_escalate(flags), "cells:", len(flagged))
    assert [m for m in bad if m not in flagged] == []
