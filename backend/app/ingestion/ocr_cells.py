"""Per-cell reads: re-OCR of missing or doubtful cells and row assembly.

Contract:
- _row_cells(table_id, gray, lay, pn) -> [(field, raw, conf)] for every expected field,
  incl. Motor Power; a cell neither pass read has raw="" and conf 0 (-> "missing").
- _confirm(...) -> (raw, conf): a second read may settle punctuation or confidence of a
  doubtful cell, never change a digit.
- _build_row(table_id, raw_pn, cells, idx) -> (Actuator | None, error OcrCell | None).
Motor Power is a merged cell: its value is copied to every row of its group (as printed).
"""

from __future__ import annotations

import cv2
import numpy as np

from app.domain.models import Actuator
from app.ingestion.normalize import (
    NormalizationError,
    check_suffix,
    normalize_row,
    split_part_number,
)
from app.ingestion.ocr_boxes import (
    _DOT_THOUSANDS,
    _NA_ONLY,
    OcrCell,
    _Box,
    _data_fields,
    _digits,
    _ocr,
    _parse_error,
)
from app.ingestion.ocr_layout import _Layout

_CONFIRM_CONF = 0.9  # same threshold as flags.CONF_MIN (flags imports this module)
_COMMA_AREA = 6


def _refill(gray: np.ndarray, lay: _Layout, pn: _Box, ci: int, scale: int = 2) -> _Box | None:
    """Re-OCR one cell on its own, upscaled (the full-table pass often misses it)."""
    lo = lay.cuts[ci - 1] if ci > 0 else lay.pn_right + 5
    hi = lay.cuts[ci] if ci < len(lay.cuts) else lay.mx0 - 12
    y0, y1 = int(pn.cy - lay.pitch * 0.45), int(pn.cy + lay.pitch * 0.45)
    crop = cv2.copyMakeBorder(
        gray[max(y0, 0) : y1, int(lo) : int(hi)], 20, 20, 30, 30, cv2.BORDER_CONSTANT, value=255
    )
    crop = cv2.resize(crop, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    found = _ocr(cv2.cvtColor(crop, cv2.COLOR_GRAY2BGR))
    if not found:
        return None
    return _Box(0, 0, 0, 0, " ".join(b.t for b in found), min(b.c for b in found))


def _separator_is_comma(gray: np.ndarray, box: _Box) -> bool | None:
    """Look at the ink between the digit groups of an 'd.ddd' cell: a printed comma leaves a
    blob about twice the area of a dot (>= _COMMA_AREA px on the 2x crop). None if the
    blob cannot be isolated (then the cell stays flagged).
    """
    x0, y0, x1, y1 = (int(v) for v in (box.x0, box.y0, box.x1, box.y1))
    crop = gray[max(y0 - 3, 0) : y1 + 4, max(x0 - 3, 0) : x1 + 3]
    _, ink = cv2.threshold(crop, 170, 255, cv2.THRESH_BINARY_INV)
    n, _, st, _ = cv2.connectedComponentsWithStats(ink)
    digits = [st[i] for i in range(1, n) if st[i][3] >= 10]
    if len(digits) < 2:
        return None
    lo, hi = min(d[0] for d in digits), max(d[0] + d[2] for d in digits)
    base = float(np.median([d[1] + d[3] for d in digits]))
    cand = [
        st[i]
        for i in range(1, n)
        if st[i][3] <= 6
        and st[i][2] <= 6
        and st[i][4] >= 2
        and lo < st[i][0] < hi
        and st[i][1] + st[i][3] >= base - 4
        and st[i][1] > base - 12
    ]
    if len(cand) != 1:
        return None
    return bool(cand[0][4] >= _COMMA_AREA)


def _confirm(
    gray: np.ndarray, lay: _Layout, pn: _Box, ci: int, raw: str, conf: float, box: _Box | None
) -> tuple[str, float]:
    """Second, independent read of a doubtful cell (low confidence, or 'd.ddd' where the
    comma was read as a dot). The new read replaces the first only if it is strictly valid,
    confident, and has the SAME digits: it can settle punctuation and confidence, never
    change a digit. Anything else keeps the first read, so flags.py still flags it.
    """
    if conf >= _CONFIRM_CONF and not _DOT_THOUSANDS.match(raw.strip()):
        return raw, conf
    if box is not None and _DOT_THOUSANDS.match(raw.strip()) and _separator_is_comma(gray, box):
        raw = raw.strip().replace(".", ",")
        if conf >= _CONFIRM_CONF:
            return raw, conf
    for scale in (2, 3):
        again = _refill(gray, lay, pn, ci, scale)
        if again is None or again.c < _CONFIRM_CONF or _digits(again.t) != _digits(raw):
            continue
        if _parse_error(again.t) is None:
            return again.t, again.c
        if _parse_error(raw) is None:  # same digits; punctuation already settled above
            return raw, again.c
    return raw, conf


def _row_cells(
    table_id: str, gray: np.ndarray, lay: _Layout, pn: _Box
) -> list[tuple[str, str, float]]:
    """(field, raw text, min confidence) for each cell of the row, incl. Motor Power."""
    fields = _data_fields(table_id)
    if id(pn) in lay.na_rows:
        na = [b for b in lay.data if _NA_ONLY.match(b.t.strip())]
        conf = min(b.c for b in na)
        return [(f, "N/A", conf) for f in (*fields, "motor_power_w")]

    def col(b: _Box) -> int:
        return sum(b.cx > c for c in lay.cuts)

    def group(y: float) -> int:
        return sum(y > r for r in lay.rules)

    by_col: dict[int, list[_Box]] = {}
    for b in lay.data:
        if abs(b.cy - pn.cy) <= lay.pitch * 0.5 and not b.t.endswith("/A") and b is not pn:
            by_col.setdefault(col(b), []).append(b)
    out: list[tuple[str, str, float]] = []
    # Every expected field yields a cell: one missed by both passes gets raw="" and
    # conf 0 (-> parse_error "missing" -> flagged). No "whole row is N/A" guess.
    for ci, field in enumerate(fields):
        bs = sorted(by_col.get(ci, []), key=lambda b: b.x0) or None
        if bs is None:
            filled = _refill(gray, lay, pn, ci)
            bs = [filled] if filled else None
        if bs:
            raw, conf = " ".join(b.t for b in bs), min(b.c for b in bs)
            single = bs[0] if len(bs) == 1 and bs[0].x1 > bs[0].x0 else None
            out.append((field, *_confirm(gray, lay, pn, ci, raw, conf, single)))
        else:
            out.append((field, "", 0.0))
    power = [b for b in lay.power if group(b.cy) == group(pn.cy)]
    if power:
        out.append(("motor_power_w", " ".join(b.t for b in power), min(b.c for b in power)))
    else:
        out.append(("motor_power_w", "", 0.0))
    return out


def _build_row(
    table_id: str, raw_pn: str, cells: list[OcrCell], idx: int
) -> tuple[Actuator | None, OcrCell | None]:
    """Strict row from raw cells (unparsable ones -> None). Bad PN -> (None, error cell)."""
    pn, _ = split_part_number(raw_pn)
    values = {c.field: (None if c.parse_error else c.raw) for c in cells}
    try:
        check_suffix(table_id, pn)
        return normalize_row(table_id, raw_pn, values, row_index=idx), None
    except NormalizationError as exc:
        return None, OcrCell(
            table_id=table_id,
            part_number=pn,
            field="part_number",
            raw=raw_pn,
            conf=0.0,
            parse_error=str(exc),
        )
