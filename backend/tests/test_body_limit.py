"""BodyLimitMiddleware: oversize uploads are rejected before auth and parsing."""

from __future__ import annotations

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from app.api.body_limit import BodyLimitMiddleware

LIMIT = 1000


@pytest.fixture
def client():
    app = FastAPI()
    app.add_middleware(BodyLimitMiddleware, max_bytes=LIMIT)

    @app.post("/api/transcribe")
    async def t(request: Request):
        return {"n": len(await request.body())}

    @app.post("/api/other")
    async def o(request: Request):
        return {"n": len(await request.body())}

    return TestClient(app)


def test_no_content_length_is_411(client):
    def gen():
        yield b"abc"

    r = client.post("/api/transcribe", content=gen())  # chunked
    assert r.status_code == 411
    assert r.json()["error"] == "length_required"


def test_declared_too_large_is_413_without_token(client):
    r = client.post("/api/transcribe", content=b"x" * (LIMIT + 1))
    assert r.status_code == 413
    assert r.json()["error"] == "audio_too_large"


def test_lying_content_length_is_cut_off():
    app = FastAPI()
    app.add_middleware(BodyLimitMiddleware, max_bytes=LIMIT)

    @app.post("/api/transcribe")
    async def t(request: Request):
        return {"n": len(await request.body())}

    import asyncio

    sent: list[dict] = []
    chunks = [b"x" * 600, b"x" * 600]

    async def receive():
        body = chunks.pop(0) if chunks else b""
        return {"type": "http.request", "body": body, "more_body": bool(chunks)}

    async def send(m):
        sent.append(m)

    scope = {
        "type": "http", "method": "POST", "path": "/api/transcribe", "query_string": b"",
        "headers": [(b"content-length", b"10")], "app": app, "http_version": "1.1",
        "scheme": "http", "server": ("t", 80), "client": ("c", 1), "root_path": "",
    }  # fmt: skip
    asyncio.run(app(scope, receive, send))
    assert sent[0]["status"] == 413


def test_small_upload_passes(client):
    r = client.post("/api/transcribe", content=b"x" * 10)
    assert r.status_code == 200 and r.json() == {"n": 10}


def test_other_paths_unaffected(client):
    r = client.post("/api/other", content=b"x" * (LIMIT * 5))
    assert r.status_code == 200
