"""POST /api/speech through the real router with the client faked (D-54). No Postgres, no network."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import deps, routes_speech
from app.api.errors import install_error_handlers
from app.auth.repo import CurrentUser
from app.speech import tts_limits
from app.speech.tts import (
    Speech,
    SpeechNotConfigured,
    SpeechRateLimited,
    SpeechRejected,
    SpeechUnavailable,
)

USER = CurrentUser(id="u1", email="u@test.invalid", role="user")


@pytest.fixture(autouse=True)
def _reset_limits():
    tts_limits.reset_all()
    yield
    tts_limits.reset_all()


@pytest.fixture
def calls(monkeypatch):
    seen: list[str] = []

    def fake(text, *_, **__):
        seen.append(text)
        return Speech(audio=b"AUDIO", media_type="audio/mpeg", model="v/tts", voice="Kore")

    monkeypatch.setattr(routes_speech, "synthesize", fake)
    return seen


def _app():
    app = FastAPI()
    install_error_handlers(app)
    app.include_router(routes_speech.router, prefix="/api")
    return app


@pytest.fixture
def client():
    app = _app()
    app.dependency_overrides[deps.get_current_user] = lambda: USER
    return TestClient(app)


def test_requires_token():
    app = _app()
    app.dependency_overrides[deps.get_conn_factory] = lambda: pytest.fail("db")
    r = TestClient(app).post("/api/speech", json={"text": "hola"})
    assert r.status_code == 401 and r.json()["error"] == "unauthorized"


def test_success_audio_and_headers(client, calls):
    r = client.post("/api/speech", json={"text": "  hola  ", "language": "es"})
    assert r.status_code == 200
    assert r.content == b"AUDIO"
    assert r.headers["content-type"] == "audio/mpeg"
    assert r.headers["x-speech-model"] == "v/tts"
    assert r.headers["x-speech-voice"] == "Kore"
    assert r.headers["cache-control"] == "no-store"
    assert calls == ["hola"]


def test_max_length_ok_and_over_is_413(client, calls):
    assert client.post("/api/speech", json={"text": "a" * 1500}).status_code == 200
    r = client.post("/api/speech", json={"text": "a" * 1501})
    assert r.status_code == 413 and r.json()["error"] == "text_too_long"
    assert len(calls) == 1


@pytest.mark.parametrize(
    "body", [{"text": "   "}, {"text": ""}, {}, {"text": "x", "language": "fr"}]
)
def test_validation_422(client, calls, body):
    r = client.post("/api/speech", json=body)
    assert r.status_code == 422 and r.json()["error"] == "validation_error"
    assert not calls


@pytest.mark.parametrize(
    ("exc", "code"),
    [
        (SpeechNotConfigured("x"), "speech_not_configured"),
        (SpeechUnavailable("x"), "speech_unavailable"),
    ],
)
def test_provider_errors_are_503(client, monkeypatch, exc, code):
    def boom(*_, **__):
        raise exc

    monkeypatch.setattr(routes_speech, "synthesize", boom)
    r = client.post("/api/speech", json={"text": "hola"})
    assert r.status_code == 503 and r.json()["error"] == code


def test_rate_limit_429(client, calls, monkeypatch):
    monkeypatch.setattr(tts_limits, "MAX_PER_WINDOW", 2)
    assert client.post("/api/speech", json={"text": "a"}).status_code == 200
    assert client.post("/api/speech", json={"text": "a"}).status_code == 200
    r = client.post("/api/speech", json={"text": "a"})
    assert r.status_code == 429 and r.json()["error"] == "too_many_speech_requests"
    assert int(r.headers["retry-after"]) >= 1
    assert len(calls) == 2


def test_default_limit_is_120():
    assert tts_limits.MAX_PER_WINDOW == 120


def test_language_is_passed_to_synthesize(client, monkeypatch):
    got: list = []

    def fake(text, language=None):
        got.append(language)
        return Speech(audio=b"A", media_type="audio/mpeg", model="v/tts", voice="Kore")

    monkeypatch.setattr(routes_speech, "synthesize", fake)
    client.post("/api/speech", json={"text": "hola", "language": "es"})
    assert got == ["es"]


def test_provider_429_maps_to_429_with_retry_after(client, monkeypatch):
    def boom(*a, **k):
        raise SpeechRateLimited(9)

    monkeypatch.setattr(routes_speech, "synthesize", boom)
    r = client.post("/api/speech", json={"text": "hola"})
    assert r.status_code == 429 and r.json()["error"] == "too_many_speech_requests"
    assert r.headers["Retry-After"] == "9"
    monkeypatch.setattr(
        routes_speech, "synthesize", lambda *a, **k: (_ for _ in ()).throw(SpeechRateLimited())
    )
    r = client.post("/api/speech", json={"text": "hola"})
    assert r.status_code == 429 and "Retry-After" not in r.headers


def test_provider_rejection_maps_to_422(client, monkeypatch):
    def boom(*a, **k):
        raise SpeechRejected("x")

    monkeypatch.setattr(routes_speech, "synthesize", boom)
    r = client.post("/api/speech", json={"text": "hola"})
    assert r.status_code == 422 and r.json()["error"] == "speech_rejected"
