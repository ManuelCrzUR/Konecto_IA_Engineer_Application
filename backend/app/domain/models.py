"""Domain models: the single data contract shared by ingestion, DB, tools and API.

Inputs:
    - Rows extracted from the PDF (bench-schema dicts, see `Actuator.from_bench_row`).
    - API requests (`ConversationRequest`).
Outputs:
    - `Actuator` / `Catalog` (file format of data/processed/actuators.json).
    - `Product`, `ToolTrace`, `ConversationResponse` (JSON-friendly API payloads).

Values are stored exactly as printed in the PDF: no unit conversion, no arithmetic.
"""

from __future__ import annotations

import uuid
from typing import Annotated, Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    computed_field,
    model_validator,
)

TABLE_IDS = (
    "T1_wp_110v_1ph",
    "T2_wp_220v_1ph",
    "T3_wp_220v_3ph",
    "T4_xp_24v_onoff",
    "T5_xp_24vdc_mod",
    "T6_xp_110v_1ph",
    "T7_xp_220v_1ph",
)

EXPECTED_ROWS: dict[str, int] = {
    "T1_wp_110v_1ph": 11,
    "T2_wp_220v_1ph": 16,
    "T3_wp_220v_3ph": 11,
    "T4_xp_24v_onoff": 5,
    "T5_xp_24vdc_mod": 5,
    "T6_xp_110v_1ph": 10,
    "T7_xp_220v_1ph": 10,
}

NUMERIC_FIELDS = (
    "onoff_torque_in_lbs",
    "onoff_torque_nm",
    "onoff_duty_cycle_pct",
    "cycles_per_hour",
    "mod_torque_in_lbs",
    "mod_torque_nm",
    "mod_duty_cycle_pct",
    "starts_per_hour",
    "output_torque_in_lbs",
    "output_torque_nm",
    "duty_cycle_pct",
    "speed_sec_60hz",
    "speed_sec_50hz",
    "speed_sec",
    "fla_60hz_a",
    "fla_50hz_a",
    "fla_a",
    "lra_60hz_a",
    "lra_50hz_a",
    "lra_a",
    "motor_power_w",
)

PART_NUMBER_PATTERN = r"^76\d[A-Z]\d{2}-[0-9A-Z]{8}/A$"

TableId = Literal[
    "T1_wp_110v_1ph",
    "T2_wp_220v_1ph",
    "T3_wp_220v_3ph",
    "T4_xp_24v_onoff",
    "T5_xp_24vdc_mod",
    "T6_xp_110v_1ph",
    "T7_xp_220v_1ph",
]


class Actuator(BaseModel):
    """One row per (part number, table). Numeric fields are null when absent or N/A."""

    model_config = ConfigDict(extra="forbid")

    table_id: TableId
    part_number: str = Field(pattern=PART_NUMBER_PATTERN)
    csa_certified: bool = True
    enclosure: Literal["weatherproof", "explosionproof"]
    certifications: str
    voltage: str
    current_type: Literal["AC", "DC", "AC/DC"]
    phase: Literal[1, 3] | None
    service: Literal["on_off_and_modulating", "on_off", "modulating", "unspecified"]

    onoff_torque_in_lbs: float | None = None
    onoff_torque_nm: float | None = None
    onoff_duty_cycle_pct: float | None = None
    cycles_per_hour: float | None = None
    mod_torque_in_lbs: float | None = None
    mod_torque_nm: float | None = None
    mod_duty_cycle_pct: float | None = None
    starts_per_hour: float | None = None
    output_torque_in_lbs: float | None = None
    output_torque_nm: float | None = None
    duty_cycle_pct: float | None = None
    speed_sec_60hz: float | None = None
    speed_sec_50hz: float | None = None
    speed_sec: float | None = None
    fla_60hz_a: float | None = None
    fla_50hz_a: float | None = None
    fla_a: float | None = None
    lra_60hz_a: float | None = None
    lra_50hz_a: float | None = None
    lra_a: float | None = None
    motor_power_w: float | None = None

    row_index: int | None = None

    @model_validator(mode="before")
    @classmethod
    def _drop_computed(cls, data: Any) -> Any:
        """`has_data` is computed, so it appears in every dump; accept it back on
        input (and ignore it) so `model_validate(x.model_dump())` round-trips
        despite extra="forbid"."""
        if isinstance(data, dict) and "has_data" in data:
            data = {k: v for k, v in data.items() if k != "has_data"}
        return data

    @computed_field  # type: ignore[prop-decorator]
    @property
    def has_data(self) -> bool:
        """True iff at least one numeric field is present (False for N/A rows)."""
        return any(getattr(self, f) is not None for f in NUMERIC_FIELDS)

    @classmethod
    def from_bench_row(cls, d: dict[str, Any]) -> Actuator:
        """Build from a benchmark-schema dict, dropping the bench-only `unparsed` key."""
        data = dict(d)
        unparsed = data.pop("unparsed", None)
        if unparsed:
            raise ValueError(f"row has unparsed cells: {unparsed}")
        return cls.model_validate(data)


class TableMeta(BaseModel):
    table_id: str
    title: str
    notes: list[str] = Field(default_factory=list)


class Catalog(BaseModel):
    """File format of data/processed/actuators.json."""

    tables: list[TableMeta]
    rows: list[Actuator]


class Product(BaseModel):
    """What the API/app shows per actuator. Values are copied as is."""

    part_number: str
    enclosure: str
    voltage: str
    phase: int | None = None
    service: str
    csa_certified: bool = True
    has_data: bool
    fields: dict[str, float | None] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)

    @classmethod
    def from_actuator(cls, a: Actuator, notes: list[str] | None = None) -> Product:
        fields = {f: v for f in NUMERIC_FIELDS if (v := getattr(a, f)) is not None}
        return cls(
            part_number=a.part_number,
            enclosure=a.enclosure,
            voltage=a.voltage,
            phase=a.phase,
            service=a.service,
            csa_certified=a.csa_certified,
            has_data=a.has_data,
            fields=fields,
            notes=list(notes or []),
        )


class ToolTrace(BaseModel):
    tool: str
    params: dict[str, Any]
    result: Any
    duration_ms: float | None = None


class ConversationRequest(BaseModel):
    session_id: uuid.UUID | None = None
    query: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]


class ConversationResponse(BaseModel):
    session_id: uuid.UUID
    answer: str
    products: list[Product] = Field(default_factory=list)
    debug: list[ToolTrace] = Field(default_factory=list)
