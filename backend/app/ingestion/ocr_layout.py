"""Table geometry: part-number rows, data columns, motor-power groups and N/A rows.

Contract:
- _layout(table_id, boxes, gray) -> _Layout (raises OcrError if the geometry cannot be
  recovered: no part numbers, no Motor Power header, no row pitch, too few numeric cells).
- _na_rows(pns, data, pitch) -> ids of part-number boxes covered by a merged 'N/A'.
Pure geometry over OCR boxes and the grayscale image; no re-reads, no parsing.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from dataclasses import field as dc_field

import numpy as np

from app.ingestion.ocr_boxes import (
    _NA_ONLY,
    _NUM_OR_NA,
    OcrError,
    _Box,
    _data_fields,
)

_PN_RE = re.compile(r"\d{3}[A-Z0-9]{3}-[A-Z0-9]{6,9}/?[A-Z]?\*?$")
_COMMA_AREA = 6
_POWER_HEADERS = ("Motor", "Watts", "Power")
_RULE_DARK = 225  # gray level below which a pixel counts as ink
_RULE_FRAC = 0.8  # share of dark pixels across the motor strip that makes a rule


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
