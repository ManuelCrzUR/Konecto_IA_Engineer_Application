"""Text-to-speech model comparison for D-54 (Sprint 10, wave S1). Paid: runs inside budgeted().

Usage (from backend/):
    uv run python scripts/tts_bench/run.py \
        --models google/gemini-3.8-flash-tts,elevenlabs/eleven-flash-v2.5 \
        --voices Kore,sarah --max-usd 0.10 [--only es1,en1] [--lang es|en] [--split-sentences] [--tag NAME]

Models and voices are aligned by position. For each (model, voice) and text: POST
{LLM_BASE_URL}/audio/speech, measure time to first byte and total time, save the audio under
--out-dir, then look up the real cost via GET /generation?id=. Writes scripts/tts_bench/REPORT.md (REPORT-<tag>.md with --tag).
--split-sentences synthesizes each sentence in order and joins the audio; --lang sets the
ElevenLabs language_code (Gemini ignores it).
Gemini returns only PCM (wrapped in WAV here); the rest is requested as mp3. Never prints the key.
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

import httpx
from dotenv import load_dotenv

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1]))
from helpers import (
    build_body,
    estimate_cost,
    parse_rate,
    pcm_to_wav,
    split_sentences,
    sum_costs,
)

from app.spend import budgeted

# Plain spoken text, as the app's speakableText sends it (values from data/processed/actuators.json).
TEXTS: dict[str, str] = {
    "es1": "Para el 764A00-11300000/A, el torque on/off es 750 Nm, o 6650 in-lbs, "
    "y el modulante es 680 Nm.",
    "es2": "Te recomiendo dos opciones. El 762B00-11320000/A entrega 200 Nm de torque on/off "
    "y consume 1.1 A de corriente a plena carga a 60 Hz. El 763B00-11330C00/A entrega 500 Nm "
    "y consume 2.0 A a 60 Hz. Ambos son weatherproof de 220V.",
    "en1": "For 765X30-11320000/A, the motor power is 180 W and the full load current "
    "at 60 Hz is 2.4 A.",
    "en2": "I could not find the part number 764Z99-11300000. Did you mean 764A00-11300000/A, "
    "762B00-11320000/A or 763B00-11330C00/A? Tell me which one and I will give you its data.",
}
HEADER = (
    "| model | voice | lang | split | ok | TTFB s | first audio ready s | total s | audio s"
    " | real USD | est. USD | est. / 300 ch |"
)
MP3_BITRATE = 128_000  # bits per second, used only for the duration estimate


def request_one(client: httpx.Client, base: str, key: str, body: dict, t0: float) -> dict:
    """One /audio/speech call. Times are seconds since t0 (ttfb, done). Returns data or error."""
    out: dict = {}
    chunks: list[bytes] = []
    try:
        with client.stream(
            "POST", f"{base}/audio/speech", json=body, headers={"Authorization": f"Bearer {key}"}
        ) as r:
            out["status"] = r.status_code
            out["gen_id"] = r.headers.get("X-Generation-Id")
            out["ctype"] = r.headers.get("Content-Type")
            for chunk in r.iter_bytes():
                if not chunks:
                    out["ttfb"] = time.monotonic() - t0
                chunks.append(chunk)
        out["done"] = time.monotonic() - t0
    except httpx.HTTPError as e:
        return {**out, "error": type(e).__name__}
    data = b"".join(chunks)
    if out["status"] != 200:
        return {**out, "error": data[:200].decode("utf-8", "replace")}
    return {**out, "data": data}


def synth(client, base, key, model, voice, cid, out: Path, lang=None, split=False, tag=""):
    gemini = "gemini" in model
    parts = split_sentences(TEXTS[cid]) if split else [TEXTS[cid]]
    res: dict = {"model": model, "voice": voice, "id": cid, "gen_ids": []}
    t0 = time.monotonic()
    datas: list[bytes] = []
    rate = 24000
    for i, part in enumerate(parts):
        r = request_one(client, base, key, build_body(model, voice, part, lang), t0)
        if r.get("gen_id"):
            res["gen_ids"].append(r["gen_id"])
        if "error" in r:
            return {**res, "error": r["error"], "status": r.get("status")}
        if i == 0:
            res["ttfb"], res["first_total"] = r["ttfb"], r["done"]
            rate = parse_rate(r.get("ctype"))
        datas.append(r["data"])
    res["total"] = time.monotonic() - t0
    data = b"".join(datas)  # PCM frames or MP3 bytes: plain concatenation
    res["bytes"] = len(data)
    stem = f"{model.replace('/', '_')}__{voice}__{cid}" + (f"__{tag}" if tag else "")
    if gemini:
        res["file"] = out / f"{stem}.wav"
        res["audio_s"] = pcm_to_wav(data, res["file"], rate)
    else:
        res["file"] = out / f"{stem}.mp3"
        res["file"].write_bytes(data)
        res["audio_s"] = len(data) * 8 / MP3_BITRATE  # estimate
    res["est"] = sum(estimate_cost(model, p, res["audio_s"] / len(parts)) for p in parts)
    return res


def real_cost(client: httpx.Client, base: str, key: str, gen_id: str | None) -> float | None:
    if not gen_id:
        return None
    try:
        for _ in range(3):
            r = client.get(
                f"{base}/generation",
                params={"id": gen_id},
                headers={"Authorization": f"Bearer {key}"},
            )
            if r.status_code == 200:
                return r.json()["data"]["total_cost"]
            time.sleep(1.5)  # stats are booked late
    except (httpx.HTTPError, KeyError, ValueError, TypeError):
        pass
    return None


def _mean(xs: list[float]) -> float:
    return sum(xs) / len(xs) if xs else 0.0


def report(rows: list[dict], pairs: list[tuple[str, str]], lang: str | None, split: bool, tag: str):
    lines = [
        "# Text-to-speech comparison (D-54, Sprint 10 wave S1)",
        "",
        "MP3 durations are estimates (bytes at 128 kbps); estimated costs use the D-54 prices.",
        "First audio ready = time until playback could start (first sentence if split, else total).",
        "",
        HEADER,
        "|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    first_row = len(lines)
    for m, v in pairs:
        rs = [r for r in rows if (r["model"], r["voice"]) == (m, v)]
        ok = [r for r in rs if "error" not in r]
        real = [r["cost"] for r in ok if r.get("cost") is not None]
        chars = sum(len(TEXTS[r["id"]]) for r in ok)
        est = sum(r["est"] for r in ok)
        ready = [r["first_total"] if split else r["total"] for r in ok]
        label = f"`{m}`" + (f" ({tag})" if tag else "")
        lines.append(
            f"| {label} | {v} | {lang or '-'} | {'yes' if split else 'no'} | {len(ok)}/{len(rs)} "
            f"| {_mean([r['ttfb'] for r in ok]):.2f} | {_mean(ready):.2f} "
            f"| {_mean([r['total'] for r in ok]):.2f} | {sum(r['audio_s'] for r in ok):.1f} "
            f"| {f'{sum(real):.6f}' if real else ''} | {est:.6f} "
            f"| {est / chars * 300 if chars else 0:.6f} |"
        )
    lines += ["", "## Samples", ""]
    for r in rows:
        lines.append(f"- `{r['model']}` / {r['voice']} / {r['id']}: {r.get('file') or r['error']}")
    (HERE / (f"REPORT-{tag}.md" if tag else "REPORT.md")).write_text("\n".join(lines) + "\n")
    print("\n".join(lines[first_row : first_row + len(pairs)]))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", required=True)
    ap.add_argument("--voices", required=True)
    ap.add_argument("--max-usd", type=float, default=0.10)
    ap.add_argument("--only", default="")
    ap.add_argument("--out-dir", type=Path, default=HERE / "audio")
    ap.add_argument("--lang", choices=["es", "en"], default=None)
    ap.add_argument("--split-sentences", action="store_true")
    ap.add_argument("--tag", default="")
    args = ap.parse_args()
    models = [m.strip() for m in args.models.split(",") if m.strip()]
    voices = [v.strip() for v in args.voices.split(",") if v.strip()]
    if len(models) != len(voices):
        sys.exit("--models and --voices must have the same number of entries")
    ids = [i for i in TEXTS if not args.only or i in args.only.split(",")]
    load_dotenv(HERE.parents[1].parent / ".env")
    key = os.environ.get("LLM_API_KEY", "").strip()
    base = (os.environ.get("LLM_BASE_URL", "").strip() or "https://openrouter.ai/api/v1").rstrip(
        "/"
    )
    args.out_dir.mkdir(parents=True, exist_ok=True)
    rows: list[dict] = []
    with (
        budgeted("tts-bench", args.max_usd, model=",".join(models)) as budget,
        httpx.Client(timeout=60) as client,
    ):
        for model, voice in zip(models, voices, strict=True):
            for cid in ids:
                rows.append(
                    synth(
                        client,
                        base,
                        key,
                        model,
                        voice,
                        cid,
                        args.out_dir,
                        args.lang,
                        args.split_sentences,
                        args.tag,
                    )
                )
                budget.calls += max(1, len(rows[-1]["gen_ids"]))
                print({k: v for k, v in rows[-1].items() if k != "file"}, flush=True)
            budget.check()
        for r in rows:
            r["cost"] = (
                None
                if "error" in r
                else sum_costs([real_cost(client, base, key, g) for g in r["gen_ids"]])
            )
    report(rows, list(zip(models, voices, strict=True)), args.lang, args.split_sentences, args.tag)


if __name__ == "__main__":
    main()
