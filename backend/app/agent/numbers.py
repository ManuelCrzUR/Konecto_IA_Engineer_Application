"""Number extraction for the number guard (D-26, D-38, D-44). Pure text code, no LLM.

Contract:
- PN_RE / FAMILY_RE: part-number-like tokens and the family name ("Series 76"),
  never figures. Both are blanked out (same length, positions are kept) before scanning.
- scan(text) -> list[Figure(token, start, end, free)]
    Every numeric token, in order: digit tokens ('1,330', '2.3', '17') and number
    words, English and Spanish, 0..20 (accents optional: 'dieciséis' == 'dieciseis').
    `one`, `once`, `un`, `una`, `uno` are NOT number words: too ambiguous (article,
    pronoun, adverb). `free` is True for the two figures that need no source:
      - a list ordinal: a number at the start of a line followed by '.' or ')';
      - the 90 of a 90 degree stroke: '90°', '90 degrees', '90 grados'.
- figures(text) -> list[Figure]   the figures that must be verified (free=False).
- tokens(text) -> list[str]       every token, free ones too (for building allowed sets).
- token_values(token) -> set[float]   all readings: '1,330' -> {1330.0, 1.33}; 'siete' -> {7.0}.
"""

from __future__ import annotations

import re
import unicodedata
from typing import NamedTuple

PN_RE = re.compile(r"76\d[A-Z]\d{2}(?:-[0-9A-Z]{8}(?:/A)?)?\*?", re.IGNORECASE)
FAMILY_RE = re.compile(r"\bS[eé]ries?[\s-]*76\b", re.IGNORECASE)  # product name, not a figure
_EN = "zero _ two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen"
_EN += " sixteen seventeen eighteen nineteen twenty"
_ES = "cero _ dos tres cuatro cinco seis siete ocho nueve diez _ doce trece catorce quince"
_ES += " dieciseis diecisiete dieciocho diecinueve veinte"
_WORDS: dict[str, int] = {
    w: i for lang in (_EN, _ES) for i, w in enumerate(lang.split()) if w != "_"
}
_WORD_FORMS = sorted({*_WORDS, "dieciséis"}, key=len, reverse=True)
_SCAN = re.compile(
    r"(?P<num>\d+(?:[.,]\d+)*)|(?<!\w)(?P<word>" + "|".join(_WORD_FORMS) + r")(?!\w)",
    re.IGNORECASE,
)
_STROKE = re.compile(r"\s?°|\s*-?\s*(?:degrees?|grados?)\b", re.IGNORECASE)


class Figure(NamedTuple):
    token: str
    start: int
    end: int
    free: bool


def blank(text: str) -> str:
    """Replace part numbers and the family name with spaces (same length)."""
    for rx in (FAMILY_RE, PN_RE):
        text = rx.sub(lambda m: " " * len(m.group(0)), text)
    return text


def _free(text: str, m: re.Match[str]) -> bool:
    if m.group("num") is None:
        return False
    after = text[m.end() : m.end() + 2]
    line_start = text.rfind("\n", 0, m.start()) + 1
    if not text[line_start : m.start()].strip() and after[:1] in (".", ")"):
        return after[1:].strip() == "" or after[1:2].isspace()  # ordinal "1. " / "2) "
    return m.group("num") == "90" and bool(_STROKE.match(text, m.end()))


def scan(text: str) -> list[Figure]:
    clean = blank(text)
    return [Figure(m.group(0), m.start(), m.end(), _free(clean, m)) for m in _SCAN.finditer(clean)]


def figures(text: str) -> list[Figure]:
    return [f for f in scan(text) if not f.free]


def tokens(text: str) -> list[str]:
    return [f.token for f in scan(text)]


def _plain(word: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", word.lower()) if c.isalpha())


def token_values(token: str) -> set[float]:
    if token[0].isalpha():
        return {float(_WORDS[_plain(token)])}
    seps = [c for c in token if not c.isdigit()]
    if not seps:
        return {float(token)}
    if len(set(seps)) == 1 and len(seps) > 1:  # '1,234,567': thousands only
        return {float(token.replace(seps[0], ""))}
    last = max(token.rfind(","), token.rfind("."))
    head, tail = token[:last], token[last + 1 :]
    plain = re.sub(r"[.,]", "", head)
    values = {float(f"{plain}.{tail}")}
    if len(seps) == 1 and len(tail) == 3:  # '1,330' may be 1330 or 1.33
        values.add(float(plain + tail))
    return values
