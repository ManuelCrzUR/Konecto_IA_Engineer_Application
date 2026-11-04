"""ensure_data(): the self-healing data chain. Runs at API, CLI and ingest start.

1. Postgres row count == rows in a valid actuators.json   -> source "db" (no-op)
2. Else actuators.json exists and validates               -> upsert, source "json"
3. Else PDF -> extract_catalog -> write JSON -> upsert     -> source "pdf"
4. Any validation failure aborts with a clear message; nothing doubtful is loaded.

Decisions:
- A JSON that is truncated, not a Catalog, or parses but fails validate.assert_valid
  is treated as CORRUPT: it is logged and the data is re-extracted from the PDF, and
  the file is rewritten with force=True (the only case where we overwrite a file).
  A MISSING JSON is written with force=False. If re-extraction also fails, the error
  propagates and the database is not touched.
- "db" is decided by row count equality only (cheap); values are not compared.
- If the DB has MORE rows than the JSON (stale extras), actuators and catalog_tables
  are emptied and reloaded in one transaction (reported as "json").
  Fewer rows (partial load) just upserts. Upserts are idempotent.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Literal

import psycopg
from pydantic import BaseModel

from app.db import actuators_repo
from app.db.connection import apply_schema
from app.domain.models import Catalog
from app.ingestion import pipeline
from app.ingestion.pipeline import Escalator
from app.ingestion.store_json import CatalogFileError, read_catalog, write_catalog
from app.ingestion.validate import ValidationFailed, assert_valid

logger = logging.getLogger("series76.bootstrap")

BACKEND_DIR = Path(__file__).resolve().parents[1]
DEFAULT_JSON = BACKEND_DIR / "data" / "processed" / "actuators.json"
DEFAULT_PDF = BACKEND_DIR / "data" / "raw" / "series_76_electric_data.pdf"


class DataStatus(BaseModel):
    source: Literal["db", "json", "pdf"]
    rows: int


def _load_valid_json(json_path: Path) -> tuple[Catalog | None, bool]:
    """(catalog, corrupt). catalog is None when missing or unusable."""
    try:
        catalog = read_catalog(json_path)
    except CatalogFileError as exc:
        logger.warning("Catalog file unusable, will re-extract from PDF: %s", exc)
        return None, True
    if catalog is None:
        logger.info("Catalog file %s not found", json_path)
        return None, False
    try:
        for w in assert_valid(catalog.rows):
            logger.warning("Catalog file warning: %s", w.message)
    except ValidationFailed as exc:
        logger.warning(
            "Catalog file %s fails validation, will re-extract from PDF: %s", json_path, exc
        )
        return None, True
    return catalog, False


def _load(conn: psycopg.Connection, catalog: Catalog, replace: bool) -> None:
    with conn.transaction():
        if replace:
            actuators_repo.delete_all(conn)
        actuators_repo.upsert_catalog(conn, catalog)
    conn.commit()


def ensure_data(
    conn: psycopg.Connection,
    json_path: Path = DEFAULT_JSON,
    pdf_path: Path = DEFAULT_PDF,
    escalator: Escalator | None = None,
) -> DataStatus:
    apply_schema(conn)
    catalog, corrupt = _load_valid_json(json_path)

    if catalog is not None:
        expected = len(catalog.rows)
        current = actuators_repo.count(conn)
        conn.commit()
        if current == expected:
            logger.info("Database already holds %d rows; nothing to do", current)
            return DataStatus(source="db", rows=current)
        logger.info("Loading %d rows from %s (db had %d)", expected, json_path, current)
        _load(conn, catalog, replace=current > expected)
        return DataStatus(source="json", rows=expected)

    logger.info("Extracting catalog from %s", pdf_path)
    extracted = pipeline.extract_catalog(pdf_path, escalator)
    write_catalog(extracted, json_path, force=corrupt)
    logger.info("Wrote %s", json_path)
    current = actuators_repo.count(conn)
    conn.commit()
    _load(conn, extracted, replace=current > len(extracted.rows))
    return DataStatus(source="pdf", rows=len(extracted.rows))
