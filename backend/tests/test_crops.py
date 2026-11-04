"""Tests for PDF -> table crops (needs poppler's pdfimages and the raw PDF)."""

from __future__ import annotations

import io
import shutil
from pathlib import Path

import pytest
from PIL import Image

from app.ingestion import crops
from app.ingestion.crops import TABLE_BOXES, CropError, crop_tables, extract_page_images

PDF = Path(__file__).resolve().parent.parent / "data" / "raw" / "series_76_electric_data.pdf"

needs_poppler = pytest.mark.skipif(shutil.which("pdfimages") is None, reason="poppler missing")


@needs_poppler
def test_extract_page_images_returns_six_pngs(tmp_path: Path) -> None:
    paths = extract_page_images(PDF, tmp_path)
    assert len(paths) == 6
    assert all(p.suffix == ".png" for p in paths)
    assert paths == sorted(paths)


@needs_poppler
def test_crop_tables_ids_and_sizes(tmp_path: Path) -> None:
    result = crop_tables(PDF, tmp_path, scale=2)
    assert set(result) == set(TABLE_BOXES)
    assert len(result) == 7
    for table_id, data in result.items():
        x0, y0, x1, y1 = TABLE_BOXES[table_id][1]
        with Image.open(io.BytesIO(data)) as im:
            assert im.format == "PNG"
            assert im.size == ((x1 - x0) * 2, (y1 - y0) * 2)


@needs_poppler
def test_crop_tables_scale_one(tmp_path: Path) -> None:
    result = crop_tables(PDF, tmp_path, scale=1)
    for table_id, data in result.items():
        x0, y0, x1, y1 = TABLE_BOXES[table_id][1]
        with Image.open(io.BytesIO(data)) as im:
            assert im.size == (x1 - x0, y1 - y0)


@needs_poppler
def test_crops_are_deterministic(tmp_path: Path) -> None:
    first = crop_tables(PDF, tmp_path / "a")
    second = crop_tables(PDF, tmp_path / "b")
    assert first == second


def test_missing_pdf_raises(tmp_path: Path) -> None:
    if shutil.which("pdfimages") is None:
        pytest.skip("poppler missing")
    with pytest.raises(CropError):
        crop_tables(tmp_path / "nope.pdf", tmp_path / "w")


def test_missing_pdfimages_raises(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(crops.shutil, "which", lambda _name: None)
    with pytest.raises(CropError, match="poppler"):
        crop_tables(PDF, tmp_path)
