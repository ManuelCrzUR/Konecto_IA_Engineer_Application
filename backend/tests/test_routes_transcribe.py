"""POST /api/transcribe through the real router with the client faked (D-53). No Postgres, no network."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import deps, routes_transcribe
from app.api.errors import install_error_handlers
from app.auth.repo import CurrentUser
from app.speech import limits
from app.speech.client import (
    Transcript,
    TranscriptionNotConfigured,
    TranscriptionUnavailable,
)

USER = CurrentUser(id="u1", email="u@test.invalid", role="user")


@pytest.fixture(autouse=True)
def _reset_limits():
    limits.reset_all()
    yield
    limits.reset_all()


@pytest.fixture
def calls(monkeypatch):
    seen: list[tuple] = []

    def fake(audio, fmt, language, **_):
        seen.append((audio, fmt, language))
        return Transcript(text="raw words", model="vendor/stt", seconds=2.0)

    monkeypatch.setattr(routes_transcribe, "transcribe", fake)
    monkeypatch.setattr(routes_transcribe, "normalize_transcript", lambda t: f"NORM({t})")
    return seen


@pytest.fixture
def client():
    app = FastAPI()
    install_error_handlers(app)
    app.include_router(routes_transcribe.router, prefix="/api")
    app.dependency_overrides[deps.get_current_user] = lambda: USER
    return TestClient(app)


def post(client, data=b"audio", name="q.m4a", ctype="audio/mp4", **form):
    return client.post("/api/transcribe", files={"audio": (name, data, ctype)}, data=form)


def test_requires_token():
    app = FastAPI()
    install_error_handlers(app)
    app.include_router(routes_transcribe.router, prefix="/api")
    app.dependency_overrides[deps.get_conn_factory] = lambda: pytest.fail("db")
    r = TestClient(app).post("/api/transcribe", files={"audio": ("a.m4a", b"x", "audio/mp4")})
    assert r.status_code == 401 and r.json()["error"] == "unauthorized"


def test_success_shape_and_normalization(client, calls):
    r = post(client, language="es")
    assert r.status_code == 200
    assert r.json() == {
        "text": "NORM(raw words)",
        "raw_text": "raw words",
        "model": "vendor/stt",
        "seconds": 2.0,
    }
    assert calls == [(b"audio", "m4a", "es")]


@pytest.mark.parametrize(
    ("name", "ctype", "fmt"),
    [("a.wav", "application/octet-stream", "wav"), ("blob", "audio/webm;codecs=opus", "webm")],
)
def test_format_from_extension_or_content_type(client, calls, name, ctype, fmt):
    assert post(client, name=name, ctype=ctype).status_code == 200
    assert calls[0][1] == fmt


def test_too_large(client, calls):
    r = post(client, data=b"x" * (routes_transcribe.MAX_BYTES + 1))
    assert r.status_code == 413 and r.json()["error"] == "audio_too_large" and not calls


def test_unsupported_format(client, calls):
    r = post(client, name="a.txt", ctype="text/plain")
    assert r.status_code == 415 and r.json()["error"] == "unsupported_audio" and not calls


def test_empty_file(client, calls):
    assert post(client, data=b"").status_code == 422 and not calls


def test_bad_language(client, calls):
    r = post(client, language="fr")
    assert r.status_code == 422 and r.json()["error"] == "validation_error" and not calls


@pytest.mark.parametrize(
    ("exc", "code"),
    [
        (TranscriptionNotConfigured("x"), "transcription_not_configured"),
        (TranscriptionUnavailable("x"), "transcription_unavailable"),
    ],
)
def test_provider_errors_are_503(client, monkeypatch, exc, code):
    def boom(*_a, **_k):
        raise exc

    monkeypatch.setattr(routes_transcribe, "transcribe", boom)
    r = post(client)
    assert r.status_code == 503 and r.json()["error"] == code


def test_rate_limit_with_retry_after(client, calls, monkeypatch):
    monkeypatch.setattr(limits, "MAX_PER_WINDOW", 2)
    assert post(client).status_code == 200
    assert post(client).status_code == 200
    r = post(client)
    assert r.status_code == 429 and r.json()["error"] == "too_many_transcriptions"
    assert int(r.headers["Retry-After"]) >= 1 and len(calls) == 2


def test_limiter_window_and_bound():
    assert limits.check_and_record("a", now=0) is None
    for _ in range(limits.MAX_PER_WINDOW - 1):
        limits.check_and_record("a", now=1)
    assert limits.check_and_record("a", now=2) == limits.WINDOW_SECONDS - 2
    assert limits.check_and_record("a", now=limits.WINDOW_SECONDS + 1) is None
    assert limits.check_and_record("b", now=2) is None
