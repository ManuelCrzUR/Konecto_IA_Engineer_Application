"""Text-to-speech client with a fake transport: no network (D-54)."""

import http.client
import io
import json
import threading
import wave

import pytest

from app.speech.tts import (
    MAX_AUDIO_BYTES,
    SpeechNotConfigured,
    SpeechRateLimited,
    SpeechRejected,
    SpeechUnavailable,
    synthesize,
)

KEY = "sk-secret-key-123"
TEXT = "confidential spoken words"


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", KEY)
    monkeypatch.setenv("SPEECH_MODEL", "eleven/flash")
    monkeypatch.setenv("SPEECH_VOICE", "Kore")
    monkeypatch.setenv("LLM_BASE_URL", "")


def fake(status=200, body=b"audio", ctype="", exc=None, seen=None):
    def http(url, headers, data, timeout):
        if seen is not None:
            seen.update(url=url, headers=headers, body=json.loads(data), timeout=timeout)
        if exc:
            raise exc
        return status, body, ctype

    return http


def test_mp3_passthrough_and_request():
    seen: dict = {}
    out = synthesize(TEXT, http=fake(body=b"ID3xyz", seen=seen))
    assert (out.audio, out.media_type, out.model, out.voice) == (
        b"ID3xyz", "audio/mpeg", "eleven/flash", "Kore",
    )  # fmt: skip
    assert seen["url"] == "https://openrouter.ai/api/v1/audio/speech"
    assert seen["headers"]["Authorization"] == f"Bearer {KEY}"
    assert seen["timeout"] == 7.0
    assert seen["body"] == {
        "model": "eleven/flash", "input": TEXT, "voice": "Kore", "response_format": "mp3",
    }  # fmt: skip


def test_pcm_wrapped_as_wav(monkeypatch):
    monkeypatch.setenv("SPEECH_MODEL", "google/gemini-3.8-flash-tts")
    monkeypatch.setenv("LLM_BASE_URL", "http://proxy.test/v1/")
    seen: dict = {}
    out = synthesize(TEXT, http=fake(body=b"\x01\x00" * 100, seen=seen))
    assert seen["body"]["response_format"] == "pcm"
    assert seen["url"] == "http://proxy.test/v1/audio/speech"
    assert out.media_type == "audio/wav"
    with wave.open(io.BytesIO(out.audio)) as w:
        assert (w.getframerate(), w.getsampwidth(), w.getnchannels(), w.getnframes()) == (
            24000, 2, 1, 100,
        )  # fmt: skip


def test_rate_from_content_type(monkeypatch):
    monkeypatch.setenv("SPEECH_MODEL", "google/gemini-3.8-flash-tts")
    out = synthesize(TEXT, http=fake(body=b"\x00\x00" * 10, ctype="audio/pcm;rate=16000"))
    with wave.open(io.BytesIO(out.audio)) as w:
        assert w.getframerate() == 16000


@pytest.mark.parametrize(
    "kwargs",
    [
        {"status": 500},
        {"exc": TimeoutError("took too long")},
        {"exc": OSError(f"boom {KEY} {TEXT}")},
        {"exc": http.client.IncompleteRead(b"ab")},
        {"exc": ConnectionResetError("reset")},
        {"body": b"x" * (MAX_AUDIO_BYTES + 1)},
    ],
)
def test_unavailable_and_messages_are_clean(kwargs):
    with pytest.raises(SpeechUnavailable) as err:
        synthesize(TEXT, http=fake(**kwargs))
    assert KEY not in str(err.value) and TEXT not in str(err.value)


@pytest.mark.parametrize("var", ["LLM_API_KEY", "SPEECH_MODEL", "SPEECH_VOICE"])
def test_not_configured(monkeypatch, var):
    monkeypatch.setenv(var, " ")
    called = []
    with pytest.raises(SpeechNotConfigured) as err:
        synthesize(TEXT, http=lambda *a: called.append(a) or (200, b"x", ""))
    assert not called and KEY not in str(err.value) and TEXT not in str(err.value)


def test_elevenlabs_gets_language_code(monkeypatch):
    monkeypatch.setenv("SPEECH_MODEL", "elevenlabs/eleven-flash-v2.5")
    seen: dict = {}
    synthesize(TEXT, "es", http=fake(body=b"ID3", seen=seen))
    assert seen["body"]["provider"] == {"options": {"elevenlabs": {"language_code": "es"}}}
    seen.clear()
    synthesize(TEXT, http=fake(body=b"ID3", seen=seen))
    assert "provider" not in seen["body"]


def test_gemini_ignores_language(monkeypatch):
    monkeypatch.setenv("SPEECH_MODEL", "google/gemini-3.8-flash-lite-tts")
    seen: dict = {}
    synthesize(TEXT, "es", http=fake(body=b"\x00\x00", seen=seen))
    assert "provider" not in seen["body"]


def test_429_is_rate_limited_with_retry_after():
    def http_(*a):
        return 429, b"", "", "7"

    with pytest.raises(SpeechRateLimited) as err:
        synthesize(TEXT, http=http_)
    assert err.value.retry_after == 7
    with pytest.raises(SpeechRateLimited) as err:
        synthesize(TEXT, http=fake(status=429))
    assert err.value.retry_after is None


@pytest.mark.parametrize("kwargs", [{"status": 400}, {"status": 404}, {"body": b""}])
def test_rejected(kwargs):
    with pytest.raises(SpeechRejected) as err:
        synthesize(TEXT, http=fake(**kwargs))
    assert KEY not in str(err.value) and TEXT not in str(err.value)


def test_busy_when_no_slot_and_slot_released(monkeypatch):
    from app.speech import tts

    monkeypatch.setattr(tts, "_slots", threading.BoundedSemaphore(1))
    called = []

    def inner(*a):
        called.append(1)
        with pytest.raises(SpeechUnavailable):  # second concurrent call: no slot, no network
            synthesize(TEXT, http=lambda *b: called.append(2) or (200, b"x", ""))
        return 200, b"ID3", ""

    assert synthesize(TEXT, http=inner).audio == b"ID3"
    assert called == [1]
    assert synthesize(TEXT, http=fake(body=b"ID3")).audio == b"ID3"  # released after success
    with pytest.raises(SpeechUnavailable):
        synthesize(TEXT, http=fake(status=500))
    assert synthesize(TEXT, http=fake(body=b"ID3")).audio == b"ID3"  # and after failure
