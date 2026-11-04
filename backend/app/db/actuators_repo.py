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

from app.domain.models import Actuator, Catalog
from app.domain.search import CatalogSummary, NoMatchReport, SearchFilters

Cond = tuple[sql.Composable, list[Any]]  # SQL fragment + its bound params

_COLS = list(Actuator.model_fields)  # static column list, same names as the table
_COLS_SQL = sql.SQL(", ").join(sql.Identifier(c) for c in _COLS)
# Column families: (on/off, modulating, 3-phase output).
_TORQUE = {
    "nm": ("onoff_torque_nm", "mod_torque_nm", "output_torque_nm"),
    "in_lbs": ("onoff_torque_in_lbs", "mod_torque_in_lbs", "output_torque_in_lbs"),
}
_DUTY = ("onoff_duty_cycle_pct", "mod_duty_cycle_pct", "duty_cycle_pct")
_SPEED = {60: "speed_sec_60hz", 50: "speed_sec_50hz"}
_SERVICES = {
    "on_off": ["on_off_and_modulating", "on_off", "unspecified"],
    "modulating": ["on_off_and_modulating", "modulating", "unspecified"],
}
_FILTERS = (
    "voltage_v",
    "phase",
    "enclosure",
    "service",
    "min_torque",
    "max_speed_sec",
    "min_duty_cycle_pct",
)
_NUMERIC = ("min_torque", "max_speed_sec", "min_duty_cycle_pct")


# ---- SQL fragment helpers ---------------------------------------------------
def _ident(col: str) -> sql.Identifier:
    return sql.Identifier(col)


def _family(cols: tuple[str, str, str], service: str | None) -> sql.Composable | None:
    """The column that applies to `service` (falling back to output_*), or None."""
    if service == "on_off":
        return sql.SQL("COALESCE({}, {})").format(_ident(cols[0]), _ident(cols[2]))
    if service == "modulating":
        return sql.SQL("COALESCE({}, {})").format(_ident(cols[1]), _ident(cols[2]))
    return None


def _speed(f: SearchFilters) -> sql.Composable:
    return sql.SQL("COALESCE({}, {})").format(_ident(_SPEED[f.speed_hz]), _ident("speed_sec"))


def _at_least(cols: tuple[str, str, str], f: SearchFilters, value: float) -> Cond:
    expr = _family(cols, f.service)
    if expr is not None:
        return sql.SQL("{} >= %s").format(expr), [value]
    ors = sql.SQL(" OR ").join(sql.SQL("{} >= %s").format(_ident(c)) for c in cols)
    return sql.SQL("({})").format(ors), [value] * 3


def _best(cols: tuple[str, str, str], f: SearchFilters) -> sql.Composable:
    """Highest value across the applicable family (GREATEST ignores NULLs)."""
    expr = _family(cols, f.service)
    return expr or sql.SQL("GREATEST({}, {}, {})").format(*(_ident(c) for c in cols))


def _fit(cols: tuple[str, str, str], f: SearchFilters, value: float) -> Cond:
    """The torque value that satisfied the minimum (smallest qualifying one)."""
    expr = _family(cols, f.service)
    if expr is not None:
        return expr, []
    parts = [sql.SQL("CASE WHEN {c} >= %s THEN {c} END").format(c=_ident(c)) for c in cols]
    return sql.SQL("LEAST({})").format(sql.SQL(", ").join(parts)), [value] * 3


def _condition(name: str, f: SearchFilters) -> Cond:
    v = getattr(f, name)
    if name == "voltage_v":
        return sql.SQL("voltage LIKE %s"), [f"{v}V%"]
    if name in ("phase", "enclosure"):
        return sql.SQL("{} = %s").format(_ident(name)), [v]
    if name == "service":
        return sql.SQL("service = ANY(%s)"), [_SERVICES[v]]
    if name == "min_torque":
        return _at_least(_TORQUE[f.torque_unit], f, v)
    if name == "min_duty_cycle_pct":
        return _at_least(_DUTY, f, v)
    return sql.SQL("{} <= %s").format(_speed(f)), [v]  # max_speed_sec


def _where(
    f: SearchFilters, skip: set[str] | None = None, only: tuple[str, ...] = _FILTERS
) -> Cond:
    """WHERE clause for the active filters (minus `skip`, limited to `only`)."""
    names = [n for n in only if getattr(f, n) is not None and n not in (skip or set())]
    parts: list[sql.Composable] = []
    params: list[Any] = []
    for n in names:
        frag, p = _condition(n, f)
        parts.append(frag)
        params += p
    if any(n in _NUMERIC for n in names):
        parts.append(sql.SQL("has_data"))  # N/A rows never match numeric filters
    if not parts:
        return sql.SQL("TRUE"), []
    return sql.SQL(" AND ").join(parts), params


