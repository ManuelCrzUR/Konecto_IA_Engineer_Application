"""Table crop (PNG) -> raw cells, offline, with RapidOCR + row/column geometry.

Port of the benchmark extractor E with one change:
NO text repair. The reference turned 'O' into '0' and guessed thousands
separators; here every raw string goes through normalize.parse_number as is.
A cell that does not parse keeps value None and `parse_error` set, so
flags.py marks it and its table is escalated (never loaded unverified).

Contract:
- Every expected field (incl. motor_power_w) yields an OcrCell; a cell neither pass
  read has raw="" and parse_error="missing".
- OcrCell: one cell as read (table_id, part_number, field, raw, conf, parse_error).
- OcrResult: rows (normalized Actuators; unparsable cells left None) + cells.
- ocr_table(table_id, png) -> OcrResult for one table.
- ocr_tables(crops) -> OcrResult for all tables, in TABLE_IDS order.
Motor Power is a merged cell: its value is copied to every row of its group
(as printed), like the reference.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from dataclasses import field as dc_field
from typing import Any

import cv2
import numpy as np
from pydantic import BaseModel, Field

from app.domain.models import TABLE_IDS, Actuator
from app.ingestion.normalize import (
    NormalizationError,
    check_suffix,
    normalize_row,
    parse_number,
    split_part_number,
)
from app.ingestion.table_meta import TABLE_FIELDS


def _data_fields(table_id: str) -> tuple[str, ...]:
    """Printed columns between the part number and Motor Power (Motor Power is last)."""
    return TABLE_FIELDS[table_id][:-1]


_PN_RE = re.compile(r"\d{3}[A-Z0-9]{3}-[A-Z0-9]{6,9}/?[A-Z]?\*?$")
_NUM_OR_NA = re.compile(r"\d|N/?A")
_NA_ONLY = re.compile(r"N\s*/?\s*A$", re.IGNORECASE)
# The PDF prints thousands with a comma and never uses 3 decimals: 'd.ddd' is a comma
# the OCR read as a dot ('9.700' = 9,700). parse_number would accept it as 9.7, so it is
# rejected here (detection only, no repair) and the cell gets flagged.
_DOT_THOUSANDS = re.compile(r"^\d{1,3}\.\d{3}$")
_CONFIRM_CONF = 0.9  # same threshold as flags.CONF_MIN (flags imports this module)
_COMMA_AREA = 6
_POWER_HEADERS = ("Motor", "Watts", "Power")
_RULE_DARK = 225  # gray level below which a pixel counts as ink
_RULE_FRAC = 0.8  # share of dark pixels across the motor strip that makes a rule


class OcrCell(BaseModel):
    table_id: str
    part_number: str
    field: str
    raw: str
    conf: float
    parse_error: str | None = None


class OcrResult(BaseModel):
    rows: list[Actuator] = Field(default_factory=list)
    cells: list[OcrCell] = Field(default_factory=list)


class OcrError(RuntimeError):
    """The table geometry could not be recovered (e.g. no part numbers found)."""


@dataclass
class _Box:
    x0: float
    y0: float
    x1: float
    y1: float
    t: str
    c: float

    @property
    def cx(self) -> float:
        return (self.x0 + self.x1) / 2

    @property
    def cy(self) -> float:
        return (self.y0 + self.y1) / 2


@dataclass
class _Layout:
    pns: list[_Box]
    pn_right: float
    mx0: float
    pitch: float
    cuts: list[float]
    rules: list[float]
    data: list[_Box]
    power: list[_Box]
    # ids of part-number boxes whose whole row is covered by a merged N/A
    na_rows: set[int] = dc_field(default_factory=set)


_engine: Any = None


def _ocr(img: np.ndarray) -> list[_Box]:
    """Run RapidOCR (built once, lazily: construction is slow)."""
    global _engine
    if _engine is None:
        from rapidocr_onnxruntime import RapidOCR

        _engine = RapidOCR()
    res, _ = _engine(img)
    return [_Box(b[0][0], b[0][1], b[2][0], b[2][1], t, float(c)) for b, t, c in res or []]


def _split_gaps(vals: list[float], n: int) -> list[float]:
    """Cut points at the n-1 widest gaps between sorted x positions."""
    v = sorted(vals)
    gaps = sorted(range(len(v) - 1), key=lambda i: v[i + 1] - v[i], reverse=True)[: n - 1]
    return sorted((v[i] + v[i + 1]) / 2 for i in gaps)


def _rules(gray: np.ndarray, mx0: float, mx1: float, y_from: int) -> list[float]:
    """y of the horizontal rules in the motor-power strip (they bound each power group)."""
    strip = gray[:, int(mx0) - 15 : int(mx1) + 15]
    frac = (strip < _RULE_DARK).mean(1)
    lines: list[list[int]] = []
    for y in range(max(y_from, 0), gray.shape[0]):
        if frac[y] > _RULE_FRAC:
            if lines and y - lines[-1][-1] <= 2:
                lines[-1].append(y)
            else:
                lines.append([y])
    return [float(np.mean(ln)) for ln in lines if len(ln) <= 6]  # thick bands are borders


def _layout(table_id: str, boxes: list[_Box], gray: np.ndarray) -> _Layout:
    pns = sorted((b for b in boxes if _PN_RE.search("".join(b.t.split()))), key=lambda b: b.cy)
    if not pns:
        raise OcrError(f"{table_id}: no part numbers found")
    pn_right = max(b.x1 for b in pns)
    heads = [b for b in boxes if b.t in _POWER_HEADERS and b.cx > pn_right]
    if not heads:
        raise OcrError(f"{table_id}: Motor Power header not found")
    mx0, mx1 = min(b.x0 for b in heads), max(b.x1 for b in heads)
    pitch = float(np.median(np.diff([p.cy for p in pns]))) if len(pns) > 1 else 0.0
    if pitch <= 0:
        raise OcrError(f"{table_id}: cannot estimate row pitch")
    top = pns[0].cy
    data = [b for b in boxes if b.x0 > pn_right and b.cy > top - 25 and b.cx < mx0 - 10]
    n_cols = len(_data_fields(table_id))
    xs = [b.cx for b in data if _NUM_OR_NA.search(b.t) and not _NA_ONLY.match(b.t.strip())]
    if len(xs) < n_cols:
        raise OcrError(f"{table_id}: too few numeric cells to find {n_cols} columns")
    rules = [r for r in _rules(gray, mx0, mx1, int(top - pitch)) if r > top - pitch / 2]
    power = [b for b in boxes if b.cx > mx0 - 10 and b.cy > top - pitch / 2 and b.t != "Watts"]
    na_rows = _na_rows(pns, data, pitch)
    return _Layout(pns, pn_right, mx0, pitch, _split_gaps(xs, n_cols), rules, data, power, na_rows)


def _na_rows(pns: list[_Box], data: list[_Box], pitch: float) -> set[int]:
    """Rows with no number at all, inside a run of such rows that holds a merged 'N/A'.

    The PDF prints one 'N/A' box centred on a block of part numbers (761A..762B in the
    three-phase table), so it lines up with no single row. Rows with no digits and no
    N/A box of their own count as N/A only if the run they belong to contains that box.
    """
    half = pitch * 0.5
    nas = [b for b in data if _NA_ONLY.match(b.t.strip())]
    empty = [not any(abs(b.cy - p.cy) <= half and re.search(r"\d", b.t) for b in data) for p in pns]
    out: set[int] = set()
    i = 0
    while i < len(pns):
        if not empty[i]:
            i += 1
            continue
        j = i
        while j + 1 < len(pns) and empty[j + 1]:
            j += 1
        lo, hi = pns[i].cy - half, pns[j].cy + half
        if any(lo <= b.cy <= hi for b in nas):
            out.update(id(p) for p in pns[i : j + 1])
        i = j + 1
    return out


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


def _digits(text: str) -> str:
    return re.sub(r"\D", "", text)


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


def _fix_pn(text: str) -> str:
    """Part-number suffix after the hyphen is digits plus one 'C' (e.g. 11330C00): a letter
    'O' there is a misread zero. Not a value repair: check_suffix still verifies the result
    against the table's expected suffix, so a wrong guess is rejected, never loaded.
    """
    head, sep, tail = "".join(text.split()).partition("-")
    return head + sep + tail.replace("O", "0")


def _parse_error(raw: str) -> str | None:
    """None if `raw` is a strictly valid cell, else why not."""
    if not raw.strip():
        return "missing"
    if _DOT_THOUSANDS.match(raw.strip()):
        return f"thousands separator read as a dot: {raw!r}"
    try:
        parse_number(raw)
    except NormalizationError as exc:
        return str(exc)
    return None


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
