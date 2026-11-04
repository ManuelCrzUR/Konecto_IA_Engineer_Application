"""Tests for app.ingestion.store_json (read/write of actuators.json).

No database and no LLM. Writes only go to pytest's tmp_path; the real
data/processed/actuators.json is read but never written.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from app.domain.models import Catalog
from app.ingestion import store_json
from app.ingestion.store_json import CatalogFileError, read_catalog, write_catalog

BACKEND_DIR = Path(__file__).resolve().parents[1]
SEED_PATH = BACKEND_DIR / "data" / "processed" / "actuators.json"


@pytest.fixture
def seed_catalog() -> Catalog:
    catalog = read_catalog(SEED_PATH)
    assert catalog is not None
    return catalog


def _load_json(path: Path) -> dict[str, Any]:
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return data


def test_round_trip_real_seed(seed_catalog: Catalog, tmp_path: Path) -> None:
    out = tmp_path / "actuators.json"
    write_catalog(seed_catalog, out)
    assert read_catalog(out) == seed_catalog


def test_written_file_matches_seed_shape(seed_catalog: Catalog, tmp_path: Path) -> None:
    out = tmp_path / "actuators.json"
    write_catalog(seed_catalog, out)

    original = _load_json(SEED_PATH)
    written = _load_json(out)

    assert set(written) == {"tables", "rows"}
    assert written == original
    assert all("has_data" not in row for row in written["rows"])
    assert written["rows"][0].keys() == original["rows"][0].keys()


def test_written_file_is_indented(seed_catalog: Catalog, tmp_path: Path) -> None:
    out = tmp_path / "actuators.json"
    write_catalog(seed_catalog, out)
    assert out.read_text(encoding="utf-8").startswith('{\n  "tables": [\n')


def test_write_refuses_overwrite_without_force(seed_catalog: Catalog, tmp_path: Path) -> None:
    out = tmp_path / "actuators.json"
    out.write_text('{"sentinel": true}', encoding="utf-8")

    with pytest.raises(FileExistsError):
        write_catalog(seed_catalog, out)

    assert out.read_text(encoding="utf-8") == '{"sentinel": true}'


def test_write_force_overwrites(seed_catalog: Catalog, tmp_path: Path) -> None:
    out = tmp_path / "actuators.json"
    out.write_text('{"sentinel": true}', encoding="utf-8")

    write_catalog(seed_catalog, out, force=True)

    assert read_catalog(out) == seed_catalog


def test_write_leaves_no_temp_files(seed_catalog: Catalog, tmp_path: Path) -> None:
    out = tmp_path / "actuators.json"
    write_catalog(seed_catalog, out)
    assert [p.name for p in tmp_path.iterdir()] == ["actuators.json"]


def test_read_missing_returns_none(tmp_path: Path) -> None:
    assert read_catalog(tmp_path / "missing.json") is None


def test_read_truncated_json_raises(seed_catalog: Catalog, tmp_path: Path) -> None:
    out = tmp_path / "actuators.json"
    write_catalog(seed_catalog, out)
    text = out.read_text(encoding="utf-8")
    out.write_text(text[: len(text) // 2], encoding="utf-8")

    with pytest.raises(CatalogFileError, match="not valid JSON") as exc_info:
        read_catalog(out)
    assert str(out) in str(exc_info.value)


def test_read_wrong_shape_raises(tmp_path: Path) -> None:
    out = tmp_path / "actuators.json"
    out.write_text(json.dumps({"tables": [], "rows": [{"part_number": "nope"}]}), encoding="utf-8")

    with pytest.raises(CatalogFileError, match="does not match Catalog schema") as exc_info:
        read_catalog(out)
    assert str(out) in str(exc_info.value)


def test_read_rejects_non_object_root(tmp_path: Path) -> None:
    out = tmp_path / "actuators.json"
    out.write_text("[1, 2, 3]", encoding="utf-8")

    with pytest.raises(CatalogFileError):
        read_catalog(out)


def test_failed_write_keeps_old_file_and_leaves_no_partial(
    seed_catalog: Catalog, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    out = tmp_path / "actuators.json"
    old_content = '{"old": "content"}'
    out.write_text(old_content, encoding="utf-8")

    def boom(*args: Any, **kwargs: Any) -> None:
        raise OSError("disk exploded")

    monkeypatch.setattr(store_json.json, "dump", boom)

    with pytest.raises(OSError, match="disk exploded"):
        write_catalog(seed_catalog, out, force=True)

    assert out.read_text(encoding="utf-8") == old_content
    assert [p.name for p in tmp_path.iterdir()] == ["actuators.json"]


def test_failed_write_without_old_file_leaves_nothing(
    seed_catalog: Catalog, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    out = tmp_path / "actuators.json"

    def boom(*args: Any, **kwargs: Any) -> None:
        raise OSError("disk exploded")

    monkeypatch.setattr(store_json.json, "dump", boom)

    with pytest.raises(OSError):
        write_catalog(seed_catalog, out)

    assert list(tmp_path.iterdir()) == []
