"""Build data/processed/actuators.json from the verified golden draft.

Stdlib plus app.ingestion.table_meta (titles and notes). Run from backend/ with:

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
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.ingestion.table_meta import TABLE_META

DEFAULT_GOLDEN = BACKEND_DIR / "tests" / "fixtures" / "golden_draft.json"
DEFAULT_OUT = BACKEND_DIR / "data" / "processed" / "actuators.json"
EXPECTED_ROWS = 68


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
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--golden", type=Path, default=DEFAULT_GOLDEN, help="path to golden_draft.json"
    )
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help="output actuators.json")
    parser.add_argument("--force", action="store_true", help="overwrite an existing output file")
    args = parser.parse_args()

    if args.out.exists() and not args.force:
        fail(f"{args.out} already exists; refusing to overwrite. Pass --force to replace it.")

    rows = load_rows(args.golden)
    payload = {"tables": [t.model_dump() for t in TABLE_META], "rows": rows}

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {len(rows)} rows and {len(TABLE_META)} tables to {args.out}")


if __name__ == "__main__":
    main()
