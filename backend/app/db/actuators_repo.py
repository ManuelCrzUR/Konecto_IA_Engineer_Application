"""Read/write access to `actuators` and `catalog_tables`. Parameterized SQL only.

Knows nothing about the agent or the LLM. Every function takes an open
psycopg connection; the caller owns transactions except where noted.
Returned numbers are exactly the stored values (numeric -> float).

Dynamic column names come only from the fixed whitelists below, wrapped in
psycopg.sql.Identifier; every value travels as a bound parameter.
"""

from __future__ import annotations

from typing import Any

import psycopg
from psycopg import sql
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from app.db.search_sql import (
    FILTERS,
    NUMERIC,
    TORQUE,
    closest_query,
    ident,
    order_by,
    where,
)
from app.domain.models import Actuator, Catalog
from app.domain.search import CatalogSummary, NoMatchReport, SearchFilters

_COLS = list(Actuator.model_fields)  # static column list, same names as the table
_COLS_SQL = sql.SQL(", ").join(sql.Identifier(c) for c in _COLS)


def _rows(cur: psycopg.Cursor[Any]) -> list[Actuator]:
    return [Actuator.model_validate(r) for r in cur.fetchall()]


def _cur(conn: psycopg.Connection) -> psycopg.Cursor[Any]:
    """Dict-row cursor regardless of the connection's own row factory."""
    return conn.cursor(row_factory=dict_row)


def _scalar(
    conn: psycopg.Connection, query: sql.Composed | sql.SQL | str, params: list[Any]
) -> Any:
    row = _cur(conn).execute(query, params).fetchone()
    return next(iter(row.values())) if row else None


def _count_where(conn: psycopg.Connection, cond: sql.Composable, params: list[Any]) -> int:
    query = sql.SQL("SELECT count(*) FROM actuators WHERE {}").format(cond)
    return int(_scalar(conn, query, params))


# ---- public API -------------------------------------------------------------
def count(conn: psycopg.Connection) -> int:
    """Number of rows in `actuators`."""
    return int(_scalar(conn, sql.SQL("SELECT count(*) FROM actuators"), []))


def upsert_catalog(conn: psycopg.Connection, catalog: Catalog) -> int:
    """Upsert catalog_tables then actuators in ONE transaction
    (INSERT ... ON CONFLICT (part_number) DO UPDATE). has_data is a generated
    column, so Postgres derives it. Idempotent: running it twice leaves the
    same rows. Returns rows written."""
    cols = _COLS
    updates = sql.SQL(", ").join(
        sql.SQL("{c} = EXCLUDED.{c}").format(c=ident(c)) for c in cols if c != "part_number"
    )
    insert = sql.SQL(
        "INSERT INTO actuators ({cols}) VALUES ({ph}) "
        "ON CONFLICT (part_number) DO UPDATE SET {upd}, updated_at = now()"
    ).format(
        cols=sql.SQL(", ").join(ident(c) for c in cols),
        ph=sql.SQL(", ").join(sql.Placeholder() * len(cols)),
        upd=updates,
    )
    tables = [(t.table_id, t.title, Jsonb(t.notes)) for t in catalog.tables]
    rows = [tuple(getattr(a, c) for c in cols) for a in catalog.rows]
    with conn.transaction(), _cur(conn) as cur:
        cur.executemany(
            "INSERT INTO catalog_tables (table_id, title, notes) VALUES (%s, %s, %s) "
            "ON CONFLICT (table_id) DO UPDATE SET title = EXCLUDED.title, notes = EXCLUDED.notes",
            tables,
        )
        cur.executemany(insert, rows)
    return len(rows)


def delete_all(conn: psycopg.Connection) -> None:
    """Remove all actuators and catalog_tables (used by `ingest.py --reset`)."""
    with conn.transaction():
        conn.execute("DELETE FROM actuators")
        conn.execute("DELETE FROM catalog_tables")


def get_by_pn(conn: psycopg.Connection, part_number: str) -> Actuator | None:
    """Exact match on the stored part_number (caller normalizes the input)."""
    query = sql.SQL("SELECT {} FROM actuators WHERE part_number = %s").format(_COLS_SQL)
    found = _rows(_cur(conn).execute(query, [part_number]))
    return found[0] if found else None


def find_like(conn: psycopg.Connection, fragment: str, limit: int = 10) -> list[Actuator]:
    """Part numbers that start with `fragment` (e.g. '764' or '764A00'),
    ordered by part_number. Used for partial input and suggestions."""
    escaped = fragment.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    query = sql.SQL(
        "SELECT {} FROM actuators WHERE part_number LIKE %s ORDER BY part_number LIMIT %s"
    ).format(_COLS_SQL)
    return _rows(_cur(conn).execute(query, [escaped + "%", limit]))


