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

from app.domain.models import Actuator, Catalog
from app.ingestion.store_json import write_catalog
from app.ingestion.table_meta import TABLE_META
from app.ingestion.validate import ValidationFailed, assert_valid

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

    # Same gate as any extractor: schema, then the shared invariants, then the
    # same atomic writer the pipeline uses (CLAUDE.md §9: never load doubtful data).
    catalog = Catalog(
        tables=TABLE_META, rows=[Actuator.from_bench_row(r) for r in load_rows(args.golden)]
    )
    try:
        assert_valid(catalog.rows)
    except ValidationFailed as exc:
        fail(f"golden rows fail validation: {exc}")
    write_catalog(catalog, args.out, force=args.force)
    print(f"wrote {len(catalog.rows)} rows and {len(catalog.tables)} tables to {args.out}")


if __name__ == "__main__":
    main()
