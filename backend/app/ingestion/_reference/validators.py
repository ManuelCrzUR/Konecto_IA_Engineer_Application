"""Invariant checks for a rows.json extraction (no ground truth needed).

Usage:  python validators.py path/to/rows.json [--json]
Exit code 0 even when checks fail; findings are printed (or emitted as JSON).

Checks
  schema        row validates against schema.ElectricalRow
  pn_regex      part number matches the family regex and the table's suffix
  row_count     rows per table == EXPECTED_ROWS (11,16,11,5,5,10,10 = 68)
  duplicate     (table_id, part_number) appears once
  torque_ratio  in-lbs / Nm within 8.85 +-5% for each torque pair
  fla_le_lra    FLA <= LRA at 60 Hz, 50 Hz and the no-Hz column
  speed_60_50   speed at 60 Hz <= speed at 50 Hz           (warning only)
  duty_range    0 <= duty cycle <= 100
  csa_flag      csa_certified is False exactly for 766A/766B/767A/767B/767C   (warning only)
"""
import json
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from schema import TABLE_IDS, ElectricalRow  # noqa: E402

EXPECTED_ROWS = dict(zip(TABLE_IDS, (11, 16, 11, 5, 5, 10, 10)))
PN_FAMILY = re.compile(r"^76[1-7][ABCXY][03]0-113[0-8]0[0C]00/A$")
PN_SUFFIX = {
    "T1_wp_110v_1ph": r"^76[1-7][ABC]00-11300000/A$",
    "T2_wp_220v_1ph": r"^76[1-7][ABC]00-11320000/A$",
    "T3_wp_220v_3ph": r"^76[1-7][ABC]00-11330C00/A$",
    "T4_xp_24v_onoff": r"^76[1-7][XY]30-11380000/A$",
    "T5_xp_24vdc_mod": r"^76[1-7][XY]30-11370000/A$",
    "T6_xp_110v_1ph": r"^76[1-7][XY]30-11300000/A$",
    "T7_xp_220v_1ph": r"^76[1-7][XY]30-11320000/A$",
}
NOT_CSA = {"766A", "766B", "767A", "767B", "767C"}
TORQUE_PAIRS = [("onoff_torque_in_lbs", "onoff_torque_nm"),
                ("mod_torque_in_lbs", "mod_torque_nm"),
                ("output_torque_in_lbs", "output_torque_nm")]
CURRENT_PAIRS = [("fla_60hz_a", "lra_60hz_a"), ("fla_50hz_a", "lra_50hz_a"), ("fla_a", "lra_a")]
DUTY_FIELDS = ["onoff_duty_cycle_pct", "mod_duty_cycle_pct", "duty_cycle_pct"]
RATIO, TOL = 8.85, 0.05


def check_rows(raw_rows):
    """Return list of findings: dict(level, check, table_id, part_number, field, msg)."""
    out = []

    def add(level, check, row, field, msg):
        out.append({"level": level, "check": check, "table_id": row.get("table_id"),
                    "part_number": row.get("part_number"), "field": field, "msg": msg})

    rows = []
    for r in raw_rows:
        try:
            rows.append(ElectricalRow.model_validate(r).model_dump())
        except Exception as e:  # pydantic ValidationError
            add("error", "schema", r, None, str(e).splitlines()[0])
    for r in rows:
        pn, tid = r["part_number"], r["table_id"]
        if not PN_FAMILY.match(pn):
            add("error", "pn_regex", r, "part_number", f"{pn!r} does not match family regex")
        elif not re.match(PN_SUFFIX[tid], pn):
            add("error", "pn_regex", r, "part_number", f"{pn!r} has wrong prefix/suffix for {tid}")
        for a, b in TORQUE_PAIRS:
            if r[a] is not None and r[b]:
                q = r[a] / r[b]
                if abs(q / RATIO - 1) > TOL:
                    add("error", "torque_ratio", r, f"{a}/{b}", f"{r[a]}/{r[b]} = {q:.3f}")
        for f, l in CURRENT_PAIRS:
            if r[f] is not None and r[l] is not None and r[f] > r[l]:
                add("error", "fla_le_lra", r, f"{f}/{l}", f"FLA {r[f]} > LRA {r[l]}")
        if r["speed_sec_60hz"] is not None and r["speed_sec_50hz"] is not None \
                and r["speed_sec_60hz"] > r["speed_sec_50hz"]:
            add("warning", "speed_60_50", r, "speed_sec_60hz/50hz",
                f"{r['speed_sec_60hz']} > {r['speed_sec_50hz']}")
        for f in DUTY_FIELDS:
            if r[f] is not None and not 0 <= r[f] <= 100:
                add("error", "duty_range", r, f, f"{r[f]} outside 0..100")
        should_be_false = pn[:4] in NOT_CSA
        if r["csa_certified"] == should_be_false:
            add("warning", "csa_flag", r, "csa_certified",
                f"csa_certified={r['csa_certified']} for {pn[:4]}")
    keys = Counter((r["table_id"], r["part_number"]) for r in rows)
    for (tid, pn), n in keys.items():
        if n > 1:
            add("error", "duplicate", {"table_id": tid, "part_number": pn}, None, f"{n} copies")
    counts = Counter(r["table_id"] for r in rows)
    for tid, exp in EXPECTED_ROWS.items():
        if counts.get(tid, 0) != exp:
            add("error", "row_count", {"table_id": tid}, None, f"{counts.get(tid, 0)} rows, expected {exp}")
    return out


def load_rows(path):
    data = json.loads(Path(path).read_text())
    return data["rows"] if isinstance(data, dict) else data


if __name__ == "__main__":
    findings = check_rows(load_rows(sys.argv[1]))
    if "--json" in sys.argv:
        print(json.dumps(findings, indent=2))
    else:
        for f in findings:
            print(f"[{f['level']}] {f['check']:<12} {f['table_id']} {f['part_number']} {f['field'] or ''}: {f['msg']}")
        n_err = sum(f["level"] == "error" for f in findings)
        print(f"-- {n_err} errors, {len(findings) - n_err} warnings")
