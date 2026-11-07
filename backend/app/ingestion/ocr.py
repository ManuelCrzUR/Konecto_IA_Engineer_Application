"""Table crop (PNG) -> raw cells, offline, with RapidOCR + row/column geometry.

Port of the benchmark extractor E with one change:
NO text repair. The reference turned 'O' into '0' and guessed thousands
separators; here every raw string goes through normalize.parse_number as is.
A cell that does not parse keeps value None and `parse_error` set, so
flags.py marks it and its table is escalated (never loaded unverified).

Contract:
- ocr_table(table_id, png) -> OcrResult for one table.
- ocr_tables(crops) -> OcrResult for all tables, in TABLE_IDS order.
- OcrCell / OcrResult / OcrError are defined in ocr_boxes and re-exported here.
Split: ocr_boxes (primitives), ocr_layout (geometry), ocr_cells (per-cell reads).
"""

from __future__ import annotations

import cv2
import numpy as np

from app.domain.models import TABLE_IDS
from app.ingestion.normalize import split_part_number
from app.ingestion.ocr_boxes import OcrCell, OcrError, OcrResult, _fix_pn, _ocr, _parse_error
from app.ingestion.ocr_cells import _build_row, _row_cells
from app.ingestion.ocr_layout import _layout
from app.ingestion.table_meta import TABLE_FIELDS

__all__ = ["OcrCell", "OcrError", "OcrResult", "ocr_table", "ocr_tables"]


def ocr_table(table_id: str, png: bytes) -> OcrResult:
    """OCR one table crop into strict rows plus the raw cell log."""
    if table_id not in TABLE_FIELDS:
        raise OcrError(f"unknown table_id: {table_id!r}")
    img = cv2.imdecode(np.frombuffer(png, np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        raise OcrError(f"{table_id}: cannot decode PNG")
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    lay = _layout(table_id, _ocr(img), gray)
    result = OcrResult()
    for i, pn in enumerate(lay.pns, start=1):
        pn_text = _fix_pn(pn.t)
        pn_clean, _ = split_part_number(pn_text)
        cells: list[OcrCell] = []
        for field, raw, conf in _row_cells(table_id, gray, lay, pn):
            err = _parse_error(raw)
            cells.append(
                OcrCell(
                    table_id=table_id,
                    part_number=pn_clean,
                    field=field,
                    raw=raw,
                    conf=conf,
                    parse_error=err,
                )
            )
        row, bad = _build_row(table_id, pn_text, cells, i)
        if row is None and bad is not None:
            result.cells.append(bad)  # row skipped: flags.py escalates the table
            continue
        result.rows.extend([row] if row else [])
        result.cells.extend(cells)
    return result


def ocr_tables(crops: dict[str, bytes]) -> OcrResult:
    """OCR every table in TABLE_IDS order (tables missing from `crops` are skipped)."""
    total = OcrResult()
    for tid in TABLE_IDS:
        if tid in crops:
            r = ocr_table(tid, crops[tid])
            total.rows.extend(r.rows)
            total.cells.extend(r.cells)
    return total
