"""Builds parameterized SQL fragments from SearchFilters; column names only from fixed whitelists via psycopg.sql.Identifier; no I/O."""

from __future__ import annotations

from typing import Any

from psycopg import sql

from app.domain.search import SearchFilters

Cond = tuple[sql.Composable, list[Any]]  # SQL fragment + its bound params

# Column families: (on/off, modulating, 3-phase output).
TORQUE = {
    "nm": ("onoff_torque_nm", "mod_torque_nm", "output_torque_nm"),
    "in_lbs": ("onoff_torque_in_lbs", "mod_torque_in_lbs", "output_torque_in_lbs"),
}
DUTY = ("onoff_duty_cycle_pct", "mod_duty_cycle_pct", "duty_cycle_pct")
_SPEED = {60: "speed_sec_60hz", 50: "speed_sec_50hz"}
_SERVICES = {
    "on_off": ["on_off_and_modulating", "on_off", "unspecified"],
    "modulating": ["on_off_and_modulating", "modulating", "unspecified"],
}
FILTERS = (
    "voltage_v",
    "phase",
    "enclosure",
    "service",
    "min_torque",
    "max_speed_sec",
    "min_duty_cycle_pct",
)
NUMERIC = ("min_torque", "max_speed_sec", "min_duty_cycle_pct")


# ---- SQL fragment helpers ---------------------------------------------------
def ident(col: str) -> sql.Identifier:
    return sql.Identifier(col)


def _family(cols: tuple[str, str, str], service: str | None) -> sql.Composable | None:
    """The column that applies to `service` (falling back to output_*), or None."""
    if service == "on_off":
        return sql.SQL("COALESCE({}, {})").format(ident(cols[0]), ident(cols[2]))
    if service == "modulating":
        return sql.SQL("COALESCE({}, {})").format(ident(cols[1]), ident(cols[2]))
    return None


def speed(f: SearchFilters) -> sql.Composable:
    return sql.SQL("COALESCE({}, {})").format(ident(_SPEED[f.speed_hz]), ident("speed_sec"))


def _family_pairs(f: SearchFilters, names: list[str]) -> list[tuple[tuple[str, str, str], float]]:
    """The per-family numeric constraints (columns, minimum) among `names`."""
    pairs: list[tuple[tuple[str, str, str], float]] = []
    if "min_torque" in names and f.min_torque is not None:
        pairs.append((TORQUE[f.torque_unit], f.min_torque))
    if "min_duty_cycle_pct" in names and f.min_duty_cycle_pct is not None:
        pairs.append((DUTY, f.min_duty_cycle_pct))
    return pairs


def _in_family(pairs: list[tuple[tuple[str, str, str], float]], k: int) -> Cond:
    """All given constraints hold within family k (0=on/off, 1=modulating, 2=output)."""
    parts = [sql.SQL("{} >= %s").format(ident(cols[k])) for cols, _ in pairs]
    return sql.SQL("({})").format(sql.SQL(" AND ").join(parts)), [v for _, v in pairs]


def _in_some_family(f: SearchFilters, pairs: list[tuple[tuple[str, str, str], float]]) -> Cond:
    """Torque/duty constraints with `service` unset: ONE family must meet all of them
    (never torque from one operating mode and duty from another).
    With `service` set, the COALESCE(family, output_*) column is used instead."""
    if f.service is not None:
        parts = [sql.SQL("{} >= %s").format(_family(cols, f.service)) for cols, _ in pairs]
        return sql.SQL(" AND ").join(parts), [v for _, v in pairs]
    ors: list[sql.Composable] = []
    params: list[Any] = []
    for k in range(3):
        frag, p = _in_family(pairs, k)
        ors.append(frag)
        params += p
    return sql.SQL("({})").format(sql.SQL(" OR ").join(ors)), params


