"""Search and lookup contracts shared by db/actuators_repo.py and agent/tools.py.

Inputs:  SearchFilters (what the user requires).
Outputs: ActuatorLookup, SearchResult, NoMatchReport, CatalogSummary.

All numbers inside these models are copied from database rows; nothing here
computes or converts technical values. Tool outputs are these models dumped
with ``model_dump(mode="json")`` so they are JSON-serializable for the LLM,
the trace and the API.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.domain.models import Actuator

TorqueUnit = Literal["nm", "in_lbs"]
VoltageV = Literal[24, 110, 220]
ServiceFilter = Literal["on_off", "modulating"]
Hz = Literal[50, 60]


class SearchFilters(BaseModel):
    """User requirements. Every field is optional; None means "no constraint".

    Semantics (implemented in actuators_repo.search):
    - min_torque + torque_unit: compares against the column family of `service`
      (onoff_* or mod_*), falling back to output_* for the 3-phase table
      (COALESCE). Without `service`, a row matches when ONE family (on/off,
      modulating or output) meets every given family constraint at once
      (torque_k >= min_torque AND duty_k >= min_duty_cycle_pct, only those set);
      torque from one mode and duty from another never combine.
      The unit picks the printed column (`*_nm` or `*_in_lbs`); no conversion.
    - voltage_v: 24 matches '24V AC/DC' and '24V DC'; 110/220 match '110V'/'220V'.
    - phase: 1 or 3. 24V tables have phase NULL and never match a phase filter.
    - service: 'on_off' matches on_off and on_off_and_modulating rows (and the
      3-phase 'unspecified' table); 'modulating' likewise.
    - max_speed_sec + speed_hz: compares speed_sec_60hz / speed_sec_50hz, or
      speed_sec for 24V tables.
    - min_duty_cycle_pct: same family rule as torque (jointly with it).
    - Rows with has_data = false never match a numeric filter.
    """

    min_torque: float | None = Field(None, gt=0)
    torque_unit: TorqueUnit = "nm"
    voltage_v: VoltageV | None = None
    phase: Literal[1, 3] | None = None
    enclosure: Literal["weatherproof", "explosionproof"] | None = None
    service: ServiceFilter | None = None
    max_speed_sec: float | None = Field(None, gt=0)
    speed_hz: Hz = 60
    min_duty_cycle_pct: float | None = Field(None, ge=0, le=100)


class Candidate(BaseModel):
    """A part number plus the section facts (from its table title) that tell
    candidates apart, so the LLM can ask "110V or 220V?" without decoding suffixes."""

    part_number: str
    enclosure: str
    voltage: str
    phase: int | None = None
    service: str
    has_data: bool


class ActuatorLookup(BaseModel):
    """Result of get_actuator(part_number).

    status:
    - found:          exactly one row and it has data -> `actuator` set.
    - found_no_data:  exactly one row, printed as N/A -> `actuator` set, has_data False.
    - ambiguous:      the input matches several part numbers -> `candidates`.
    - not_found:      no match -> `suggestions` (closest PNs, may be empty).
    `notes`: printed notes of the actuator's table (found / found_no_data),
    plus "Sizes 6 and 7 are not CSA Certified" when csa_certified is False.
    """

    status: Literal["found", "found_no_data", "ambiguous", "not_found"]
    query: str
    normalized: str
    actuator: Actuator | None = None
    notes: list[str] = Field(default_factory=list)
    candidates: list[Candidate] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list)


class NoMatchReport(BaseModel):
    """Why a search returned nothing.

    blocking: filter names that, removed one at a time, would yield results
    (e.g. ["min_torque"]). out_of_catalog: the combination does not exist in
    the catalog at all (e.g. 24V weatherproof, 3-phase explosionproof).
    closest: per blocking numeric filter, the best value available among rows
    that satisfy all *other* filters, e.g. {"min_torque": 4000.0}.
    """

    blocking: list[str] = Field(default_factory=list)
    out_of_catalog: bool = False
    closest: dict[str, float] = Field(default_factory=dict)
    message: str


class SearchResult(BaseModel):
    """Result of search_actuators(filters). Matches are ordered tightest-fit
    first (smallest torque, among the families meeting all constraints, that
    meets min_torque; then fastest speed)."""

    status: Literal["ok", "no_match"]
    filters: SearchFilters
    matches: list[Actuator] = Field(default_factory=list)
    total: int = 0
    no_match: NoMatchReport | None = None


class CatalogSummary(BaseModel):
    """Result of describe_catalog(): what exists, for ambiguous questions."""

    combinations: list[dict[str, str | int | None]] = Field(
        default_factory=list,
        description="Distinct (enclosure, voltage, phase, service, table_id, rows)",
    )
    torque_nm_range: tuple[float, float] | None = None
    torque_in_lbs_range: tuple[float, float] | None = None
    total_rows: int = 0
    rows_without_data: int = 0
