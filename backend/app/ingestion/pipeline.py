"""PDF -> Catalog. Orchestrates crops -> ocr -> validate -> flags -> escalate -> validate.

Contract:
- Escalator: callable(table_id, crop_png_bytes) -> list[Actuator] for that whole
  table (vision re-read, already normalized). Injected so tests pass a fixture.
- extract_catalog(pdf_path, escalator=None) -> Catalog:
  1. crops.crop_tables, then ocr.ocr_tables (offline RapidOCR).
  2. validate.validate_rows on the OCR rows; flags.flag_cells(cells, issues).
  3. Each table in flags.tables_to_escalate(flags, issues, cells) (flagged tables, plus
     tables with table-level validator errors such as row_count/unique_pn) is replaced WHOLE by escalator(...).
     If escalator is None and something is flagged -> ExtractionError listing
     the flagged cells (never load doubtful data).
  4. validate.assert_valid on the final rows (ValidationFailed -> ExtractionError).
  5. Catalog.tables come from table_meta.TABLE_META (titles + printed notes,
     transcribed once from this PDF; OCR does not read the notes).
- ExtractionReport (returned by extract_with_report) says which tables were
  escalated and why, for logs and the README.
"""

from __future__ import annotations

import tempfile
from collections.abc import Callable
from pathlib import Path

from pydantic import BaseModel, Field

from app.domain.models import TABLE_IDS, Actuator, Catalog
from app.ingestion.crops import crop_tables
from app.ingestion.flags import Flag, flag_cells, tables_to_escalate
from app.ingestion.ocr import ocr_tables
from app.ingestion.table_meta import TABLE_META
from app.ingestion.validate import Issue, ValidationFailed, assert_valid, validate_rows

Escalator = Callable[[str, bytes], list[Actuator]]

MAX_LISTED_CELLS = 20
HINT = (
    "Set LLM_API_KEY and EXTRACT_LLM_MODEL (vision model) so flagged tables can be "
    "re-read by vision, or fix data/processed/actuators.json by hand."
)


class ExtractionError(RuntimeError):
    """Extraction produced doubtful data; message lists the offending cells."""


class ExtractionReport(BaseModel):
    escalated: list[str] = Field(default_factory=list)
    flagged_cells: int = 0
    warnings: list[str] = Field(default_factory=list)


def _describe(flags: list[Flag]) -> str:
    shown = [
        f"{f.table_id}/{f.part_number}/{f.field} raw={f.raw!r}" for f in flags[:MAX_LISTED_CELLS]
    ]
    more = len(flags) - len(shown)
    suffix = f" (+{more} more)" if more > 0 else ""
    return "; ".join(shown) + suffix


def _table_errors(issues: list[Issue]) -> str:
    msgs = [i.message for i in issues if i.level == "error" and i.field in (None, "part_number")]
    return f" [table-level errors: {'; '.join(msgs[:MAX_LISTED_CELLS])}]" if msgs else ""


def extract_with_report(
    pdf_path: Path, escalator: Escalator | None = None
) -> tuple[Catalog, ExtractionReport]:
    with tempfile.TemporaryDirectory(prefix="series76_crops_") as work:
        crops = crop_tables(pdf_path, Path(work))
    ocr = ocr_tables(crops)
    issues = validate_rows(ocr.rows)
    flags = flag_cells(ocr.cells, issues)
    to_escalate = tables_to_escalate(flags, issues, ocr.cells)
    report = ExtractionReport(escalated=list(to_escalate), flagged_cells=len(flags))

    rows = list(ocr.rows)
    if to_escalate:
        if escalator is None:
            raise ExtractionError(
                f"{len(flags)} doubtful cell(s) in {', '.join(to_escalate)} and no escalator "
                f"available: {_describe(flags)}{_table_errors(issues)}. {HINT}"
            )
        for table_id in to_escalate:
            new_rows = escalator(table_id, crops[table_id])
            rows = [r for r in rows if r.table_id != table_id] + list(new_rows)

    order = {t: i for i, t in enumerate(TABLE_IDS)}
    rows.sort(key=lambda r: (order[r.table_id], r.row_index or 0))
    try:
        warnings = assert_valid(rows)
    except ValidationFailed as exc:
        detail = "; ".join(i.message for i in exc.issues[:MAX_LISTED_CELLS])
        context = f" Flagged cells: {_describe(flags)}." if flags else ""
        raise ExtractionError(
            f"extracted data failed validation: {detail}.{context} {HINT}"
        ) from exc
    report.warnings = [w.message for w in warnings]
    return Catalog(tables=list(TABLE_META), rows=rows), report


def extract_catalog(pdf_path: Path, escalator: Escalator | None = None) -> Catalog:
    """extract_with_report without the report."""
    return extract_with_report(pdf_path, escalator)[0]