def search(conn: psycopg.Connection, filters: SearchFilters, limit: int = 10) -> list[Actuator]:
    """Rows meeting every filter (semantics in SearchFilters docstring),
    tightest fit first. Empty list when nothing matches."""
    cond, params = where(filters)
    order, order_params = order_by(filters)
    query = sql.SQL("SELECT {} FROM actuators WHERE {} ORDER BY {} LIMIT %s").format(
        _COLS_SQL, cond, order
    )
    return _rows(_cur(conn).execute(query, [*params, *order_params, limit]))


def count_matches(conn: psycopg.Connection, filters: SearchFilters) -> int:
    """Total rows meeting the filters (no limit)."""
    return _count_where(conn, *where(filters))


def _closest(conn: psycopg.Connection, f: SearchFilters, name: str) -> float | None:
    value = _scalar(conn, *closest_query(f, name))
    return None if value is None else float(value)


def _message(f: SearchFilters, blocking: list[str], oob: bool, closest: dict[str, float]) -> str:
    if oob:
        return "No actuator in the catalog has this combination of voltage, phase, enclosure and service."
    if not blocking:
        return (
            "No single requirement is responsible; the combination of requirements is too strict."
        )
    unit = "Nm" if f.torque_unit == "nm" else "in-lbs"
    facts = {
        "min_torque": f"max available torque {closest.get('min_torque')} {unit}",
        "max_speed_sec": f"fastest available {closest.get('max_speed_sec')} s at {f.speed_hz} Hz",
        "min_duty_cycle_pct": f"max available duty cycle {closest.get('min_duty_cycle_pct')}%",
    }
    detail = [facts[n] for n in blocking if n in closest]
    tail = f" ({'; '.join(detail)})" if detail else ""
    return f"No actuator meets all requirements; relaxing {', '.join(blocking)} would give results{tail}."


def diagnose_no_match(conn: psycopg.Connection, filters: SearchFilters) -> NoMatchReport:
    """Called when search() is empty: which filters block, whether the
    combination exists in the catalog at all, and the closest available value
    per blocking numeric filter (max torque, min speed, max duty).

    Closest values follow the one-family rule of search(): with `service` unset,
    the closest torque is the largest torque among families that also meet the
    duty requirement (if given), and vice versa for duty. Rows considered are
    those meeting all other (non-skipped) filters."""
    active = [n for n in FILTERS if getattr(filters, n) is not None]
    blocking = []
    for n in active:
        if _count_where(conn, *where(filters, skip={n})):
            blocking.append(n)
    static = where(filters, only=tuple(n for n in FILTERS if n not in NUMERIC))
    has_static = any(n not in NUMERIC for n in active)
    out = has_static and not _count_where(conn, *static)
    closest = {}
    for n in blocking:
        if n in NUMERIC and (v := _closest(conn, filters, n)) is not None:
            closest[n] = v
    return NoMatchReport(
        blocking=blocking,
        out_of_catalog=bool(out),
        closest=closest,
        message=_message(filters, blocking, bool(out), closest),
    )


def catalog_summary(conn: psycopg.Connection) -> CatalogSummary:
    """Distinct combinations, torque ranges, row totals."""
    cur = _cur(conn)
    combos = cur.execute(
        "SELECT enclosure, voltage, phase, service, table_id, count(*)::int AS rows "
        "FROM actuators GROUP BY enclosure, voltage, phase, service, table_id "
        "ORDER BY table_id"
    ).fetchall()

    def span(cols: tuple[str, str, str]) -> tuple[float, float] | None:
        lo = sql.SQL("LEAST({})").format(
            sql.SQL(", ").join(sql.SQL("MIN({})").format(ident(c)) for c in cols)
        )
        hi = sql.SQL("GREATEST({})").format(
            sql.SQL(", ").join(sql.SQL("MAX({})").format(ident(c)) for c in cols)
        )
        row = cur.execute(
            sql.SQL("SELECT {} AS lo, {} AS hi FROM actuators").format(lo, hi)
        ).fetchone()
        return None if row is None or row["lo"] is None else (float(row["lo"]), float(row["hi"]))

    totals = cur.execute(
        "SELECT count(*)::int AS total, count(*) FILTER (WHERE NOT has_data)::int AS missing FROM actuators"
    ).fetchone()
    assert totals is not None
    return CatalogSummary(
        combinations=[dict(c) for c in combos],
        torque_nm_range=span(TORQUE["nm"]),
        torque_in_lbs_range=span(TORQUE["in_lbs"]),
        total_rows=totals["total"],
        rows_without_data=totals["missing"],
    )


def table_notes(conn: psycopg.Connection, table_ids: list[str]) -> dict[str, list[str]]:
    """Printed notes per table_id (tolerances, IEC 60034-1, hazardous area, CSA)."""
    cur = _cur(conn).execute(
        "SELECT table_id, notes FROM catalog_tables WHERE table_id = ANY(%s)", [table_ids]
    )
    return {r["table_id"]: list(r["notes"]) for r in cur.fetchall()}
