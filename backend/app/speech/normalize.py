"""Deterministic clean-up of a speech transcript before it reaches the agent (D-53). Pure code.

Contract:
- normalize_transcript(text: str) -> str
    Rewrites only spans that look like a dictated Series 76 part number; the rest of the
    text is returned unchanged (except surrounding whitespace, stripped).
    A span starts at a model number "76" + one digit (761..767; "76 4" is accepted) and continues over groups of
    digits/letters joined by spaces, commas, dots, hyphens, slashes or spoken separators.
    Inside such a span:
      - spoken separators: "guion", "guión", "raya", "dash", "hyphen" -> "-";
        "barra", "barra oblicua", "slash" -> "/";
      - "by", "por", "equis", "x" between the model number and the next two digits -> "X"
        (e.g. "764 by 30" -> "764X30", "762 por 30" -> "762X30");
      - thousands separators and spaces between groups are removed ("11,320,000" -> "11320000");
      - a single spoken letter before more digits joins the group ("764 a 00" -> "764A00");
      - letters are uppercased ("766 a00" -> "766A00");
      - a trailing "a" / "A" after "/" or a spoken "barra"/"slash" becomes "/A".
    The result for a full span is the canonical shape "<6-char base>-<8-char suffix>/A" when the
    collapsed characters have that shape (base = 3 digits + letter + 2 digits/letters, suffix =
    8 alphanumerics); a base-only span becomes the 6-char base ("762 por 30" -> "762X30").
    Spans whose characters do not fit these shapes are left as the model wrote them (never
    guessed, never padded, never snapped to the catalog).
    A base-only result is also left as written when the next token after the span is a unit or
    unit word (Hz, hertz, V, volt(s), voltios, Nm, newton, in-lbs, A, amp(s), amperios, W, watts,
    vatios, %, s, seg, segundos, seconds, cycles, ciclos, starts, arranques; case-insensitive,
    except the single letters A/W/V/s, which must be written so): there the span is a question
    ("764 a 60 Hz", "761 x 20 Nm"), not a part number. Full part numbers are unaffected. A
    spoken letter is not joined once the collected characters already form a complete base
    ("764 a 00 a 60 Hz" -> "764A00 a 60 Hz").
    Never raises.
"""

from __future__ import annotations

import re

_START = re.compile(
    r"(?<![0-9A-Za-z])76\s?([1-7])(?![0-9])(?:\s*(?:by|por|equis|x)\s*(?=\d{2}))?", re.IGNORECASE
)
_SEPWORD = re.compile(
    r"[\s,]*(barra\s+oblicua|barra|slash|guion|guión|raya|dash|hyphen)\b", re.IGNORECASE
)
_PUNCT = re.compile(r"\s*([-/])\s*(?=[0-9A-Za-z])")
_LETTER = re.compile(r"\s*([A-Za-z])(?![0-9A-Za-z])")
_LETTER_BEFORE_DIGIT = re.compile(r"\s*([A-Za-z])(?=\s*\d)(?![0-9A-Za-z])")
_NEVER = re.compile(r"(?!)")
_GROUP = re.compile(r"\s*[,.]?([0-9A-Za-z]*\d[0-9A-Za-z]*)")
_BASE = re.compile(r"\d{3}[A-Z][0-9A-Z]{2}")
_UNIT = re.compile(
    r"\s*(?:(?i:hz|hertz|volts?|voltios?|nm|newtons?|in-lbs|amps?|amperios?|watts?|vatios?"
    r"|seg|segundos|seconds|cycles|ciclos|starts|arranques)|[AWVs]|%)(?![0-9A-Za-z])"
)
_SLASH_WORDS = {"barra", "slash"}


def _span(text: str, m: re.Match[str]) -> tuple[int, str]:
    """Scan the pieces after the model number; return (end, replacement or '' if no fit)."""
    first = m.group(0)
    chars = "76" + m.group(1) + ("X" if re.search(r"[A-Za-z]", first) else "")
    pos = end = m.end()
    tail: str | None = None
    last_slash = False
    while pos < len(text):
        piece = _SEPWORD.match(text, pos)
        if piece:
            last_slash = piece.group(1).lower().split()[0] in _SLASH_WORDS
            pos = piece.end()
            continue
        piece = _PUNCT.match(text, pos)
        if piece:
            last_slash = piece.group(1) == "/"
            pos = piece.end()
            continue
        joinable = tail is None and len(chars) < 14 and not _BASE.fullmatch(chars.upper())
        # a spoken letter inside an unfinished number
        piece = (_LETTER if last_slash else _LETTER_BEFORE_DIGIT if joinable else _NEVER).match(
            text, pos
        )
        if piece:
            if last_slash:
                tail = piece.group(1).upper()
            else:
                chars += piece.group(1)
            last_slash = False
        else:
            piece = _GROUP.match(text, pos)
            if not piece:
                break
            chars, last_slash = chars + piece.group(1).upper(), False
        pos = end = piece.end()
    chars = chars.upper()
    if tail in (None, "A") and re.fullmatch(_BASE.pattern + r"[0-9A-Z]{8}", chars):
        return end, f"{chars[:6]}-{chars[6:]}/A"
    if tail is None and _BASE.fullmatch(chars) and not _UNIT.match(text, end):
        return end, chars
    return end, ""


def normalize_transcript(text: str) -> str:
    try:
        out: list[str] = []
        pos = 0
        while m := _START.search(text, pos):
            end, new = _span(text, m)
            out.append(text[pos : m.start()] + (new or text[m.start() : end]))
            pos = end
        out.append(text[pos:])
        return "".join(out).strip()
    except Exception:  # noqa: BLE001 - a transcript clean-up must never break the request
        return text.strip()
