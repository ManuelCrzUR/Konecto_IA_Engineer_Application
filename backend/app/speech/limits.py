"""Per-user transcription limiter, in memory (D-53; same idea as auth/attempts.py, D-52).

Contract:
- check_and_record(user_id, now=None) -> int | None: None when the call is allowed (and it
  is counted); else the seconds to wait (int >= 1) until the oldest counted call leaves the window.
- reset_all(): clears everything (tests).
- Env TRANSCRIBE_MAX_PER_WINDOW (default 20) and TRANSCRIBE_WINDOW_SECONDS (default 600),
  read at import. Sliding window, per process, thread-safe, bounded (MAX_TRACKED users,
  oldest inserted evicted). `now` is a monotonic float for tests.
"""

from __future__ import annotations

import math
import os
import threading
import time
from collections import deque

MAX_PER_WINDOW = int(os.environ.get("TRANSCRIBE_MAX_PER_WINDOW", "20"))
WINDOW_SECONDS = int(os.environ.get("TRANSCRIBE_WINDOW_SECONDS", "600"))
MAX_TRACKED = 10_000

_lock = threading.Lock()
_calls: dict[str, deque[float]] = {}


def check_and_record(user_id: str, now: float | None = None) -> int | None:
    now = time.monotonic() if now is None else now
    with _lock:
        calls = _calls.get(user_id)
        if calls is None:
            while len(_calls) >= MAX_TRACKED:
                del _calls[next(iter(_calls))]  # dicts keep insertion order: oldest
            calls = _calls[user_id] = deque()
        while calls and now - calls[0] >= WINDOW_SECONDS:
            calls.popleft()
        if len(calls) >= MAX_PER_WINDOW:
            return max(1, math.ceil(calls[0] + WINDOW_SECONDS - now))
        calls.append(now)
        return None


def reset_all() -> None:
    with _lock:
        _calls.clear()
