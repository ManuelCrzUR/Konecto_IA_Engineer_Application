"""Transcription client with a fake transport: no network (D-53)."""

import base64
import json

import pytest

from app.speech import client
from app.speech.client import TranscriptionNotConfigured, TranscriptionUnavailable, transcribe

KEY = "sk-secret-key-123"


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", KEY)
    monkeypatch.setenv("TRANSCRIBE_MODEL", "vendor/stt")
    monkeypatch.setenv("LLM_BASE_URL", "")


def fake(status=200, body=None, exc=None, seen=None):
    def http(url, headers, data, timeout):
        if seen is not None:
            seen.update(url=url, headers=headers, body=json.loads(data), timeout=timeout)
        if exc:
            raise exc
        return status, json.dumps(body if body is not None else {}).encode()

    return http


def test_success_builds_request_and_parses_seconds():
    seen: dict = {}
    out = transcribe(
        b"abc", "m4a", "es", http=fake(body={"text": "hola", "usage": {"seconds": 3.5}}, seen=seen)
    )
    assert (out.text, out.model, out.seconds) == ("hola", "vendor/stt", 3.5)
    assert seen["url"] == "https://openrouter.ai/api/v1/audio/transcriptions"
    assert seen["headers"]["Authorization"] == f"Bearer {KEY}"
    assert seen["timeout"] == 12.0
    assert seen["body"] == {
        "model": "vendor/stt",
        "input_audio": {"data": base64.b64encode(b"abc").decode(), "format": "m4a"},
        "temperature": 0,
        "language": "es",
    }


def test_language_omitted_and_custom_base_url(monkeypatch):
    monkeypatch.setenv("LLM_BASE_URL", "http://example.invalid/v1/")
    seen: dict = {}
    out = transcribe(b"a", "wav", None, http=fake(body={"text": "x"}, seen=seen))
    assert "language" not in seen["body"] and out.seconds is None
    assert seen["url"] == "http://example.invalid/v1/audio/transcriptions"


@pytest.mark.parametrize("var", ["LLM_API_KEY", "TRANSCRIBE_MODEL"])
def test_not_configured(monkeypatch, var):
    monkeypatch.setenv(var, "")
    with pytest.raises(TranscriptionNotConfigured):
        transcribe(b"a", "m4a", None, http=fake(body={"text": "x"}))


@pytest.mark.parametrize(
    "http",
    [
        fake(status=500, body={"error": f"leak {KEY}"}),
        fake(exc=TimeoutError("timed out")),
        fake(exc=OSError(f"boom {KEY}")),
        fake(body={"nope": 1}),
        fake(body={"text": 5}),
    ],
)
def test_unavailable_and_messages_hide_key(http):
    with pytest.raises(TranscriptionUnavailable) as err:
        transcribe(b"audio-bytes", "m4a", None, http=http)
    assert KEY not in str(err.value) and "audio-bytes" not in str(err.value)


def test_default_transport_is_not_used_when_injected(monkeypatch):
    monkeypatch.setattr(client, "_urllib_post", lambda *a: pytest.fail("network"))
    assert transcribe(b"a", "m4a", None, http=fake(body={"text": "ok"})).text == "ok"
