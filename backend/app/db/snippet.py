"""Search snippet: a short window of text around the first match of a query.

Contract: make_snippet(text, query, width=80) -> str. Pure, no I/O.
- Newlines and runs of whitespace collapse to single spaces.
- The window is about `width` chars centred on the first case-insensitive match.
- Cut edges move outward to whitespace so a token (a number, a part number such
  as "764A00-11300000/A") is never split; if no whitespace is near, it cuts hard.
- "…" is prepended/appended where text was cut. No match -> the start of the text.
"""

from __future__ import annotations

import re

WIDTH = 80
_MAX_EXPAND = 24  # how far a cut may move outward to reach whitespace


def _snap(text: str, pos: int, step: int) -> int:
    """Move `pos` in direction `step` until it sits on a token boundary."""
    if pos <= 0 or pos >= len(text):
        return max(0, min(pos, len(text)))
    p = pos
    for _ in range(_MAX_EXPAND):
        if text[p - 1].isspace() or text[p].isspace():
            return p
        p += step
        if p <= 0 or p >= len(text):
            return max(0, min(p, len(text)))
    return pos


def make_snippet(text: str, query: str, width: int = WIDTH) -> str:
    flat = " ".join(text.split())
    m = (
        re.search(re.escape(" ".join(query.split())), flat, re.IGNORECASE)
        if query.strip()
        else None
    )
    if m is None:
        start, end = 0, min(len(flat), width)
    else:
        start = max(0, m.start() - max(0, width - (m.end() - m.start())) // 2)
        end = min(len(flat), max(start + width, m.end()))
        start = max(0, min(start, end - width)) if end - start < width else start
    start = _snap(flat, start, -1)
    end = _snap(flat, end, +1)
    body = flat[start:end].strip()
    return ("…" if start > 0 else "") + body + ("…" if end < len(flat) else "")
