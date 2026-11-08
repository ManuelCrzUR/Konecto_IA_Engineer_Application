"""Sliding-window limiter shared by the transcription and speech limits (D-52, D-53, D-54).

Contract:
- SlidingWindowLimiter(max_per_window, window_seconds, max_tracked=10_000)
- check_and_record(key, now=None) -> int | None: None when allowed (and counted); else the
  seconds (>= 1) until the oldest counted call leaves the window. `now` is monotonic (tests).
- reset(): clears everything. Per process, thread-safe, bounded (oldest inserted key evicted).
- `max_per_window` and `window_seconds` are plain attributes, read on every call.
"""

from __future__ import annotations

import math
import threading
import time
from collections import deque


class SlidingWindowLimiter:
    def __init__(self, max_per_window: int, window_seconds: int, max_tracked: int = 10_000) -> None:
        self.max_per_window = max_per_window
        self.window_seconds = window_seconds
        self.max_tracked = max_tracked
        self._lock = threading.Lock()
        self._calls: dict[str, deque[float]] = {}

    def check_and_record(self, key: str, now: float | None = None) -> int | None:
        now = time.monotonic() if now is None else now
        with self._lock:
            calls = self._calls.get(key)
            if calls is None:
                while len(self._calls) >= self.max_tracked:
                    del self._calls[next(iter(self._calls))]  # dicts keep insertion order
                calls = self._calls[key] = deque()
            while calls and now - calls[0] >= self.window_seconds:
                calls.popleft()
            if len(calls) >= self.max_per_window:
                return max(1, math.ceil(calls[0] + self.window_seconds - now))
            calls.append(now)
            return None

    def reset(self) -> None:
        with self._lock:
            self._calls.clear()
