"""Pipeline orchestration tests. Fast ones fake crops/OCR/flags/escalator (no OCR, no LLM)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import Mock

import pytest

from app.domain.models import TABLE_IDS, Actuator
from app.ingestion import pipeline
from app.ingestion.flags import Flag
from app.ingestion.ocr import OcrCell, OcrResult
from app.ingestion.pipeline import ExtractionError, extract_catalog, extract_with_report
from app.ingestion.table_meta import TABLE_META

BACKEND_DIR = Path(__file__).resolve().parents[1]
GOLDEN = BACKEND_DIR / "tests" / "fixtures" / "golden_draft.json"
SEED = BACKEND_DIR / "data" / "processed" / "actuators.json"
PDF = BACKEND_DIR / "data" / "raw" / "series_76_electric_data.pdf"
BAD_PN = "761Y30-11320000/A"
BAD_TABLE = "T7_xp_220v_1ph"


def golden() -> list[Actuator]:
    rows = json.loads(GOLDEN.read_text())["rows"]
    return [Actuator.model_validate({k: v for k, v in r.items() if k != "unparsed"}) for r in rows]


def corrupted() -> list[Actuator]:
    return [
        r.model_copy(update={"onoff_torque_nm": 6.0}) if r.part_number == BAD_PN else r
        for r in golden()
    ]


def fake_cells() -> list[OcrCell]:
    return [
        OcrCell(table_id=BAD_TABLE, part_number=BAD_PN, field="onoff_torque_nm", raw="6", conf=0.5),
        OcrCell(
            table_id="T1_wp_110v_1ph",
            part_number="761A00-11300000/A",
            field="fla_60hz_a",
            raw="1.2",
            conf=0.99,
        ),
    ]


def fake_flags(cells: list[OcrCell], issues: list) -> list[Flag]:
    return [
        Flag(
            table_id=c.table_id,
            part_number=c.part_number,
            field=c.field,
            raw=c.raw,
            reasons=["low_conf"],
        )
        for c in cells
        if c.conf < 0.9
    ]


def fake_tables(flags: list[Flag]) -> list[str]:
    return sorted({f.table_id for f in flags})


def golden_escalator(table_id: str, png: bytes) -> list[Actuator]:
    return [r for r in golden() if r.table_id == table_id]


@pytest.fixture
def fakes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(pipeline, "crop_tables", lambda pdf, work: {t: b"png" for t in TABLE_IDS})
    monkeypatch.setattr(
        pipeline, "ocr_tables", lambda crops: OcrResult(rows=corrupted(), cells=fake_cells())
    )
    monkeypatch.setattr(pipeline, "flag_cells", fake_flags)
    monkeypatch.setattr(pipeline, "tables_to_escalate", fake_tables)


def test_escalation_replaces_table_and_matches_golden(fakes: None) -> None:
    catalog, report = extract_with_report(PDF, golden_escalator)
    assert catalog.rows == golden()
    assert report.escalated == [BAD_TABLE]
    assert report.flagged_cells == 1


def test_no_escalator_raises_listing_cell(fakes: None) -> None:
    with pytest.raises(ExtractionError) as err:
        extract_catalog(PDF, None)
    msg = str(err.value)
    assert f"{BAD_TABLE}/{BAD_PN}/onoff_torque_nm raw='6'" in msg
    assert "LLM_API_KEY" in msg and "EXTRACT_LLM_MODEL" in msg


def test_nothing_flagged_never_escalates(monkeypatch: pytest.MonkeyPatch, fakes: None) -> None:
    monkeypatch.setattr(
        pipeline, "ocr_tables", lambda crops: OcrResult(rows=golden(), cells=fake_cells()[1:])
    )
    escalator = Mock(side_effect=golden_escalator)
    catalog, report = extract_with_report(PDF, escalator)
    escalator.assert_not_called()
    assert report.escalated == []
    assert catalog.rows == golden()


def test_escalated_table_failing_validation_raises(fakes: None) -> None:
    def bad(table_id: str, png: bytes) -> list[Actuator]:
        return [r for r in corrupted() if r.table_id == table_id]

    with pytest.raises(ExtractionError, match="failed validation"):
        extract_catalog(PDF, bad)


def test_catalog_tables_are_table_meta(fakes: None) -> None:
    assert extract_catalog(PDF, golden_escalator).tables == TABLE_META


def test_table_meta_matches_seed_json() -> None:
    tables = json.loads(SEED.read_text())["tables"]
    assert [t.model_dump() for t in TABLE_META] == tables


@pytest.mark.slow
def test_end_to_end_real_ocr_matches_golden() -> None:
    catalog = extract_catalog(PDF, golden_escalator)
    assert len(catalog.rows) == len(golden())
    for got, want in zip(catalog.rows, golden(), strict=True):
        assert got.model_dump() == want.model_dump(), want.part_number
