"""make_snippet: pure unit tests."""

import pytest

from app.db.snippet import make_snippet

PN = "764A00-11300000/A"


def test_short_text_is_returned_whole():
    assert make_snippet("What is the torque?", "torque") == "What is the torque?"


def test_newlines_collapse():
    assert make_snippet("line one\n\nline  two", "two") == "line one line two"


def test_case_insensitive_match_cut_both_sides():
    text = "word " * 40 + "TORQUE" + " word" * 40
    out = make_snippet(text, "torque")
    assert out.startswith("…") and out.endswith("…")
    assert "TORQUE" in out and len(out) <= 80 + 2 + 24 * 2


def test_cut_only_at_end_has_no_leading_ellipsis():
    out = make_snippet("torque " + "word " * 60, "torque")
    assert not out.startswith("…") and out.endswith("…")


@pytest.mark.parametrize("token", [PN, "6650", "1,250"])
def test_never_splits_a_token(token):
    for pad in range(25, 60):
        text = ("ab " * pad)[:pad] + " " + token + " " + ("cd " * pad)[:pad] + " end"
        words = set(text.split())
        for query in (token, "no-such-text"):
            body = make_snippet(text, query).strip("…")
            assert all(w in words for w in body.split()), (pad, query, body)


def test_no_match_returns_start():
    assert make_snippet("abc " * 50, "nope").startswith("abc")


def test_blank_query_does_not_crash():
    assert make_snippet("hello", "  ") == "hello"
