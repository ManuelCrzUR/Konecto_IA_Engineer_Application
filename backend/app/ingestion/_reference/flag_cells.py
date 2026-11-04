"""Flag suspicious cells in E's (RapidOCR) output and decide which tables to escalate to a vision model.

A cell is flagged when ANY of these holds:
  low_conf      min OCR confidence of the cell's boxes < CONF_MIN (0.9)
  leading_zero  raw OCR text starts with 0 followed by a digit (e.g. "096", "06"); "0.7" is fine
  validator     an error-level finding of validators.check_rows names this field on this row
A table with at least one flagged cell is escalated whole (row context helps the vision model).

Usage:
  python flag_cells.py <bench> [--golden golden_draft.json] [--vision outputs/B_vision_crop/run3/rows.json]
Writes outputs/E_paddle_rapidocr/flags.json. With --golden, prints how many of E's errors were caught.
With --vision, also writes outputs/H_hybrid_E_flagB/rows.json: E's rows, with every escalated table
replaced by that table from the vision output (a stand-in for a live Sonnet call; no API is called here).
"""
import argparse
import json
import re
from collections import defaultdict
from pathlib import Path

from validators import check_rows, load_rows
from schema import NUMERIC_FIELDS  # validators.py already put the bench dir on sys.path

CONF_MIN = 0.9
LEADING_ZERO = re.compile(r"^0\d")


def flag(rows_path, cells_path):
    rows = load_rows(rows_path)
    cells = json.loads(Path(cells_path).read_text())
    flags = defaultdict(list)  # (table, pn, field) -> reasons
    for c in cells:
        k = (c["table_id"], c["part_number"], c["field"])
        if c["conf"] < CONF_MIN:
            flags[k].append(f"low_conf {c['conf']:.3f}")
        if LEADING_ZERO.match(c["raw"].replace(" ", "")):
            flags[k].append(f"leading_zero '{c['raw']}'")
    for f in check_rows(rows):
        if f["level"] == "error" and f["field"] and f["part_number"]:
            for field in f["field"].split("/"):
                flags[(f["table_id"], f["part_number"], field)].append(f"validator {f['check']}")
    return {k: v for k, v in flags.items()}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("bench", type=Path)
    ap.add_argument("--golden")
    ap.add_argument("--vision")
    a = ap.parse_args()
    e_dir = a.bench / "outputs/E_paddle_rapidocr"
    flags = flag(e_dir / "rows.json", e_dir / "cells.json")
    tables = sorted({k[0] for k in flags})
    out = {"rule": f"conf < {CONF_MIN} OR raw ~ ^0\\d OR validator error",
           "n_flagged_cells": len(flags), "escalate_tables": tables,
           "cells": [{"table_id": t, "part_number": p, "field": f, "reasons": r} for (t, p, f), r in sorted(flags.items())]}
    (e_dir / "flags.json").write_text(json.dumps(out, indent=1))
    print(f"flagged cells: {len(flags)}   tables to escalate: {tables}")
    for (t, p, f), r in sorted(flags.items()):
        print(f"  {t} {p} {f}: {', '.join(r)}")

    if a.golden:
        gold = {(r["table_id"], r["part_number"]): r for r in load_rows(a.bench / a.golden)}
        e_rows = {(r["table_id"], r["part_number"]): r for r in load_rows(e_dir / "rows.json")}
        def norm(v):
            return None if v is None else round(float(v), 3)
        errors = [(t, p, f) for (t, p), r in e_rows.items() if (t, p) in gold
                  for f in NUMERIC_FIELDS if norm(r.get(f)) != norm(gold[(t, p)].get(f))]
        caught = [e for e in errors if e in flags]
        missed = [e for e in errors if e not in flags]
        fp = [k for k in flags if k not in errors]
        print(f"\nE errors vs golden: {len(errors)}   caught: {len(caught)}   missed: {missed or 'none'}")
        print(f"flagged but correct (false positives): {len(fp)}")
        print(f"errors inside escalated tables: {sum(e[0] in tables for e in errors)}/{len(errors)}")

    if a.vision:
        vis = load_rows(a.bench / a.vision)
        hybrid = [r for r in load_rows(e_dir / "rows.json") if r["table_id"] not in tables]
        hybrid += [r for r in vis if r["table_id"] in tables]
        h_dir = a.bench / "outputs/H_hybrid_E_flagB"
        h_dir.mkdir(exist_ok=True)
        (h_dir / "rows.json").write_text(json.dumps({"candidate": "H_hybrid_E_flagB", "run": 1, "rows": hybrid}, indent=1))
        (h_dir / "LOG.md").write_text(
            "STATUS: OK (simulated)\n\nE (RapidOCR) for every table; tables with a flagged cell "
            f"({', '.join(tables)}) replaced by `{a.vision}`.\nThe vision part reuses an existing Sonnet run (B run3) "
            "instead of a live OpenRouter call. Built by scripts/flag_cells.py.\n")
        print(f"hybrid written: {len(hybrid)} rows -> {h_dir / 'rows.json'}")


if __name__ == "__main__":
    main()
