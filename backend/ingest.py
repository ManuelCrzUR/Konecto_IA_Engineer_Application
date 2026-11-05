"""CLI for loading the actuator catalog into Postgres.

Usage (from backend/):
    uv run python ingest.py                 # ensure_data: DB -> JSON -> PDF cascade
    uv run python ingest.py --reset         # empty the tables first, then ensure_data
    uv run python ingest.py --from-pdf --force   # re-extract the PDF, overwrite the JSON

This file only parses arguments, wires dependencies and prints a summary.
The logic lives in app.bootstrap, app.ingestion and app.db.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import psycopg

from app.bootstrap import DEFAULT_JSON, DEFAULT_PDF, DataStatus, ensure_data
from app.db.actuators_repo import delete_all, upsert_catalog
from app.db.connection import apply_schema, connect, database_url
from app.ingestion.crops import CropError
from app.ingestion.escalate import EscalationError, make_vision_escalator
from app.ingestion.ocr import OcrError
from app.ingestion.pipeline import Escalator, ExtractionError, extract_with_report
from app.ingestion.store_json import CatalogFileError, write_catalog
from app.ingestion.validate import ValidationFailed
from app.llm import LLMConfigError

logger = logging.getLogger("ingest")

EXIT_OK = 0
EXIT_FAILED = 1
EXIT_USAGE = 2

ESCALATION_WARNING = (
    "Escalation is ON: flagged tables may be re-read by the paid model configured in "
    "EXTRACT_LLM_MODEL. Pass --no-escalation to run offline only."
)


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Load Series 76 actuator data into Postgres.")
    parser.add_argument("--reset", action="store_true", help="delete all rows before loading")
    parser.add_argument(
        "--from-pdf",
        action="store_true",
        help="re-extract from the PDF even if actuators.json exists",
    )
    parser.add_argument(
        "--force", action="store_true", help="allow overwriting actuators.json (with --from-pdf)"
    )
    parser.add_argument(
        "--no-escalation",
        action="store_true",
        help="do not call the vision model; fail if any table is flagged",
    )
    parser.add_argument("--json", type=Path, default=DEFAULT_JSON, help="path to actuators.json")
    parser.add_argument("--pdf", type=Path, default=DEFAULT_PDF, help="path to the source PDF")
    parser.add_argument("--database-url", default=None, help="Postgres URL (default: DATABASE_URL)")
    return parser.parse_args(argv)


def _run_ensure(args: argparse.Namespace, escalator: Escalator | None) -> int:
    if escalator is not None and not args.json.exists():
        logger.warning(ESCALATION_WARNING)
    conn = connect(args.database_url or database_url())
    try:
        if args.reset:
            apply_schema(conn)  # a brand-new database has no tables to clear yet
            delete_all(conn)
        status = ensure_data(conn, json_path=args.json, pdf_path=args.pdf, escalator=escalator)
    finally:
        conn.close()
    print(status.summary())
    return EXIT_OK


def _run_from_pdf(args: argparse.Namespace, escalator: Escalator | None) -> int:
    if args.json.exists() and not args.force:
        print("error: actuators.json exists; pass --force to overwrite", file=sys.stderr)
        return EXIT_USAGE
    if escalator is not None:
        logger.warning(ESCALATION_WARNING)
    catalog, report = extract_with_report(args.pdf, escalator)
    if report.escalated:
        logger.info("escalated tables: %s", ", ".join(report.escalated))
    write_catalog(catalog, args.json, force=args.force)
    conn = connect(args.database_url or database_url())
    try:
        apply_schema(conn)
        # Replace, not merge: a part number dropped by the new extraction must not
        # linger. One transaction, so a failure keeps the previous rows.
        with conn.transaction():
            delete_all(conn)
            upsert_catalog(conn, catalog)
    finally:
        conn.close()
    print(DataStatus(source="pdf", rows=len(catalog.rows)).summary())
    return EXIT_OK


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO)
    args = _parse_args(argv)
    escalator: Escalator | None = None if args.no_escalation else make_vision_escalator()
    try:
        if args.from_pdf:
            return _run_from_pdf(args, escalator)
        return _run_ensure(args, escalator)
    except (
        ExtractionError,
        ValidationFailed,
        CatalogFileError,
        EscalationError,
        CropError,
        OcrError,
        LLMConfigError,
        FileExistsError,
    ) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_FAILED
    except psycopg.OperationalError as exc:
        print(
            f"error: cannot reach Postgres ({exc}). Is it running? Try: docker compose up -d db",
            file=sys.stderr,
        )
        return EXIT_FAILED


if __name__ == "__main__":
    sys.exit(main())
