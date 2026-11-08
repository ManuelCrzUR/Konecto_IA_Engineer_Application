"""Per-user transcription limiter, in memory (D-53; same idea as auth/attempts.py, D-52).

Contract:
- check_and_record(user_id, now=None) -> int | None: None when the call is allowed (and it
  is counted); else the seconds to wait (int >= 1) until the oldest counted call leaves the window.
- reset_all(): clears everything (tests).
- Env TRANSCRIBE_MAX_PER_WINDOW (default 20) and TRANSCRIBE_WINDOW_SECONDS (default 600),
  read at import. Implemented with window.SlidingWindowLimiter.
"""

from __future__ import annotations

import os

from app.speech.window import SlidingWindowLimiter

MAX_PER_WINDOW = int(os.environ.get("TRANSCRIBE_MAX_PER_WINDOW", "20"))
WINDOW_SECONDS = int(os.environ.get("TRANSCRIBE_WINDOW_SECONDS", "600"))

_limiter = SlidingWindowLimiter(MAX_PER_WINDOW, WINDOW_SECONDS)


def check_and_record(user_id: str, now: float | None = None) -> int | None:
    # Re-read the module values so tests can monkeypatch them.
    _limiter.max_per_window, _limiter.window_seconds = MAX_PER_WINDOW, WINDOW_SECONDS
    return _limiter.check_and_record(user_id, now)


def reset_all() -> None:
    _limiter.reset()
