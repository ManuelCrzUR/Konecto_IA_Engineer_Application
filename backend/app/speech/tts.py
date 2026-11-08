"""OpenRouter text-to-speech client (D-54). One call, no retries, nothing stored.

Contract:
- synthesize(text: str, language=None, *, http=None) -> Speech {audio: bytes, media_type, model, voice}
    POST {LLM_BASE_URL or https://openrouter.ai/api/v1}/audio/speech with JSON
    {"model": SPEECH_MODEL, "input": text, "voice": SPEECH_VOICE,
     "response_format": "pcm" if "gemini" in the model id else "mp3"} and
    `Authorization: Bearer LLM_API_KEY`. Per-operation timeout 7 s and an overall read deadline of 9 s; the response is capped at 5 MB.
    mp3 comes back as audio/mpeg. PCM is wrapped in a WAV header (stdlib `wave`): 16-bit mono,
    24000 Hz unless the response Content-Type carries a rate ("audio/pcm;rate=16000").
- language ("es" | "en" | None): only when the model id starts with "elevenlabs/" it adds
  "provider": {"options": {"elevenlabs": {"language_code": language}}}; Gemini ignores it.
- `http` (tests): callable (url, headers, body: bytes, timeout: float) ->
  (status, body bytes, content_type str[, retry_after str]). Default is post.post_bounded.
- Errors (all subclasses of SpeechError; messages never include the key, text or provider body):
  SpeechNotConfigured: LLM_API_KEY, SPEECH_MODEL or SPEECH_VOICE is empty (no network call).
  SpeechUnavailable (sticky for the app): network error, timeout, dropped connection
    (OSError, HTTPException), provider 5xx, body over 5 MB, or no free slot (at most
    SPEECH_MAX_CONCURRENCY, default 8, provider calls at once; never blocks).
  SpeechRateLimited(retry_after: int | None): provider 429.
  SpeechRejected: other provider non-200 (4xx) or 200 with empty audio.
"""

from __future__ import annotations

import io
import json
import os
import re
import threading
import wave
from collections.abc import Callable
from http.client import HTTPException

from pydantic import BaseModel

from app.speech.post import post_bounded

DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"
TIMEOUT_S = 7.0  # per socket operation
DEADLINE_S = 9.0  # whole provider read
MAX_AUDIO_BYTES = 5 * 1024 * 1024
DEFAULT_RATE = 24000
MAX_RETRY_AFTER = 3600

Http = Callable[..., tuple]

_slots = threading.BoundedSemaphore(max(1, int(os.environ.get("SPEECH_MAX_CONCURRENCY", "8"))))


class SpeechError(RuntimeError):
    """Base of the provider failures below."""


class SpeechNotConfigured(SpeechError):
    """No key, model or voice."""


class SpeechUnavailable(SpeechError):
    """Network error, timeout, dropped connection, 5xx, oversize body or no free slot."""


class SpeechRateLimited(SpeechError):
    """The provider answered 429."""

    def __init__(self, retry_after: int | None = None) -> None:
        super().__init__("Speech provider answered HTTP 429")
        self.retry_after = retry_after


class SpeechRejected(SpeechError):
    """The provider refused this text (other 4xx) or answered 200 without audio."""


class Speech(BaseModel):
    audio: bytes
    media_type: str
    model: str
    voice: str


def _post(url: str, headers: dict[str, str], body: bytes, timeout: float) -> tuple:
    return post_bounded(url, headers, body, timeout, MAX_AUDIO_BYTES, DEADLINE_S)


def pcm_to_wav(pcm: bytes, rate: int = DEFAULT_RATE) -> bytes:
    """16-bit mono PCM -> WAV bytes (a trailing odd byte is dropped)."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(pcm[: len(pcm) - len(pcm) % 2])
    return buf.getvalue()


def parse_rate(content_type: str | None, default: int = DEFAULT_RATE) -> int:
    match = re.search(r"rate=(\d{3,6})", content_type or "")
    return int(match.group(1)) if match else default


def _retry_after(value: str) -> int | None:
    value = value.strip()
    return min(max(int(value), 1), MAX_RETRY_AFTER) if value.isdigit() else None


def synthesize(text: str, language: str | None = None, *, http: Http | None = None) -> Speech:
    key = os.environ.get("LLM_API_KEY", "").strip()
    model = os.environ.get("SPEECH_MODEL", "").strip()
    voice = os.environ.get("SPEECH_VOICE", "").strip()
    if not key or not model or not voice:
        raise SpeechNotConfigured("LLM_API_KEY, SPEECH_MODEL and SPEECH_VOICE must be set")
    base = os.environ.get("LLM_BASE_URL", "").strip() or DEFAULT_BASE_URL
    pcm = "gemini" in model.lower()
    payload: dict[str, object] = {
        "model": model,
        "input": text,
        "voice": voice,
        "response_format": "pcm" if pcm else "mp3",
    }
    if language and model.lower().startswith("elevenlabs/"):
        payload["provider"] = {"options": {"elevenlabs": {"language_code": language}}}
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    if not _slots.acquire(blocking=False):
        raise SpeechUnavailable("Speech is busy: no free provider slot")
    try:
        result = (http or _post)(
            f"{base.rstrip('/')}/audio/speech", headers, json.dumps(payload).encode(), TIMEOUT_S
        )
    except (OSError, TimeoutError, HTTPException) as exc:  # URLError and socket timeouts: OSError
        raise SpeechUnavailable(f"Speech request failed ({type(exc).__name__})") from None
    finally:
        _slots.release()
    status, raw, ctype = result[0], result[1], result[2]
    retry = _retry_after(result[3]) if len(result) > 3 and isinstance(result[3], str) else None
    if status == 429:
        raise SpeechRateLimited(retry)
    if status >= 500:
        raise SpeechUnavailable(f"Speech provider answered HTTP {status}")
    if status != 200:
        raise SpeechRejected(f"Speech provider answered HTTP {status}")
    if not raw:
        raise SpeechRejected("Speech provider answered without audio")
    if len(raw) > MAX_AUDIO_BYTES:
        raise SpeechUnavailable("Speech provider answered with too much audio")
    if pcm:
        return Speech(
            audio=pcm_to_wav(raw, parse_rate(ctype)),
            media_type="audio/wav",
            model=model,
            voice=voice,
        )
    return Speech(audio=raw, media_type="audio/mpeg", model=model, voice=voice)
