"""PDF -> one PNG crop per table (input of OCR and of the vision escalation).

The PDF has no text layer; each page is an embedded image. We extract the
embedded images with poppler's `pdfimages -png` (no re-rendering, original
pixels) and crop each table with fixed boxes measured on this document
(TABLE_BOXES, from the benchmark manifest), then upscale `scale`x.
Limitation: the boxes are specific to series_76_electric_data.pdf.
"""

from __future__ import annotations

import io
import shutil
import subprocess
from pathlib import Path

from PIL import Image

# table_id -> (embedded image file name from `pdfimages -png`, (x0, y0, x1, y1))
TABLE_BOXES: dict[str, tuple[str, tuple[int, int, int, int]]] = {
    "T1_wp_110v_1ph": ("page-001.png", (0, 0, 727, 302)),
    "T2_wp_220v_1ph": ("page-001.png", (0, 304, 727, 692)),
    "T3_wp_220v_3ph": ("page-003.png", (0, 0, 718, 252)),
    "T4_xp_24v_onoff": ("page-004.png", (0, 145, 1162, 405)),
    "T5_xp_24vdc_mod": ("page-004.png", (0, 418, 1162, 676)),
    "T6_xp_110v_1ph": ("page-005.png", (0, 150, 1126, 580)),
    "T7_xp_220v_1ph": ("page-005.png", (0, 594, 1126, 1024)),
}


class CropError(RuntimeError):
    """pdfimages missing/failed, or an expected image/box is absent."""


def extract_page_images(pdf_path: Path, out_dir: Path) -> list[Path]:
    """Run `pdfimages -png pdf out_dir/page`; return the PNG paths, sorted."""
    if shutil.which("pdfimages") is None:
        raise CropError(
            "pdfimages not found; install poppler: "
            "`brew install poppler` / `apt-get install poppler-utils`"
        )
    if not pdf_path.is_file():
        raise CropError(f"PDF not found: {pdf_path}")
    out_dir.mkdir(parents=True, exist_ok=True)
    try:
        subprocess.run(
            ["pdfimages", "-png", str(pdf_path), str(out_dir / "page")],
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        raise CropError(f"pdfimages failed: {exc.stderr.strip()}") from exc
    return sorted(out_dir.glob("page-*.png"))


def crop_tables(pdf_path: Path, work_dir: Path, scale: int = 2) -> dict[str, bytes]:
    """table_id -> PNG bytes of the upscaled crop, for all 7 tables."""
    paths = {p.name: p for p in extract_page_images(pdf_path, work_dir)}
    crops: dict[str, bytes] = {}
    for table_id, (image_name, box) in TABLE_BOXES.items():
        if image_name not in paths:
            raise CropError(f"{table_id}: expected image {image_name} not extracted")
        with Image.open(paths[image_name]) as page:
            if box[2] > page.width or box[3] > page.height:
                raise CropError(f"{table_id}: box {box} outside {page.size} image")
            crop = page.crop(box)
        if scale != 1:
            crop = crop.resize((crop.width * scale, crop.height * scale), Image.Resampling.LANCZOS)
        buf = io.BytesIO()
        crop.save(buf, format="PNG")
        crops[table_id] = buf.getvalue()
    return crops
