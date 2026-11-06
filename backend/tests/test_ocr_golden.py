"""OCR-only extraction vs the golden file: exact rows per table and >= 99% of cells (slow).

Offline RapidOCR over the real PDF crops; no LLM. Regression guard for the Sprint 8 findings:
the merged 'N/A' block of the three-phase table, 'O' misread as '0' in a part number, and
thousands commas read as dots.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import pytest

from app.domain.models import TABLE_IDS
from app.ingestion.crops import crop_tables
from app.ingestion.flags import flag_cells
from app.ingestion.ocr import OcrResult, ocr_tables
from app.ingestion.validate import validate_rows

ROOT = Path(__file__).parent.parent
PDF = ROOT / "data/raw/series_76_electric_data.pdf"
GOLDEN = ROOT / "tests/fixtures/golden_draft.json"
SKIP = {"candidate", "run", "row_index", "unparsed"}

pytestmark = pytest.mark.slow


@pytest.fixture(scope="module")
def result(tmp_path_factory: pytest.TempPathFactory) -> OcrResult:
    return ocr_tables(crop_tables(PDF, tmp_path_factory.mktemp("crops")))


def _gold() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = json.loads(GOLDEN.read_text())["rows"]
    return rows


def test_exact_row_count_per_table(result: OcrResult) -> None:
    want = Counter(r["table_id"] for r in _gold())
    got = Counter(r.table_id for r in result.rows)
    assert {t: got[t] for t in TABLE_IDS} == {t: want[t] for t in TABLE_IDS}
    assert sum(got.values()) == 68


def test_na_rows_are_read_as_empty_rows(result: OcrResult) -> None:
    t3 = {r.part_number: r for r in result.rows if r.table_id == "T3_wp_220v_3ph"}
    for pn in ("761A00-11330C00/A", "761B00-11330C00/A", "762A00-11330C00/A", "762B00-11330C00/A"):
        row = t3[pn]
        assert row.output_torque_in_lbs is None and row.motor_power_w is None


def test_cell_accuracy_at_least_99_percent(result: OcrResult) -> None:
    by_key = {(r.table_id, r.part_number): r for r in result.rows}
    total = wrong = 0
    for g in _gold():
        row = by_key[(str(g["table_id"]), str(g["part_number"]))]
        for field, want in g.items():
            if field in SKIP:
                continue
            total += 1
            wrong += getattr(row, field, None) != want
    assert 1 - wrong / total >= 0.99, f"{wrong}/{total} cells differ"


def test_na_cells_and_clean_tables_are_not_flagged(result: OcrResult) -> None:
    flags = flag_cells(result.cells, validate_rows(result.rows))
    na = {"761A00-11330C00/A", "761B00-11330C00/A", "762A00-11330C00/A", "762B00-11330C00/A"}
    assert not [f for f in flags if f.part_number in na]
    assert not [
        f for f in flags if f.table_id in ("T4_xp_24v_onoff", "T5_xp_24vdc_mod", "T6_xp_110v_1ph")
    ]
