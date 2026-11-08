"""Shared bounded POST, window limiter and the client's HTTPException mapping: no network."""

import http.client
from typing import ClassVar

import pytest

from app.speech import client, post
from app.speech.window import SlidingWindowLimiter


class FakeResp:
    status = 200
    headers: ClassVar[dict[str, str]] = {"Content-Type": "audio/pcm;rate=16000"}

    def __init__(self, data=b"", exc=None):
        self.data, self.exc, self.reads = data, exc, []

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def read(self, n):
        self.reads.append(n)
        if self.exc:
            raise self.exc
        out, self.data = self.data[:n], self.data[n:]
        return out


def _patch(monkeypatch, resp):
    monkeypatch.setattr(post.urllib.request, "urlopen", lambda *a, **k: resp)


def test_reads_in_chunks_and_stops_one_past_the_cap(monkeypatch):
    resp = FakeResp(b"x" * 500_000)
    _patch(monkeypatch, resp)
    status, data, ctype, _ = post.post_bounded("http://x", {}, b"", 1, 200_000, 5)
    assert (status, len(data), ctype) == (200, 200_001, "audio/pcm;rate=16000")
    assert all(n <= post.CHUNK for n in resp.reads)


def test_overall_deadline_aborts(monkeypatch):
    _patch(monkeypatch, FakeResp(b"x" * 500_000))
    with pytest.raises(TimeoutError):
        post.post_bounded("http://x", {}, b"", 1, 400_000, -1)


def test_http_exception_becomes_oserror(monkeypatch):
    _patch(monkeypatch, FakeResp(exc=http.client.IncompleteRead(b"a")))
    with pytest.raises(OSError):
        post.post_bounded("http://x", {}, b"", 1, 100, 5)


def test_client_maps_http_exception_to_unavailable(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "k")
    monkeypatch.setenv("TRANSCRIBE_MODEL", "m")

    def boom(*a):
        raise http.client.IncompleteRead(b"a")

    with pytest.raises(client.TranscriptionUnavailable):
        client.transcribe(b"a", "wav", None, http=boom)


def test_window_limiter():
    lim = SlidingWindowLimiter(2, 10, max_tracked=2)
    assert lim.check_and_record("a", 0) is None
    assert lim.check_and_record("a", 1) is None
    assert lim.check_and_record("a", 4) == 6
    assert lim.check_and_record("a", 10) is None
    lim.check_and_record("b", 0)
    lim.check_and_record("c", 0)  # evicts "a"
    assert lim.check_and_record("a", 11) is None and lim.check_and_record("a", 11) is None
    lim.reset()
    assert lim.check_and_record("a", 11) is None


@pytest.mark.parametrize(
    ("answer", "query", "lang"),
    [
        ("El 764A tiene un torque de 100 in-lbs.", "764A?", "es"),
        ("It has 100 in-lbs of torque.", "¿cuánto torque tiene el 764A?", "en"),
        ("100 / 50", "¿cuánto torque?", "es"),
        ("100 / 50", "how much torque?", "en"),
    ],
)
def test_conversation_language_follows_the_answer(answer, query, lang):
    from app.api.routes_conversation import _answer_language

    assert _answer_language(answer, query) == lang
