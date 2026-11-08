"""Pure helpers for the TTS benchmark (no network, no env): request body, sentences, cost math."""

from __future__ import annotations

import re
from pathlib import Path

from app.speech.tts import parse_rate
from app.speech.tts import pcm_to_wav as _pcm_to_wav

__all__ = ["parse_rate"]

# USD prices from D-54 (estimates, per character for ElevenLabs, per token for Gemini).
PRICE_PER_CHAR = {"eleven-flash-v2.5": 0.00004, "eleven-turbo-v2.5": 0.00004}
PRICE_PER_CHAR_DEFAULT = 0.00008  # eleven-multilingual-v2 and unknown ElevenLabs models
GEMINI_IN, GEMINI_OUT = 0.0000005, 0.000009

# A sentence ends at . ? ! followed by whitespace; "1.1" and "764A00-11300000/A," never match.
_SENTENCE_END = re.compile(r"(?<=[.?!])\s+")


def split_sentences(text: str) -> list[str]:
    return [s for s in _SENTENCE_END.split(text.strip()) if s]


def build_body(model: str, voice: str, text: str, lang: str | None = None) -> dict:
    """Request JSON for /audio/speech. Gemini only returns PCM; the rest is requested as mp3."""
    gemini = "gemini" in model
    body: dict = {
        "model": model,
        "input": text,
        "voice": voice,
        "response_format": "pcm" if gemini else "mp3",
    }
    if lang and model.startswith("elevenlabs/"):
        body["provider"] = {"options": {"elevenlabs": {"language_code": lang}}}
    return body


def pcm_to_wav(pcm: bytes, path: Path, rate: int = 24000) -> float:
    """Write 16-bit mono PCM as a WAV file (app.speech.tts); return its duration in seconds."""
    path.write_bytes(_pcm_to_wav(pcm, rate))
    return len(pcm) // 2 / rate


def estimate_cost(model: str, text: str, audio_s: float) -> float:
    if "gemini" in model:
        return (len(text) / 4) * GEMINI_IN + audio_s * 25 * GEMINI_OUT
    return len(text) * PRICE_PER_CHAR.get(model.split("/")[-1], PRICE_PER_CHAR_DEFAULT)


def sum_costs(costs: list[float | None]) -> float | None:
    """Total of per-sentence real costs; None if any lookup is missing (partial sums mislead)."""
    return None if not costs or any(c is None for c in costs) else sum(costs)  # type: ignore[arg-type]
