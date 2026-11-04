"""Build data/processed/actuators.json from the verified golden draft.

Stdlib only. Run from backend/ with:

    uv run python scripts/build_seed.py [--golden PATH] [--out PATH] [--force]

Values are copied exactly as they are in the golden file: no rounding, no unit
conversion. The only transformation is dropping the `unparsed` key, which must
be empty for every row (otherwise the script aborts).

Refuses to overwrite an existing output file unless --force is passed.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

BACKEND_DIR = Path(__file__).resolve().parents[1]
DEFAULT_GOLDEN = BACKEND_DIR / "tests" / "fixtures" / "golden_draft.json"
DEFAULT_OUT = BACKEND_DIR / "data" / "processed" / "actuators.json"
EXPECTED_ROWS = 68

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

TABLES: list[dict[str, Any]] = [
    {
        "table_id": "T1_wp_110v_1ph",
        "title": "WEATHERPROOF - CSA, CE, & UKCA | 110V - Single Phase Power",
        "notes": list(WP_NOTES),
    },
    {
        "table_id": "T2_wp_220v_1ph",
        "title": "WEATHERPROOF - CSA, CE, & UKCA | 220V - Single Phase Power",
        "notes": [*WP_NOTES, "* Sizes 6 and 7 are not CSA Certified"],
    },
    {
        "table_id": "T3_wp_220v_3ph",
        "title": "WEATHERPROOF - CSA, CE, & UKCA | 220V - 3 Phase Power",
        "notes": list(WP_NOTES),
    },
    {
        "table_id": "T4_xp_24v_onoff",
        "title": "EXPLOSIONPROOF - CSA | 24V AC/DC Power - On/Off",
        "notes": list(XP_24V_NOTES),
    },
    {
        "table_id": "T5_xp_24vdc_mod",
        "title": "EXPLOSIONPROOF - CSA | 24V DC Power - Modulating",
        "notes": list(XP_24V_NOTES),
    },
    {
        "table_id": "T6_xp_110v_1ph",
        "title": "EXPLOSIONPROOF - CSA | 110V - Single Phase Power",
        "notes": list(XP_110_220_NOTES),
    },
    {
        "table_id": "T7_xp_220v_1ph",
        "title": "EXPLOSIONPROOF - CSA | 220V - Single Phase Power",
        "notes": list(XP_110_220_NOTES),
    },
]


def fail(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(1)


def load_rows(golden_path: Path) -> list[dict[str, Any]]:
    if not golden_path.is_file():
        fail(f"golden file not found: {golden_path}")
    data = json.loads(golden_path.read_text(encoding="utf-8"))
    rows = data.get("rows")
    if not isinstance(rows, list):
        fail("golden file has no 'rows' list")
    if len(rows) != EXPECTED_ROWS:
        fail(f"expected {EXPECTED_ROWS} rows, got {len(rows)}")

    out: list[dict[str, Any]] = []
    for row in rows:
        unparsed = row.get("unparsed")
        if unparsed:
            fail(f"row {row.get('part_number')!r} has non-empty 'unparsed': {unparsed!r}")
        cleaned = {k: v for k, v in row.items() if k != "unparsed"}
        out.append(cleaned)
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--golden", type=Path, default=DEFAULT_GOLDEN, help="path to golden_draft.json")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help="output actuators.json")
    parser.add_argument("--force", action="store_true", help="overwrite an existing output file")
    args = parser.parse_args()

    if args.out.exists() and not args.force:
        fail(f"{args.out} already exists; refusing to overwrite. Pass --force to replace it.")

    rows = load_rows(args.golden)
    payload = {"tables": TABLES, "rows": rows}

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {len(rows)} rows and {len(TABLES)} tables to {args.out}")


if __name__ == "__main__":
    main()
