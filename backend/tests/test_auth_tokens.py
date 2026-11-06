import re

import pytest

from app.auth.tokens import TOKEN_TTL, hash_token, new_token, parse_bearer


def test_new_token_length_and_uniqueness():
    tokens = {new_token() for _ in range(100)}
    assert len(tokens) == 100
    assert all(len(t) >= 43 for t in tokens)


def test_hash_token_is_64_hex_and_deterministic():
    h = hash_token("abc")
    assert re.fullmatch(r"[0-9a-f]{64}", h)
    assert h == hash_token("abc") != hash_token("abd")


def test_ttl_is_seven_days():
    assert TOKEN_TTL.days == 7


@pytest.mark.parametrize(
    ("header", "expected"),
    [
        ("Bearer abc", "abc"),
        ("bearer abc", "abc"),
        ("BEARER abc", "abc"),
        ("  Bearer   abc  ", "abc"),
        ("Bearer", None),
        ("Bearer ", None),
        ("Basic abc", None),
        ("abc", None),
        ("", None),
        (None, None),
    ],
)
def test_parse_bearer(header, expected):
    assert parse_bearer(header) == expected