def _best(
    cols: tuple[str, str, str],
    f: SearchFilters,
    other: tuple[tuple[str, str, str], float] | None = None,
) -> Cond:
    """Highest value of `cols` among the applicable family (GREATEST ignores NULLs).
    With `service` unset and another active family constraint `other`, a family's
    value only counts when that family also meets `other` (same one-family rule)."""
    expr = _family(cols, f.service)
    if expr is not None:
        return expr, []
    if other is None:
        return sql.SQL("GREATEST({}, {}, {})").format(*(ident(c) for c in cols)), []
    parts = [
        sql.SQL("CASE WHEN {o} >= %s THEN {c} END").format(o=ident(other[0][k]), c=ident(cols[k]))
        for k in range(3)
    ]
    return sql.SQL("GREATEST({})").format(sql.SQL(", ").join(parts)), [other[1]] * 3


def fit(f: SearchFilters) -> Cond:
    """The torque value that satisfied the constraints: with `service` unset, the
    smallest torque among the families that meet ALL active family constraints."""
    cols = TORQUE[f.torque_unit]
    expr = _family(cols, f.service)
    if expr is not None:
        return expr, []
    pairs = _family_pairs(f, ["min_torque", "min_duty_cycle_pct"])
    parts: list[sql.Composable] = []
    params: list[Any] = []
    for k in range(3):
        cond, p = _in_family(pairs, k)
        parts.append(sql.SQL("CASE WHEN {} THEN {} END").format(cond, ident(cols[k])))
        params += p
    return sql.SQL("LEAST({})").format(sql.SQL(", ").join(parts)), params


def _condition(name: str, f: SearchFilters) -> Cond:
    v = getattr(f, name)
    if name == "voltage_v":
        return sql.SQL("voltage LIKE %s"), [f"{v}V%"]
    if name in ("phase", "enclosure"):
        return sql.SQL("{} = %s").format(ident(name)), [v]
    if name == "service":
        return sql.SQL("service = ANY(%s)"), [_SERVICES[v]]
    return sql.SQL("{} <= %s").format(speed(f)), [v]  # max_speed_sec


def where(f: SearchFilters, skip: set[str] | None = None, only: tuple[str, ...] = FILTERS) -> Cond:
    """WHERE clause for the active filters (minus `skip`, limited to `only`)."""
    names = [n for n in only if getattr(f, n) is not None and n not in (skip or set())]
    parts: list[sql.Composable] = []
    params: list[Any] = []
    pairs = _family_pairs(f, names)
    if pairs:  # torque + duty are evaluated together (one family must meet both)
        frag, p = _in_some_family(f, pairs)
        parts.append(frag)
        params += p
    for n in names:
        if n in ("min_torque", "min_duty_cycle_pct"):
            continue
        frag, p = _condition(n, f)
        parts.append(frag)
        params += p
    if any(n in NUMERIC for n in names):
        parts.append(sql.SQL("has_data"))  # N/A rows never match numeric filters
    if not parts:
        return sql.SQL("TRUE"), []
    return sql.SQL(" AND ").join(parts), params


def order_by(f: SearchFilters) -> Cond:
    """ORDER BY expressions: tightest torque fit first (when min_torque is set), then speed, then part number."""
    order: list[sql.Composable] = []
    params: list[Any] = []
    if f.min_torque is not None:
        expr, params = fit(f)
        order.append(expr)
    order += [speed(f), ident("part_number")]
    return sql.SQL(", ").join(order), params


def closest_query(f: SearchFilters, name: str) -> tuple[sql.Composed, list[Any]]:
    """SELECT for the best available value of numeric filter `name` among rows meeting the others."""
    cond, params = where(f, skip={name})
    agg_params: list[Any] = []
    if name == "min_torque":
        # Other family constraint (duty) is honoured within the same family.
        other = (DUTY, f.min_duty_cycle_pct) if f.min_duty_cycle_pct is not None else None
        best, agg_params = _best(TORQUE[f.torque_unit], f, other)
        agg = sql.SQL("MAX({})").format(best)
    elif name == "min_duty_cycle_pct":
        other = (TORQUE[f.torque_unit], f.min_torque) if f.min_torque is not None else None
        best, agg_params = _best(DUTY, f, other)
        agg = sql.SQL("MAX({})").format(best)
    else:
        agg = sql.SQL("MIN({})").format(speed(f))
    query = sql.SQL("SELECT {} FROM actuators WHERE has_data AND {}").format(agg, cond)
    return query, [*agg_params, *params]
