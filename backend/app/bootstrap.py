"""ensure_data(): the self-healing data chain. Runs at API, CLI and ingest start.

Cascade:
1. actuators.json valid and Postgres row count == its rows   -> source "db" (no-op)
2. actuators.json valid, DB differs                          -> upsert, source "json"
3. actuators.json MISSING (not corrupt) and Postgres holds the full catalog
   (rows rebuilt from the DB pass assert_valid and per-table counts equal
   EXPECTED_ROWS)                                            -> JSON rebuilt from
   the DB (force=False), source "db". No OCR / paid vision call.
4. Otherwise PDF -> extract_catalog -> write JSON -> upsert  -> source "pdf"
5. Any validation failure aborts with a clear message; nothing doubtful is loaded.

Decisions:
- A JSON that is truncated, not a Catalog, or parses but fails validate.assert_valid
  is CORRUPT: the data is re-extracted from the PDF. Only after extraction succeeds
  is the bad file MOVED ASIDE to actuators.json.corrupt-<UTC YYYYmmddTHHMMSSZ>
  (never deleted, WARNING logged with both paths) and the new catalog is written
  with force=False. If extraction fails, the bad file is left untouched and the
  error propagates (database not touched). actuators.json is never overwritten.
- "db" in step 1 is decided by row count equality only (cheap).
- If the DB has MORE rows than the JSON (stale extras), actuators and catalog_tables
  are emptied and reloaded in one transaction (reported as "json").
  Fewer rows (partial load) just upserts. Upserts are idempotent.
"""

from __future__ import annotations

import logging
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

import psycopg
from pydantic import BaseModel

from app.db import actuators_repo
from app.db.connection import apply_schema
from app.domain.models import EXPECTED_ROWS, TABLE_IDS, Catalog
from app.ingestion import pipeline
from app.ingestion.pipeline import Escalator
from app.ingestion.store_json import CatalogFileError, read_catalog, write_catalog
from app.ingestion.table_meta import TABLE_META
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


def _move_aside(json_path: Path) -> Path:
    """Rename a bad catalog to <name>.corrupt-<UTC timestamp>; never deletes it."""
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    dest = json_path.with_name(f"{json_path.name}.corrupt-{stamp}")
    json_path.rename(dest)
    logger.warning("Corrupt catalog moved aside: %s -> %s", json_path, dest)
    return dest


def _rebuild_from_db(conn: psycopg.Connection) -> Catalog | None:
    """Catalog from Postgres if it holds the complete, valid catalog, else None."""
    if actuators_repo.count(conn) == 0:
        conn.commit()
        return None
    rows = actuators_repo.find_like(conn, "", limit=10_000)
    conn.commit()
    order = {t: i for i, t in enumerate(TABLE_IDS)}
    rows.sort(key=lambda a: (order[a.table_id], a.row_index if a.row_index is not None else 0))
    counts = Counter(a.table_id for a in rows)
    if dict(counts) != EXPECTED_ROWS:
        logger.info(
            "Database holds a partial catalog (%s); not rebuilding JSON from it", dict(counts)
        )
        return None
    try:
        assert_valid(rows)
    except ValidationFailed as exc:
        logger.warning("Database rows fail validation, falling back to PDF: %s", exc)
        return None
    return Catalog(tables=list(TABLE_META), rows=rows)


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

    if not corrupt:
        rebuilt = _rebuild_from_db(conn)
        if rebuilt is not None:
            write_catalog(rebuilt, json_path, force=False)
            logger.info("Rebuilt %s from the database (%d rows)", json_path, len(rebuilt.rows))
            return DataStatus(source="db", rows=len(rebuilt.rows))

    logger.info("Extracting catalog from %s", pdf_path)
    extracted = pipeline.extract_catalog(pdf_path, escalator)
    if corrupt:
        _move_aside(json_path)
    write_catalog(extracted, json_path, force=False)
    logger.info("Wrote %s", json_path)
    current = actuators_repo.count(conn)
    conn.commit()
    _load(conn, extracted, replace=current > len(extracted.rows))
    return DataStatus(source="pdf", rows=len(extracted.rows))
