"""Titles and printed notes of the 7 tables of series_76_electric_data.pdf.

Transcribed once by hand from the page images (OCR does not read the notes),
so extract_catalog can build a full Catalog. Single source of truth: also used
by scripts/build_seed.py. Moved verbatim from that script.
"""

from __future__ import annotations

from app.domain.models import TableMeta


def _cols(names: str) -> tuple[str, ...]:
    return tuple(names.split())


_STD = _cols(
    "onoff_torque_in_lbs onoff_torque_nm onoff_duty_cycle_pct cycles_per_hour "
    "mod_torque_in_lbs mod_torque_nm mod_duty_cycle_pct starts_per_hour speed_sec_60hz "
    "speed_sec_50hz fla_60hz_a fla_50hz_a lra_60hz_a lra_50hz_a motor_power_w"
)
# Single source of truth for the column layout: fields printed in each table, left to
# right after the part number, Motor Power (merged cell) LAST. Used by ocr.py (geometry)
# and escalate.py (vision prompt/parsing). Verified against the OCR geometry (for T3 the
# output torque columns come first).
TABLE_FIELDS: dict[str, tuple[str, ...]] = {
    "T1_wp_110v_1ph": _STD,
    "T2_wp_220v_1ph": _STD,
    "T3_wp_220v_3ph": _cols(
        "output_torque_in_lbs output_torque_nm duty_cycle_pct cycles_per_hour starts_per_hour "
        "speed_sec_60hz speed_sec_50hz fla_60hz_a fla_50hz_a lra_60hz_a lra_50hz_a motor_power_w"
    ),
    "T4_xp_24v_onoff": _cols(
        "onoff_torque_in_lbs onoff_torque_nm onoff_duty_cycle_pct cycles_per_hour "
        "speed_sec fla_a lra_a motor_power_w"
    ),
    "T5_xp_24vdc_mod": _cols(
        "mod_torque_in_lbs mod_torque_nm mod_duty_cycle_pct starts_per_hour speed_sec fla_a "
        "lra_a motor_power_w"
    ),
    "T6_xp_110v_1ph": _STD,
    "T7_xp_220v_1ph": _STD,
}

# Table titles and printed notes, transcribed from the page images of
# series_76_electric_data.pdf. Notes are stored as printed. A notes block is
# attached to every table in the same section on the same page (the block is
# printed once, under the last table of the page). The asterisk footnote sits
# directly under T2 only.
WP_NOTES = [
    "1. Full load current (FLA) @ Max. rated load",
    "2. Locked rotor current (LRA) @ Locked rotor load",
    "3. Allowable motor voltage tolerance: +/- 10%",
    "4. Allowable power frequency tolerance: +/- 5%",
    "5. Duty cycle per IEC 60034-1 for on/off and modulating service",
    "6. Starts and cycles per hour based on rated torque",
]

XP_24V_NOTES = [
    "Hazardous Location Certification (Area Classification)",
    "Class I, Division 1, GRoups C, D; T4",  # [?] capitalization of "GRoups" is a low-res reading
    "Ex d IIB T4 Gb",
    "Class I, Zone 1, AEx d IIB T4 Gb",
    "1. Full load current (FLA) @ Max. rated load",
    "2. Locked rotor current (LRA) @ Locked rotor load",
    "3. Allowable motor voltage tolerance: +/- 10%",
    "4. Allowable power frequency tolerance: +/- 5%",
    "5. Duty cycle per IEC 60034-1 for on/off and modulating service",
    "6. Starts and cycles per hour based on rated torque",
]

XP_110_220_NOTES = [
    "1. Hazardous Location Certification (Area Classification)",
    "Class I, Division 1, Groups C, D; T4",
    "Ex d IIB T4 Gb",
    "Class I, Zone 1, AEx d IIB T4 Gb",
    "2. Full load current (FLA) @ Max. rated load",
    "3. Locked rotor current (LRA) @ Locked rotor load",
    "4. Allowable motor voltage tolerance: +/- 10%",
    "5. Allowable power frequency tolerance: +/- 5%",
    "6. Duty cycle per IEC 60034-1 for on/off and modulating service",
    "7. Starts and cycles per hour based on rated torque",
]

TABLE_META: list[TableMeta] = [
    TableMeta(
        table_id="T1_wp_110v_1ph",
        title="WEATHERPROOF - CSA, CE, & UKCA | 110V - Single Phase Power",
        notes=list(WP_NOTES),
    ),
    TableMeta(
        table_id="T2_wp_220v_1ph",
        title="WEATHERPROOF - CSA, CE, & UKCA | 220V - Single Phase Power",
        notes=[*WP_NOTES, "* Sizes 6 and 7 are not CSA Certified"],
    ),
    TableMeta(
        table_id="T3_wp_220v_3ph",
        title="WEATHERPROOF - CSA, CE, & UKCA | 220V - 3 Phase Power",
        notes=list(WP_NOTES),
    ),
    TableMeta(
        table_id="T4_xp_24v_onoff",
        title="EXPLOSIONPROOF - CSA | 24V AC/DC Power - On/Off",
        notes=list(XP_24V_NOTES),
    ),
    TableMeta(
        table_id="T5_xp_24vdc_mod",
        title="EXPLOSIONPROOF - CSA | 24V DC Power - Modulating",
        notes=list(XP_24V_NOTES),
    ),
    TableMeta(
        table_id="T6_xp_110v_1ph",
        title="EXPLOSIONPROOF - CSA | 110V - Single Phase Power",
        notes=list(XP_110_220_NOTES),
    ),
    TableMeta(
        table_id="T7_xp_220v_1ph",
        title="EXPLOSIONPROOF - CSA | 220V - Single Phase Power",
        notes=list(XP_110_220_NOTES),
    ),
]
