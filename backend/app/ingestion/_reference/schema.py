"""Flat row schema for the Series 76 electrical-data benchmark.

One `ElectricalRow` per (table_id, part_number). Every data field is nullable:
a table that has no such column leaves it null, and printed "N/A" becomes null.

Field families (which tables fill them):

  onoff_torque_in_lbs / onoff_torque_nm   "On/Off Output Torque"      T1 T2 T4 T6 T7
  onoff_duty_cycle_pct                    "On/Off Duty Cycle (S4%)"   T1 T2 T4 T6 T7
  cycles_per_hour                         "Cycles per Hour"           T1 T2 T3 T4 T6 T7
  mod_torque_in_lbs / mod_torque_nm       "Modulating Output Torque"  T1 T2 T5 T6 T7
  mod_duty_cycle_pct                      "Modulating Duty Cycle"     T1 T2 T5 T6 T7
  starts_per_hour                         "Starts per Hour"           T1 T2 T3 T5 T6 T7
  output_torque_in_lbs / output_torque_nm "Output Torque" (single)    T3
  duty_cycle_pct                          "Duty Cycle" (single)       T3
  speed_sec_60hz / speed_sec_50hz         "Operating Speed (sec)"     T1 T2 T3 T6 T7
  speed_sec                               "Operating Speed Sec" (no Hz)  T4 T5
  fla_60hz_a / fla_50hz_a                 "Full Load Current (FLA)"   T1 T2 T3 T6 T7
  fla_a                                   "Full Load Current Amps"    T4 T5
  lra_60hz_a / lra_50hz_a                 "Locked Rotor Current"      T1 T2 T3 T6 T7
  lra_a                                   "Locked Rotor Current Amps" T4 T5
  motor_power_w                           "Motor Power Watts" — merged cell, copied to every row of its group

Extraction rules: values exactly as printed (no unit conversion, no arithmetic, no
"corrections"); thousands commas removed; N/A -> null; a trailing "*" on the part number
-> csa_certified=False and the part number is stored without it. Enclosure, voltage,
phase and service come from the section/table titles, never from the part number.
A cell that is present but cannot be read goes to `unparsed` as {field: raw_text}
with the field itself left null.
"""
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

TABLE_IDS = (
    "T1_wp_110v_1ph",
    "T2_wp_220v_1ph",
    "T3_wp_220v_3ph",
    "T4_xp_24v_onoff",
    "T5_xp_24vdc_mod",
    "T6_xp_110v_1ph",
    "T7_xp_220v_1ph",
)

TableId = Literal[TABLE_IDS]  # type: ignore[valid-type]

NUMERIC_FIELDS = (
    "onoff_torque_in_lbs", "onoff_torque_nm", "onoff_duty_cycle_pct", "cycles_per_hour",
    "mod_torque_in_lbs", "mod_torque_nm", "mod_duty_cycle_pct", "starts_per_hour",
    "output_torque_in_lbs", "output_torque_nm", "duty_cycle_pct",
    "speed_sec_60hz", "speed_sec_50hz", "speed_sec",
    "fla_60hz_a", "fla_50hz_a", "fla_a",
    "lra_60hz_a", "lra_50hz_a", "lra_a",
    "motor_power_w",
)
META_FIELDS = ("enclosure", "certifications", "voltage", "current_type", "phase", "service")


class ElectricalRow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # identity
    table_id: TableId
    part_number: str = Field(description="As printed, without '*' and without spaces, e.g. 761A00-11300000/A")
    csa_certified: bool = Field(True, description="False only when the printed part number carries '*'")

    # from section / table titles
    enclosure: Literal["weatherproof", "explosionproof"]
    certifications: str = Field(description="Section subtitle after the dash, e.g. 'CSA, CE, & UKCA' or 'CSA'")
    voltage: str = Field(description="Table title voltage as printed, e.g. '110V', '24V AC/DC', '24V DC'")
    current_type: Literal["AC", "DC", "AC/DC"]
    phase: Optional[Literal[1, 3]] = Field(None, description="1 or 3 when the title says Single/3 Phase, else null")
    service: Literal["on_off_and_modulating", "on_off", "modulating", "unspecified"]

    # numeric cells (null = column absent in this table or printed N/A)
    onoff_torque_in_lbs: Optional[float] = None
    onoff_torque_nm: Optional[float] = None
    onoff_duty_cycle_pct: Optional[float] = None
    cycles_per_hour: Optional[float] = None
    mod_torque_in_lbs: Optional[float] = None
    mod_torque_nm: Optional[float] = None
    mod_duty_cycle_pct: Optional[float] = None
    starts_per_hour: Optional[float] = None
    output_torque_in_lbs: Optional[float] = None
    output_torque_nm: Optional[float] = None
    duty_cycle_pct: Optional[float] = None
    speed_sec_60hz: Optional[float] = None
    speed_sec_50hz: Optional[float] = None
    speed_sec: Optional[float] = None
    fla_60hz_a: Optional[float] = None
    fla_50hz_a: Optional[float] = None
    fla_a: Optional[float] = None
    lra_60hz_a: Optional[float] = None
    lra_50hz_a: Optional[float] = None
    lra_a: Optional[float] = None
    motor_power_w: Optional[float] = None

    # bookkeeping
    row_index: Optional[int] = Field(None, description="1-based row order within the table")
    unparsed: dict[str, str] = Field(default_factory=dict, description="field -> raw text that could not be parsed")


class Extraction(BaseModel):
    """File format of every candidate output: rows.json"""
    model_config = ConfigDict(extra="forbid")
    candidate: str
    run: int = 1
    rows: list[ElectricalRow]


if __name__ == "__main__":
    import json
    print(json.dumps(Extraction.model_json_schema(), indent=2))
