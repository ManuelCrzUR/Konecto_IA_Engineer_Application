"""Tests for the processed seed data (data/processed/actuators.json).

No database and no LLM. Covers the output of scripts/build_seed.py against the
verified golden draft and the raw PDF checksum.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import subprocess
import sys
from collections import Counter
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]
SEED_PATH = BACKEND_DIR / "data" / "processed" / "actuators.json"
RAW_DIR = BACKEND_DIR / "data" / "raw"
PDF_PATH = RAW_DIR / "series_76_electric_data.pdf"
SHA_FILE = RAW_DIR / "SHA256SUMS"
BUILD_SCRIPT = BACKEND_DIR / "scripts" / "build_seed.py"

EXPECTED_TABLE_COUNTS = {
    "T1_wp_110v_1ph": 11,
    "T2_wp_220v_1ph": 16,
    "T3_wp_220v_3ph": 11,
    "T4_xp_24v_onoff": 5,
    "T5_xp_24vdc_mod": 5,
    "T6_xp_110v_1ph": 10,
    "T7_xp_220v_1ph": 10,
}


def _load_build_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("build_seed", BUILD_SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


BUILD = _load_build_module()
GOLDEN_PATH = Path(os.environ.get("SERIES76_GOLDEN", BUILD.DEFAULT_GOLDEN))


@pytest.fixture(scope="module")
def seed() -> dict[str, Any]:
    assert SEED_PATH.is_file(), f"missing {SEED_PATH}; run scripts/build_seed.py"
    return json.loads(SEED_PATH.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def test_seed_file_exists() -> None:
    assert SEED_PATH.is_file()


def test_has_68_rows(seed: dict[str, Any]) -> None:
    assert len(seed["rows"]) == 68


def test_per_table_counts(seed: dict[str, Any]) -> None:
    counts = Counter(row["table_id"] for row in seed["rows"])
    assert dict(counts) == EXPECTED_TABLE_COUNTS


def test_part_numbers_unique(seed: dict[str, Any]) -> None:
    part_numbers = [row["part_number"] for row in seed["rows"]]
    assert len(part_numbers) == len(set(part_numbers))


def test_no_unparsed_key(seed: dict[str, Any]) -> None:
    assert all("unparsed" not in row for row in seed["rows"])


def test_seven_tables_with_titles(seed: dict[str, Any]) -> None:
    tables = seed["tables"]
    assert len(tables) == 7
    assert [t["table_id"] for t in tables] == list(EXPECTED_TABLE_COUNTS)
    for table in tables:
        assert isinstance(table["title"], str) and table["title"].strip(), table["table_id"]
        assert isinstance(table["notes"], list), table["table_id"]


@pytest.mark.skipif(not GOLDEN_PATH.is_file(), reason=f"golden file not available: {GOLDEN_PATH}")
def test_rows_equal_golden_field_by_field(seed: dict[str, Any]) -> None:
    golden_rows = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))["rows"]
    golden_by_pn = {row["part_number"]: row for row in golden_rows}
    seed_by_pn = {row["part_number"]: row for row in seed["rows"]}

    assert set(seed_by_pn) == set(golden_by_pn)
    for pn, golden_row in golden_by_pn.items():
        expected = {k: v for k, v in golden_row.items() if k != "unparsed"}
        assert seed_by_pn[pn] == expected, f"mismatch for {pn}"


def test_pdf_sha256_matches_sha256sums() -> None:
    assert PDF_PATH.is_file(), f"missing {PDF_PATH}"
    assert SHA_FILE.is_file(), f"missing {SHA_FILE}"
    expected_hash, expected_name = SHA_FILE.read_text(encoding="utf-8").split()[:2]
    assert expected_name == PDF_PATH.name
    assert _sha256(PDF_PATH) == expected_hash


def test_build_refuses_to_overwrite_without_force(tmp_path: Path) -> None:
    # Never point the script at the committed seed: if the guard regressed,
    # the test itself would overwrite it (CLAUDE.md §9).
    out = tmp_path / "actuators.json"
    out.write_text("sentinel", encoding="utf-8")
    before_mtime = out.stat().st_mtime_ns

    result = subprocess.run(
        [sys.executable, str(BUILD_SCRIPT), "--out", str(out)],
        cwd=BACKEND_DIR,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode != 0
    assert "refusing to overwrite" in result.stderr
    assert out.read_text(encoding="utf-8") == "sentinel"
    assert out.stat().st_mtime_ns == before_mtime


def test_build_reproduces_committed_seed(tmp_path: Path) -> None:
    """build_seed (validated + atomic writer) yields exactly the committed JSON."""
    out = tmp_path / "actuators.json"
    result = subprocess.run(
        [sys.executable, str(BUILD_SCRIPT), "--out", str(out)],
        cwd=BACKEND_DIR, capture_output=True, text=True, check=False,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(out.read_text(encoding="utf-8")) == json.loads(
        SEED_PATH.read_text(encoding="utf-8")
    )
