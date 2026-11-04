"""Invariants over a full extraction. Run on the output of ANY extractor and on
actuators.json before loading. Errors block loading; warnings are reported.

Checks (level):
- row_count (error): rows per table == EXPECTED_ROWS.
- unique_pn (error): no duplicate part_number.
- suffix (error): PN suffix matches the table (normalize.SUFFIX_BY_TABLE).
- torque_ratio (error): in_lbs / nm within 8.85 ±5% for each torque pair
  (onoff, mod, output) when both are present.
- fla_le_lra (error): FLA <= LRA for each pair (60 Hz, 50 Hz, no-Hz).
- duty_range (error): duty cycle fields in [0, 100].
- speed_60_le_50 (warning): speed_sec_60hz <= speed_sec_50hz.
- starts_known (warning): starts_per_hour in {720, 840, 960, 1200}.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from app.domain.models import EXPECTED_ROWS, Actuator
from app.ingestion.normalize import SUFFIX_BY_TABLE

TORQUE_RATIO = 8.85
TORQUE_TOLERANCE = 0.05
KNOWN_STARTS = frozenset({720.0, 840.0, 960.0, 1200.0})


class Issue(BaseModel):
    level: Literal["error", "warning"]
    check: str
    table_id: str | None = None
    part_number: str | None = None
    field: str | None = None
    message: str


class ValidationFailed(RuntimeError):
    """Raised by assert_valid; `.issues` holds the error-level issues."""

    def __init__(self, issues: list[Issue]) -> None:
        self.issues = issues
        super().__init__("; ".join(i.message for i in issues[:10]))


TORQUE_PAIRS = (
    ("onoff_torque_in_lbs", "onoff_torque_nm"),
    ("mod_torque_in_lbs", "mod_torque_nm"),
    ("output_torque_in_lbs", "output_torque_nm"),
)
CURRENT_PAIRS = (
    ("fla_60hz_a", "lra_60hz_a"),
    ("fla_50hz_a", "lra_50hz_a"),
    ("fla_a", "lra_a"),
)
DUTY_FIELDS = ("onoff_duty_cycle_pct", "mod_duty_cycle_pct", "duty_cycle_pct")


def _row_issues(a: Actuator, seen: set[str]) -> list[Issue]:
    """Per-row checks, in the fixed order documented in the module docstring."""
    out: list[Issue] = []
    tid, pn = a.table_id, a.part_number

    def add(level: Literal["error", "warning"], check: str, field: str | None, msg: str) -> None:
        # A pair check ("a/b") emits one issue per cell: either value may be the
        # wrong one, and flags.py looks issues up by real field name.
        for name in field.split("/") if field else [None]:
            out.append(
                Issue(
                    level=level,
                    check=check,
                    table_id=tid,
                    part_number=pn,
                    field=name,
                    message=f"[{tid}] {pn}: {msg}",
                )
            )

    if pn in seen:
        add("error", "unique_pn", "part_number", f"duplicate part number {pn!r}")
    seen.add(pn)

    suffix = pn.split("-", 1)[1].split("/", 1)[0]
    expected = SUFFIX_BY_TABLE[tid]
    if suffix != expected:
        add("error", "suffix", "part_number", f"suffix {suffix!r} does not match {expected!r}")

    for f_in, f_nm in TORQUE_PAIRS:
        v_in, v_nm = getattr(a, f_in), getattr(a, f_nm)
        if v_in is None or v_nm is None:
            continue
        if v_nm <= 0:
            add(
                "error",
                "torque_ratio",
                f"{f_in}/{f_nm}",
                f"{f_nm}={v_nm} is not positive ({f_in}={v_in})",
            )
            continue
        ratio = v_in / v_nm
        if abs(ratio / TORQUE_RATIO - 1) > TORQUE_TOLERANCE:
            add(
                "error",
                "torque_ratio",
                f"{f_in}/{f_nm}",
                f"{f_in}={v_in} / {f_nm}={v_nm} = {ratio:.2f}, expected {TORQUE_RATIO} "
                f"+-{TORQUE_TOLERANCE:.0%}",
            )

    for f_fla, f_lra in CURRENT_PAIRS:
        fla, lra = getattr(a, f_fla), getattr(a, f_lra)
        if fla is not None and lra is not None and fla > lra:
            add("error", "fla_le_lra", f"{f_fla}/{f_lra}", f"{f_fla}={fla} > {f_lra}={lra}")

    for f in DUTY_FIELDS:
        v = getattr(a, f)
        if v is not None and not 0 <= v <= 100:
            add("error", "duty_range", f, f"{f}={v} outside 0..100")

    s60, s50 = a.speed_sec_60hz, a.speed_sec_50hz
    if s60 is not None and s50 is not None and s60 > s50:
        add(
            "warning",
            "speed_60_le_50",
            "speed_sec_60hz/speed_sec_50hz",
            f"speed_sec_60hz={s60} > speed_sec_50hz={s50}",
        )

    if a.starts_per_hour is not None and a.starts_per_hour not in KNOWN_STARTS:
        known = sorted(int(k) for k in KNOWN_STARTS)
        add(
            "warning",
            "starts_known",
            "starts_per_hour",
            f"starts_per_hour={a.starts_per_hour} not in {known}",
        )
    return out


def validate_rows(rows: list[Actuator]) -> list[Issue]:
    """All issues (errors and warnings), deterministic order (table, row, check)."""
    issues: list[Issue] = []
    seen: set[str] = set()
    for tid, expected in EXPECTED_ROWS.items():
        table_rows = [r for r in rows if r.table_id == tid]
        if len(table_rows) != expected:
            issues.append(
                Issue(
                    level="error",
                    check="row_count",
                    table_id=tid,
                    message=f"[{tid}] expected {expected} rows, found {len(table_rows)}",
                )
            )
        for r in table_rows:
            issues.extend(_row_issues(r, seen))
    return issues


def assert_valid(rows: list[Actuator]) -> list[Issue]:
    """Raise ValidationFailed if any error; otherwise return the warnings."""
    issues = validate_rows(rows)
    errors = [i for i in issues if i.level == "error"]
    if errors:
        raise ValidationFailed(errors)
    return [i for i in issues if i.level == "warning"]
