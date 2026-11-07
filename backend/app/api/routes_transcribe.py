"""POST /api/transcribe: audio -> text for voice input (D-53).

Contract (router mounted under "/api"; sync `def`, so FastAPI runs it in its threadpool):
  Request  multipart: `audio` (file, required), `language` (optional "es" | "en", else 422).
  Response 200 {text (normalized), raw_text, model, seconds}.
  Needs the current user (Bearer, same dependency as the other routes).
  Checks in order: per-user limiter (429 too_many_transcriptions + Retry-After), size <= 2 MB
  (reads at most 2 MB + 1 byte; 413 audio_too_large), format from the filename extension or
  content type among m4a/mp4/aac/wav/mp3/ogg/webm/flac (415 unsupported_audio), empty (422
  empty_audio). Then speech.client.transcribe: TranscriptionNotConfigured -> 503
  transcription_not_configured; TranscriptionUnavailable -> 503 transcription_unavailable.
  Audio is never stored; the log line holds the transcript length and model, never its text.
"""

from __future__ import annotations

import logging
import os
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, File, Form, UploadFile
from pydantic import BaseModel

from app.api.deps import get_current_user
from app.api.errors import ApiError
from app.auth.repo import CurrentUser
from app.speech import limits
from app.speech.client import TranscriptionNotConfigured, TranscriptionUnavailable, transcribe
from app.speech.normalize import normalize_transcript

logger = logging.getLogger("series76.api")
router = APIRouter()

MAX_BYTES = 2 * 1024 * 1024
# extension or content subtype -> format sent to the provider
FORMATS = {
    "m4a": "m4a", "mp4": "m4a", "aac": "aac", "wav": "wav", "x-wav": "wav", "wave": "wav",
    "mp3": "mp3", "mpeg": "mp3", "ogg": "ogg", "webm": "webm", "flac": "flac",
    "x-m4a": "m4a", "x-flac": "flac",
}  # fmt: skip


class TranscribeOut(BaseModel):
    text: str
    raw_text: str
    model: str
    seconds: float | None = None


def _format_of(upload: UploadFile) -> str | None:
    ext = os.path.splitext(upload.filename or "")[1].lstrip(".").lower()
    if ext in FORMATS:
        return FORMATS[ext]
    subtype = (upload.content_type or "").split(";")[0].strip().lower().rpartition("/")[2]
    return FORMATS.get(subtype)


@router.post("/transcribe", response_model=TranscribeOut)
def transcribe_audio(
    user: Annotated[CurrentUser, Depends(get_current_user)],
    audio: Annotated[UploadFile, File()],
    language: Annotated[Literal["es", "en"] | None, Form()] = None,
) -> TranscribeOut:
    wait = limits.check_and_record(user.id)
    if wait is not None:
        raise ApiError(
            429,
            "too_many_transcriptions",
            "Too many voice requests. Try again later.",
            headers={"Retry-After": str(wait)},
        )
    data = audio.file.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise ApiError(413, "audio_too_large", "Audio is larger than 2 MB")
    fmt = _format_of(audio)
    if fmt is None:
        raise ApiError(415, "unsupported_audio", "Use m4a, aac, wav, mp3, ogg, webm or flac audio")
    if not data:
        raise ApiError(422, "empty_audio", "The audio file is empty")
    try:
        result = transcribe(data, fmt, language)
    except TranscriptionNotConfigured:
        raise ApiError(
            503, "transcription_not_configured", "Set LLM_API_KEY and TRANSCRIBE_MODEL"
        ) from None
    except TranscriptionUnavailable as exc:
        logger.warning("Transcription failed: %s", exc)
        raise ApiError(
            503, "transcription_unavailable", "Transcription is unavailable. Try again shortly."
        ) from None
    logger.info("Transcribed %d chars with %s", len(result.text), result.model)
    return TranscribeOut(
        text=normalize_transcript(result.text),
        raw_text=result.text,
        model=result.model,
        seconds=result.seconds,
    )
