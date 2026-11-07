"""OpenRouter speech-to-text client (D-53). One call, no retries, nothing stored.

Contract:
- transcribe(audio: bytes, fmt: str, language: str | None, *, http=None) -> Transcript
    POST {LLM_BASE_URL or https://openrouter.ai/api/v1}/audio/transcriptions with JSON
    {"model": TRANSCRIBE_MODEL, "input_audio": {"data": <base64>, "format": fmt},
     "temperature": 0, "language": <only when given>} and `Authorization: Bearer LLM_API_KEY`.
    Timeout 12 s (under the app's 15 s, so the server answers 503 first). Transcript {text, model, seconds}; seconds = usage.seconds when present.
- `http` (tests): callable (url, headers, body: bytes, timeout: float) -> (status, body bytes).
  Default uses urllib. It may raise OSError/TimeoutError, which become TranscriptionUnavailable.
- TranscriptionNotConfigured: LLM_API_KEY or TRANSCRIBE_MODEL is empty (no network call).
- TranscriptionUnavailable: network error, timeout, non-200, invalid JSON or no "text".
  Messages never include the key, the audio or the provider's body.
"""

from __future__ import annotations

import base64
import json
import os
import urllib.error
import urllib.request
from collections.abc import Callable

from pydantic import BaseModel

DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"
# Must stay below the Android client's 15 s so the server answers 503 before the app gives up.
TIMEOUT_S = 12.0

Http = Callable[[str, dict[str, str], bytes, float], tuple[int, bytes]]


class TranscriptionNotConfigured(RuntimeError):
    """No key or no TRANSCRIBE_MODEL."""


class TranscriptionUnavailable(RuntimeError):
    """The provider failed, timed out or answered without text."""


class Transcript(BaseModel):
    text: str
    model: str
    seconds: float | None = None


def _urllib_post(
    url: str, headers: dict[str, str], body: bytes, timeout: float
) -> tuple[int, bytes]:
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as exc:
        return exc.code, b""


def transcribe(
    audio: bytes, fmt: str, language: str | None, *, http: Http | None = None
) -> Transcript:
    key = os.environ.get("LLM_API_KEY", "").strip()
    model = os.environ.get("TRANSCRIBE_MODEL", "").strip()
    if not key or not model:
        raise TranscriptionNotConfigured("LLM_API_KEY and TRANSCRIBE_MODEL must be set")
    base = os.environ.get("LLM_BASE_URL", "").strip() or DEFAULT_BASE_URL
    payload: dict[str, object] = {
        "model": model,
        "input_audio": {"data": base64.b64encode(audio).decode("ascii"), "format": fmt},
        "temperature": 0,
    }
    if language:
        payload["language"] = language
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    try:
        status, raw = (http or _urllib_post)(
            f"{base.rstrip('/')}/audio/transcriptions",
            headers,
            json.dumps(payload).encode(),
            TIMEOUT_S,
        )
    except (OSError, TimeoutError) as exc:  # URLError and socket timeouts are OSError
        raise TranscriptionUnavailable(
            f"Transcription request failed ({type(exc).__name__})"
        ) from None
    if status != 200:
        raise TranscriptionUnavailable(f"Transcription provider answered HTTP {status}")
    try:
        data = json.loads(raw)
        text = data["text"]
        if not isinstance(text, str):
            raise TypeError
    except (ValueError, KeyError, TypeError):
        raise TranscriptionUnavailable("Transcription provider answered without text") from None
    usage = data.get("usage")
    seconds = usage.get("seconds") if isinstance(usage, dict) else None
    return Transcript(
        text=text, model=model, seconds=float(seconds) if isinstance(seconds, int | float) else None
    )