def _rows(cur: psycopg.Cursor[Any]) -> list[Actuator]:
    return [Actuator.model_validate(r) for r in cur.fetchall()]


def _cur(conn: psycopg.Connection) -> psycopg.Cursor[Any]:
    """Dict-row cursor regardless of the connection's own row factory."""
    return conn.cursor(row_factory=dict_row)


def _scalar(conn: psycopg.Connection, query: sql.Composed | sql.SQL | str, params: list[Any]) -> Any:
    row = _cur(conn).execute(query, params).fetchone()
    return next(iter(row.values())) if row else None


# ---- public API -------------------------------------------------------------
def count(conn: psycopg.Connection) -> int:
    """Number of rows in `actuators`."""
    return int(_scalar(conn, sql.SQL("SELECT count(*) FROM actuators"), []))


def upsert_catalog(conn: psycopg.Connection, catalog: Catalog) -> int:
    """Upsert catalog_tables then actuators in ONE transaction
    (INSERT ... ON CONFLICT (part_number) DO UPDATE). Writes has_data.
    Idempotent: running it twice leaves the same rows. Returns rows written."""
    cols = [*_COLS, "has_data"]
    updates = sql.SQL(", ").join(
        sql.SQL("{c} = EXCLUDED.{c}").format(c=_ident(c)) for c in cols if c != "part_number"
    )
    insert = sql.SQL(
        "INSERT INTO actuators ({cols}) VALUES ({ph}) "
        "ON CONFLICT (part_number) DO UPDATE SET {upd}, updated_at = now()"
    ).format(
        cols=sql.SQL(", ").join(_ident(c) for c in cols),
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
    where, params = _where(filters)
    order: list[sql.Composable] = []
    if filters.min_torque is not None:
        expr, p = _fit(_TORQUE[filters.torque_unit], filters, filters.min_torque)
        order.append(expr)
        params += p
    order += [_speed(filters), _ident("part_number")]
    query = sql.SQL("SELECT {} FROM actuators WHERE {} ORDER BY {} LIMIT %s").format(
        _COLS_SQL, where, sql.SQL(", ").join(order)
    )
    return _rows(_cur(conn).execute(query, [*params, limit]))


def count_matches(conn: psycopg.Connection, filters: SearchFilters) -> int:
    """Total rows meeting the filters (no limit)."""
    where, params = _where(filters)
    return int(
        _scalar(conn, sql.SQL("SELECT count(*) FROM actuators WHERE {}").format(where), params)
    )


def _closest(conn: psycopg.Connection, f: SearchFilters, name: str) -> float | None:
    """Best available value for numeric filter `name` among rows meeting the others."""
    where, params = _where(f, skip={name})
    if name == "min_torque":
        agg = sql.SQL("MAX({})").format(_best(_TORQUE[f.torque_unit], f))
    elif name == "min_duty_cycle_pct":
        agg = sql.SQL("MAX({})").format(_best(_DUTY, f))
    else:
        agg = sql.SQL("MIN({})").format(_speed(f))
    value = _scalar(
        conn, sql.SQL("SELECT {} FROM actuators WHERE has_data AND {}").format(agg, where), params
    )
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
    per blocking numeric filter (max torque, min speed, max duty)."""
    active = [n for n in _FILTERS if getattr(filters, n) is not None]
    blocking = []
    for n in active:
        where, params = _where(filters, skip={n})
        if _scalar(conn, sql.SQL("SELECT count(*) FROM actuators WHERE {}").format(where), params):
            blocking.append(n)
    where, params = _where(filters, only=tuple(n for n in _FILTERS if n not in _NUMERIC))
    has_static = any(n not in _NUMERIC for n in active)
    out = has_static and not _scalar(
        conn, sql.SQL("SELECT count(*) FROM actuators WHERE {}").format(where), params
    )
    closest = {}
    for n in blocking:
        if n in _NUMERIC and (v := _closest(conn, filters, n)) is not None:
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
            sql.SQL(", ").join(sql.SQL("MIN({})").format(_ident(c)) for c in cols)
        )
        hi = sql.SQL("GREATEST({})").format(
            sql.SQL(", ").join(sql.SQL("MAX({})").format(_ident(c)) for c in cols)
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
        torque_nm_range=span(_TORQUE["nm"]),
        torque_in_lbs_range=span(_TORQUE["in_lbs"]),
        total_rows=totals["total"],
        rows_without_data=totals["missing"],
    )


def table_notes(conn: psycopg.Connection, table_ids: list[str]) -> dict[str, list[str]]:
    """Printed notes per table_id (tolerances, IEC 60034-1, hazardous area, CSA)."""
    cur = _cur(conn).execute(
        "SELECT table_id, notes FROM catalog_tables WHERE table_id = ANY(%s)", [table_ids]
    )
    return {r["table_id"]: list(r["notes"]) for r in cur.fetchall()}
