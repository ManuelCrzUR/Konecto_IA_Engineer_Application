"""OCR primitives: the cell/result models, the RapidOCR call and text clean-up helpers.

Contract:
- OcrCell: one cell as read (table_id, part_number, field, raw, conf, parse_error).
- OcrResult: rows (normalized Actuators; unparsable cells left None) + cells.
- _ocr(img BGR array) -> list[_Box] (RapidOCR built once, lazily).
- _fix_pn(text) -> part number with a misread 'O' in the suffix turned into '0'.
- _parse_error(raw) -> None if the cell is strictly valid, else the reason.
No text repair of values: every raw string goes to normalize.parse_number as is.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

import numpy as np
from pydantic import BaseModel, Field

from app.domain.models import Actuator
from app.ingestion.normalize import NormalizationError, parse_number
from app.ingestion.table_meta import TABLE_FIELDS


def _data_fields(table_id: str) -> tuple[str, ...]:
    """Printed columns between the part number and Motor Power (Motor Power is last)."""
    return TABLE_FIELDS[table_id][:-1]


_NUM_OR_NA = re.compile(r"\d|N/?A")
_NA_ONLY = re.compile(r"N\s*/?\s*A$", re.IGNORECASE)
# The PDF prints thousands with a comma and never uses 3 decimals: 'd.ddd' is a comma
# the OCR read as a dot ('9.700' = 9,700). parse_number would accept it as 9.7, so it is
# rejected here (detection only, no repair) and the cell gets flagged.
_DOT_THOUSANDS = re.compile(r"^\d{1,3}\.\d{3}$")


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


_engine: Any = None


def _ocr(img: np.ndarray) -> list[_Box]:
    """Run RapidOCR (built once, lazily: construction is slow)."""
    global _engine
    if _engine is None:
        from rapidocr_onnxruntime import RapidOCR

        _engine = RapidOCR()
    res, _ = _engine(img)
    return [_Box(b[0][0], b[0][1], b[2][0], b[2][1], t, float(c)) for b, t, c in res or []]


def _digits(text: str) -> str:
    return re.sub(r"\D", "", text)


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
