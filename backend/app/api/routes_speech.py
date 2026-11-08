"""POST /api/speech: text -> spoken audio for reading answers aloud (D-54).

Contract (router mounted under "/api"; sync `def`, so FastAPI runs it in its threadpool):
  Request  JSON {text (1..1500 chars after strip), language: "es" | "en" | null}. Empty text or
           a bad language -> 422. `language` is accepted for the client and is passed to ElevenLabs models only.
  Response 200 audio bytes (audio/mpeg or audio/wav) with headers X-Speech-Model,
           X-Speech-Voice and Cache-Control: no-store.
  Needs the current user (Bearer). Checks in order: auth, per-user limiter (429
  too_many_speech_requests + Retry-After), length (413 text_too_long), then
  speech.tts.synthesize: SpeechNotConfigured -> 503 speech_not_configured; SpeechUnavailable
  (network, timeout, dropped connection, provider 5xx, server busy) -> 503 speech_unavailable
  (the app treats it as sticky); SpeechRateLimited (provider 429) -> 429 too_many_speech_requests
  with the provider's Retry-After when sent; SpeechRejected (other provider 4xx, empty audio) ->
  422 speech_rejected (the app falls back for that message only). Nothing is stored; the log line holds counts, never the text.
"""

from __future__ import annotations

import logging
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, StringConstraints

from app.api.deps import get_current_user
from app.api.errors import ApiError
from app.auth.repo import CurrentUser
from app.speech import tts_limits
from app.speech.tts import (
    SpeechNotConfigured,
    SpeechRateLimited,
    SpeechRejected,
    SpeechUnavailable,
    synthesize,
)

logger = logging.getLogger("series76.api")
router = APIRouter()

MAX_CHARS = 1500


class SpeechIn(BaseModel):
    # No max_length here: an over-long text must be 413 (after the limiter), not 422.
    text: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
    language: Literal["es", "en"] | None = None


@router.post("/speech")
def speak(body: SpeechIn, user: Annotated[CurrentUser, Depends(get_current_user)]) -> Response:
    wait = tts_limits.check_and_record(user.id)
    if wait is not None:
        raise ApiError(
            429,
            "too_many_speech_requests",
            "Too many speech requests. Try again later.",
            headers={"Retry-After": str(wait)},
        )
    if len(body.text) > MAX_CHARS:
        raise ApiError(413, "text_too_long", f"Text is longer than {MAX_CHARS} characters")
    try:
        result = synthesize(body.text, body.language)
    except SpeechNotConfigured:
        raise ApiError(
            503, "speech_not_configured", "Set LLM_API_KEY, SPEECH_MODEL and SPEECH_VOICE"
        ) from None
    except SpeechUnavailable as exc:
        logger.warning("Speech failed: %s", exc)
        raise ApiError(
            503, "speech_unavailable", "Speech is unavailable. Try again shortly."
        ) from None
    except SpeechRateLimited as exc:
        logger.warning("Speech provider rate limit")
        raise ApiError(
            429,
            "too_many_speech_requests",
            "Too many speech requests. Try again later.",
            headers={"Retry-After": str(exc.retry_after)} if exc.retry_after else None,
        ) from None
    except SpeechRejected as exc:
        logger.warning("Speech rejected: %s", exc)
        raise ApiError(
            422, "speech_rejected", "The speech provider could not read this text"
        ) from None
    logger.info(
        "Spoke %d chars with %s (%d bytes)", len(body.text), result.model, len(result.audio)
    )
    return Response(
        content=result.audio,
        media_type=result.media_type,
        headers={
            "X-Speech-Model": result.model,
            "X-Speech-Voice": result.voice,
            "Cache-Control": "no-store",
        },
    )
