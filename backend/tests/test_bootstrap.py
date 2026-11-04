"""ensure_data() against a dedicated Postgres. The real actuators.json is never written."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from app.bootstrap import ensure_data
from app.db import actuators_repo
from app.domain.models import Catalog
from app.ingestion import pipeline
from app.ingestion.store_json import read_catalog

BACKEND_DIR = Path(__file__).resolve().parents[1]
REAL_JSON = BACKEND_DIR / "data" / "processed" / "actuators.json"
PDF = BACKEND_DIR / "data" / "raw" / "series_76_electric_data.pdf"


@pytest.fixture
def json_path(tmp_path: Path) -> Path:
    dst = tmp_path / "actuators.json"
    shutil.copy(REAL_JSON, dst)
    return dst


@pytest.fixture
def golden_catalog() -> Catalog:
    return Catalog.model_validate_json(REAL_JSON.read_text())


@pytest.fixture
def no_extract(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*a: object, **k: object) -> Catalog:
        raise AssertionError("extract_catalog must not be called")

    monkeypatch.setattr(pipeline, "extract_catalog", boom)


def test_empty_db_loads_json_then_noop(pg, json_path: Path, no_extract: None) -> None:
    s = ensure_data(pg, json_path, PDF)
    assert (s.source, s.rows) == ("json", 68)
    assert actuators_repo.count(pg) == 68
    s = ensure_data(pg, json_path, PDF)
    assert (s.source, s.rows) == ("db", 68)


def test_partial_load_is_completed(pg, json_path: Path, no_extract: None) -> None:
    ensure_data(pg, json_path, PDF)
    pg.execute(
        "DELETE FROM actuators WHERE part_number IN "
        "(SELECT part_number FROM actuators ORDER BY part_number LIMIT 10)"
    )
    assert actuators_repo.count(pg) == 58
    s = ensure_data(pg, json_path, PDF)
    assert (s.source, s.rows) == ("json", 68)
    assert actuators_repo.count(pg) == 68


def test_stale_extra_row_is_removed(pg, json_path: Path, no_extract: None) -> None:
    ensure_data(pg, json_path, PDF)
    pg.execute(
        "INSERT INTO actuators (table_id, part_number, enclosure, certifications, voltage, "
        "current_type, service, csa_certified, has_data) "
        "SELECT table_id, '999Z99-99999999/A', enclosure, certifications, voltage, "
        "current_type, service, csa_certified, has_data FROM actuators LIMIT 1"
    )
    assert actuators_repo.count(pg) == 69
    s = ensure_data(pg, json_path, PDF)
    assert (s.source, s.rows) == ("json", 68)
    assert actuators_repo.count(pg) == 68


def test_missing_json_extracts_from_pdf(
    pg, json_path: Path, golden_catalog: Catalog, monkeypatch: pytest.MonkeyPatch
) -> None:
    json_path.unlink()
    monkeypatch.setattr(pipeline, "extract_catalog", lambda pdf, esc=None: golden_catalog)
    s = ensure_data(pg, json_path, PDF)
    assert (s.source, s.rows) == ("pdf", 68)
    assert read_catalog(json_path) == golden_catalog
    assert actuators_repo.count(pg) == 68


def test_corrupt_json_is_rewritten(
    pg, json_path: Path, golden_catalog: Catalog, monkeypatch: pytest.MonkeyPatch
) -> None:
    json_path.write_text(json_path.read_text()[:500])
    monkeypatch.setattr(pipeline, "extract_catalog", lambda pdf, esc=None: golden_catalog)
    s = ensure_data(pg, json_path, PDF)
    assert s.source == "pdf"
    assert read_catalog(json_path) == golden_catalog


def test_invalid_value_json_is_reextracted(
    pg, json_path: Path, golden_catalog: Catalog, monkeypatch: pytest.MonkeyPatch
) -> None:
    data = json.loads(json_path.read_text())
    data["rows"][0]["onoff_duty_cycle_pct"] = 150
    json_path.write_text(json.dumps(data))
    monkeypatch.setattr(pipeline, "extract_catalog", lambda pdf, esc=None: golden_catalog)
    s = ensure_data(pg, json_path, PDF)
    assert s.source == "pdf"
    assert read_catalog(json_path) == golden_catalog


def test_extraction_failure_raises_and_db_untouched(
    pg, json_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    json_path.write_text("{ not json")

    def fail(pdf: Path, esc: object = None) -> Catalog:
        raise pipeline.ExtractionError("doubtful cells")

    monkeypatch.setattr(pipeline, "extract_catalog", fail)
    with pytest.raises(pipeline.ExtractionError):
        ensure_data(pg, json_path, PDF)
    assert actuators_repo.count(pg) == 0
    assert json_path.read_text() == "{ not json"
