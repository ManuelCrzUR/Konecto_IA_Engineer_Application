"""Read/write access to `actuators` and `catalog_tables`. Parameterized SQL only.

Knows nothing about the agent or the LLM. Every function takes an open
psycopg connection; the caller owns transactions except where noted.
Returned numbers are exactly the stored values (numeric -> float).
"""

from __future__ import annotations

import psycopg

from app.domain.models import Actuator, Catalog
from app.domain.search import CatalogSummary, NoMatchReport, SearchFilters


def count(conn: psycopg.Connection) -> int:
    """Number of rows in `actuators`."""
    raise NotImplementedError


def upsert_catalog(conn: psycopg.Connection, catalog: Catalog) -> int:
    """Upsert catalog_tables then actuators in ONE transaction
    (INSERT ... ON CONFLICT (part_number) DO UPDATE). Writes has_data.
    Idempotent: running it twice leaves the same rows. Returns rows written."""
    raise NotImplementedError


def delete_all(conn: psycopg.Connection) -> None:
    """Remove all actuators and catalog_tables (used by `ingest.py --reset`)."""
    raise NotImplementedError


def get_by_pn(conn: psycopg.Connection, part_number: str) -> Actuator | None:
    """Exact match on the stored part_number (caller normalizes the input)."""
    raise NotImplementedError


def find_like(conn: psycopg.Connection, fragment: str, limit: int = 10) -> list[Actuator]:
    """Part numbers that start with `fragment` (e.g. '764' or '764A00'),
    ordered by part_number. Used for partial input and suggestions."""
    raise NotImplementedError


def search(conn: psycopg.Connection, filters: SearchFilters, limit: int = 10) -> list[Actuator]:
    """Rows meeting every filter (semantics in SearchFilters docstring),
    tightest fit first. Empty list when nothing matches."""
    raise NotImplementedError


def count_matches(conn: psycopg.Connection, filters: SearchFilters) -> int:
    """Total rows meeting the filters (no limit)."""
    raise NotImplementedError


def diagnose_no_match(conn: psycopg.Connection, filters: SearchFilters) -> NoMatchReport:
    """Called when search() is empty: which filters block, whether the
    combination exists in the catalog at all, and the closest available value
    per blocking numeric filter (max torque, min speed, max duty)."""
    raise NotImplementedError


def catalog_summary(conn: psycopg.Connection) -> CatalogSummary:
    """Distinct combinations, torque ranges, row totals."""
    raise NotImplementedError


def table_notes(conn: psycopg.Connection, table_ids: list[str]) -> dict[str, list[str]]:
    """Printed notes per table_id (tolerances, IEC 60034-1, hazardous area, CSA)."""
    raise NotImplementedError
