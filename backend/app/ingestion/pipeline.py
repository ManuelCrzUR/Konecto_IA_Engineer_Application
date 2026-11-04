"""PDF -> Catalog. Orchestrates crops -> ocr -> normalize -> flags -> escalate -> validate.

Contract:
- Escalator: callable(table_id, crop_png_bytes) -> list[dict] of bench-format rows
  for that whole table (vision model). Injected so tests can pass a fixture.
- extract_catalog(pdf_path, escalator=None) -> Catalog:
  1. RapidOCR on each table crop (offline).
  2. Flag cells (conf < 0.9, leading zero, validator failure).
  3. Tables with >= 1 flagged cell are re-read whole by `escalator`.
     If escalator is None and something is flagged -> raise ExtractionError
     listing the flagged cells (never load doubtful data).
  4. validate() on the result; raise ExtractionError on failure.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from app.domain.models import Catalog

Escalator = Callable[[str, bytes], list[dict]]


class ExtractionError(RuntimeError):
    """Extraction produced doubtful data; message lists the offending cells."""


def extract_catalog(pdf_path: Path, escalator: Escalator | None = None) -> Catalog:
    raise NotImplementedError
