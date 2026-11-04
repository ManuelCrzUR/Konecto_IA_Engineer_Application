"""Which OCR cells are doubtful, and which tables must be re-read by vision.

Rule (benchmark REPORT, flag_cells.py). A cell is flagged if ANY holds:
1. low_conf:      conf < CONF_MIN (0.9)
2. leading_zero:  raw text matches ^0\\d  (e.g. '096', '06'; '0.7' does not)
3. validator:     validate.py reported an error on that (part_number, field)
4. unparsable:    the cell has parse_error (strict normalize rejected it)
A table is escalated WHOLE (row alignment errors are table-wide) if ANY holds:
a. it has >= 1 flagged cell;
b. (tables_to_escalate(flags, issues)) it has an error-level validator issue whose
   (part_number, field) matches no OCR cell: table-level errors such as row_count
   (no part number) or unique_pn, which can never become a cell flag. On the benchmark document: 14 of 869 cells, tables T1 T2 T3 T7.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from typing import Literal

from pydantic import BaseModel

from app.ingestion.ocr import OcrCell
from app.ingestion.validate import Issue

CONF_MIN = 0.9
_LEADING_ZERO = re.compile(r"^0\d")
Reason = Literal["low_conf", "leading_zero", "validator", "unparsable"]


class Flag(BaseModel):
    table_id: str
    part_number: str
    field: str
    raw: str
    reasons: list[Reason]


def flag_cells(cells: list[OcrCell], issues: list[Issue]) -> list[Flag]:
    """One Flag per doubtful cell (reasons combined), in input order."""
    bad = {(i.part_number, i.field) for i in issues if i.level == "error"}
    flags: list[Flag] = []
    for c in cells:
        reasons: list[Reason] = []
        if c.conf < CONF_MIN:
            reasons.append("low_conf")
        if _LEADING_ZERO.match("".join(c.raw.split())):
            reasons.append("leading_zero")
        if (c.part_number, c.field) in bad:
            reasons.append("validator")
        if c.parse_error is not None:
            reasons.append("unparsable")
        if reasons:
            flags.append(
                Flag(
                    table_id=c.table_id,
                    part_number=c.part_number,
                    field=c.field,
                    raw=c.raw,
                    reasons=reasons,
                )
            )
    return flags


def tables_to_escalate(
    flags: list[Flag], issues: Sequence[Issue] = (), cells: Sequence[OcrCell] = ()
) -> list[str]:
    """Distinct table_ids to re-read, sorted: tables with flags (rule a), plus tables with
    an error-level issue matching no cell in `cells` by (part_number, field) (rule b).
    """
    tables = {f.table_id for f in flags}
    known = {(c.part_number, c.field) for c in cells}
    for i in issues:
        if i.level == "error" and i.table_id and (i.part_number, i.field) not in known:
            tables.add(i.table_id)
    return sorted(tables)
