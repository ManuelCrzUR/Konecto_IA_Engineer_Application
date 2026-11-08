"""Per-user text-to-speech limiter, in memory (D-54; same sliding window as limits.py).

Contract:
- check_and_record(user_id, now=None) -> int | None: None when allowed (and counted); else the
  seconds (>= 1) until the oldest counted call leaves the window.
- reset_all(): clears everything (tests).
- Env SPEECH_MAX_PER_WINDOW (default 120) and SPEECH_WINDOW_SECONDS (default 600), read at
  import. Implemented with window.SlidingWindowLimiter.
"""

from __future__ import annotations

import os

from app.speech.window import SlidingWindowLimiter

MAX_PER_WINDOW = int(os.environ.get("SPEECH_MAX_PER_WINDOW", "120"))
WINDOW_SECONDS = int(os.environ.get("SPEECH_WINDOW_SECONDS", "600"))

_limiter = SlidingWindowLimiter(MAX_PER_WINDOW, WINDOW_SECONDS)


def check_and_record(user_id: str, now: float | None = None) -> int | None:
    _limiter.max_per_window, _limiter.window_seconds = MAX_PER_WINDOW, WINDOW_SECONDS
    return _limiter.check_and_record(user_id, now)


def reset_all() -> None:
    _limiter.reset()
