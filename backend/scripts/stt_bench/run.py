"""Speech-to-text model comparison for D-53 (Sprint 9, wave V1). Paid: runs inside budgeted().

Usage (from backend/):
    uv run python scripts/stt_bench/run.py --models a,b --clips-dir scripts/stt_bench/clips \
        --extra-dir ~/Desktop/voz-pruebas --max-usd 0.05

For every clip and model: POST {LLM_BASE_URL}/audio/transcriptions with base64 audio, then score
whether each expected part number is in the transcript:
- raw: the exact part number (or base) appears as written;
- chars: after removing spaces and punctuation and mapping spoken digits/separators, the
  part-number characters appear in order (what a deterministic normalizer could recover).
Writes scripts/stt_bench/REPORT.md. Never prints the key.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import sys
import time
from pathlib import Path

import httpx
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from app.spend import budgeted

HERE = Path(__file__).resolve().parent
# clip id -> (text read, expected part numbers or bases)
CASES: dict[str, tuple[str, list[str]]] = {
    "s1": (
        "torque on off del siete seis cuatro A cero cero guion ... barra A (es-MX)",
        ["764A00-11300000/A"],
    ),
    "s2": ("Dame el LRA a cincuenta hertz del 763B00-11330C00/A (es-ES)", ["763B00-11330C00/A"]),
    "s3": ("What is the duty cycle of 766A00-11320000/A? (en)", ["766A00-11320000/A"]),
    "s4": ("explosionproof 24 V modulante, al menos 100 Nm (es-MX)", []),
    "s5": (
        "Compare 764X30-11320000/A and 765A00-11320000/A (en)",
        ["764X30-11320000/A", "765A00-11320000/A"],
    ),
    "s6": ("¿Qué potencia tiene el 761A00-11330C00 barra A? (es-ES)", ["761A00-11330C00/A"]),
    "s7": ("y cuántos arranques por hora tiene el 762X30 (es-MX)", ["762X30"]),
    "1": ("¿Cuál es el torque del 764A00-11300000/A? (user)", ["764A00-11300000/A"]),
    "2": ("Dame la corriente FLA a 60 hertz del 762B00-11320000/A (user)", ["762B00-11320000/A"]),
    "3": ("What is the motor power of 765X30-11320000/A? (user)", ["765X30-11320000/A"]),
    "4": ("200 Nm, 220 voltios, intemperie, modulante (user)", []),
    "5": ("¿Y la velocidad a 50 hertz del 761Y30? (user)", ["761Y30"]),
}
_WORDS = {
    "cero": "0",
    "zero": "0",
    "uno": "1",
    "one": "1",
    "dos": "2",
    "two": "2",
    "tres": "3",
    "three": "3",
    "cuatro": "4",
    "four": "4",
    "cinco": "5",
    "five": "5",
    "seis": "6",
    "six": "6",
    "siete": "7",
    "seven": "7",
    "ocho": "8",
    "eight": "8",
    "nueve": "9",
    "nine": "9",
}
_FORMATS = {
    ".m4a": "m4a",
    ".mp3": "mp3",
    ".wav": "wav",
    ".ogg": "ogg",
    ".webm": "webm",
    ".aac": "aac",
    ".flac": "flac",
}


def _alnum(text: str) -> str:
    words = [_WORDS.get(w.lower(), w) for w in re.split(r"(\W+)", text)]
    return re.sub(r"[^0-9A-Z]", "", "".join(words).upper())


def score(text: str, expected: list[str]) -> tuple[int, int]:
    raw = sum(
        1
        for pn in expected
        if pn.upper() in text.upper() or pn.upper().removesuffix("/A") in text.upper()
    )
    chars = sum(1 for pn in expected if _alnum(pn.removesuffix("/A")) in _alnum(text))
    return raw, chars


def transcribe(client: httpx.Client, base: str, key: str, model: str, clip: Path) -> dict:
    body = {
        "model": model,
        "input_audio": {
            "data": base64.b64encode(clip.read_bytes()).decode(),
            "format": _FORMATS[clip.suffix],
        },
        "temperature": 0,
    }
    t0 = time.monotonic()
    r = client.post(
        f"{base}/audio/transcriptions", json=body, headers={"Authorization": f"Bearer {key}"}
    )
    dt = time.monotonic() - t0
    if r.status_code != 200:
        return {"error": f"{r.status_code} {r.text[:160]}", "seconds": dt}
    data = r.json()
    return {
        "text": data.get("text", ""),
        "cost": (data.get("usage") or {}).get("cost"),
        "seconds": dt,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", required=True)
    ap.add_argument("--clips-dir", type=Path, default=HERE / "clips")
    ap.add_argument("--extra-dir", type=Path, default=None)
    ap.add_argument("--only", default="")
    ap.add_argument("--max-usd", type=float, default=0.05)
    args = ap.parse_args()
    load_dotenv(HERE.parents[1].parent / ".env")
    key = os.environ.get("LLM_API_KEY", "").strip()
    base = os.environ.get("LLM_BASE_URL", "").strip() or "https://openrouter.ai/api/v1"
    clips: dict[str, Path] = {}
    for d in [args.clips_dir, args.extra_dir]:
        if d and d.expanduser().is_dir():
            for f in sorted(d.expanduser().iterdir()):
                if f.suffix.lower() in _FORMATS and f.stem in CASES:
                    clips[f.stem] = f
    if args.only:
        clips = {k: v for k, v in clips.items() if k in args.only.split(",")}
    models = [m.strip() for m in args.models.split(",") if m.strip()]
    rows: list[dict] = []
    with (
        budgeted("stt-bench", args.max_usd, model=",".join(models)) as budget,
        httpx.Client(timeout=60) as client,
    ):
        for model in models:
            for cid, clip in clips.items():
                out = transcribe(client, base, key, model, clip)
                budget.calls += 1
                raw, chars = score(out.get("text", ""), CASES[cid][1])
                rows.append(
                    {
                        "model": model,
                        "clip": cid,
                        "raw": raw,
                        "chars": chars,
                        "n": len(CASES[cid][1]),
                        **out,
                    }
                )
                print(json.dumps(rows[-1], ensure_ascii=False)[:300], flush=True)
            budget.check()
    _report(rows, models)


def _report(rows: list[dict], models: list[str]) -> None:
    lines = [
        "# Speech-to-text comparison (D-53, Sprint 9 wave V1)",
        "",
        "| model | part numbers exact | after normalization | errors | mean latency s | cost USD |",
        "|---|---|---|---|---|---|",
    ]
    for m in models:
        rs = [r for r in rows if r["model"] == m]
        n = sum(r["n"] for r in rs)
        cost = sum(r.get("cost") or 0 for r in rs)
        lat = sum(r["seconds"] for r in rs) / max(len(rs), 1)
        errs = sum(1 for r in rs if "error" in r)
        lines.append(
            f"| `{m}` | {sum(r['raw'] for r in rs)}/{n} | {sum(r['chars'] for r in rs)}/{n} | {errs} | {lat:.2f} | {cost:.6f} |"
        )
    lines += ["", "## Transcripts", ""]
    for r in rows:
        lines.append(
            f"- `{r['model']}` / {r['clip']} ({CASES[r['clip']][0]}): {r.get('text') or r.get('error')!r}"
        )
    (HERE / "REPORT.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines[: 4 + len(models)]))


if __name__ == "__main__":
    main()
