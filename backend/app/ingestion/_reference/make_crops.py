"""Crop each of the 7 tables (with its sub-title row) from the extracted page images.
Boxes were set by eye from the page PNGs; crops are upscaled 2x (LANCZOS) for readability.
Usage: python make_crops.py <bench_dir>"""
import json, sys
from pathlib import Path
from PIL import Image

# table_id -> (page image, (x0, y0, x1, y1))
BOXES = {
    "T1_wp_110v_1ph":      ("page-001.png", (0, 0, 727, 302)),
    "T2_wp_220v_1ph":      ("page-001.png", (0, 304, 727, 692)),
    "T3_wp_220v_3ph":      ("page-003.png", (0, 0, 718, 252)),
    "T4_xp_24v_onoff":     ("page-004.png", (0, 145, 1162, 405)),
    "T5_xp_24vdc_mod":     ("page-004.png", (0, 418, 1162, 676)),
    "T6_xp_110v_1ph":      ("page-005.png", (0, 150, 1126, 580)),
    "T7_xp_220v_1ph":      ("page-005.png", (0, 594, 1126, 1024)),
}

def main(bench):
    pages, out = bench / "inputs/pages", bench / "inputs/crops"
    out.mkdir(parents=True, exist_ok=True)
    manifest = {}
    for tid, (img, box) in BOXES.items():
        im = Image.open(pages / img).crop(box)
        im.save(out / f"{tid}.png")
        im.resize((im.width * 2, im.height * 2), Image.LANCZOS).save(out / f"{tid}@2x.png")
        manifest[tid] = {"page_image": img, "box": box}
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2))

if __name__ == "__main__":
    main(Path(sys.argv[1]))
