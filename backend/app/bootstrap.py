"""ensure_data(): the self-healing data chain. Runs at API, CLI and ingest start.

1. Postgres row count == rows in a valid actuators.json   -> source "db" (no-op)
2. Else actuators.json exists and validates               -> upsert, source "json"
3. Else PDF -> extract_catalog -> write JSON -> upsert     -> source "pdf"
4. Any validation failure aborts with a clear message; nothing doubtful is loaded.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import psycopg
from pydantic import BaseModel

from app.ingestion.pipeline import Escalator

BACKEND_DIR = Path(__file__).resolve().parents[1]
DEFAULT_JSON = BACKEND_DIR / "data" / "processed" / "actuators.json"
DEFAULT_PDF = BACKEND_DIR / "data" / "raw" / "series_76_electric_data.pdf"


class DataStatus(BaseModel):
    source: Literal["db", "json", "pdf"]
    rows: int


def ensure_data(
    conn: psycopg.Connection,
    json_path: Path = DEFAULT_JSON,
    pdf_path: Path = DEFAULT_PDF,
    escalator: Escalator | None = None,
) -> DataStatus:
    raise NotImplementedError
