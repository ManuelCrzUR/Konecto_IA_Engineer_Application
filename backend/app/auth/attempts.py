"""In-memory login attempt limiter (D-52).

Contract:
- Keyed by the lowercased, stripped email; unknown emails are tracked like real ones.
- blocked(email, now=None) -> seconds to wait (int >= 1) when the email has
  MAX_FAILURES failures inside the last WINDOW_SECONDS, else None.
- record_failure(email, now=None): adds a failure; the window starts at the first
  failure and a block lasts until that window ends.
- reset(email): forgets the email (called on a successful login).
- reset_all(): clears everything (tests).
- Env LOGIN_MAX_FAILURES (default 5) and LOGIN_WINDOW_SECONDS (default 300), read at
  import. State is per process, thread-safe, and bounded (MAX_TRACKED emails, oldest
  evicted; expired entries dropped). `now` is a float epoch for tests (default time.monotonic()).
"""

from __future__ import annotations

import math
import os
import threading
import time

MAX_FAILURES = int(os.environ.get("LOGIN_MAX_FAILURES", "5"))
WINDOW_SECONDS = int(os.environ.get("LOGIN_WINDOW_SECONDS", "300"))
MAX_TRACKED = 10_000

_lock = threading.Lock()
_entries: dict[str, tuple[float, int]] = {}  # key -> (window start, failures)


def _key(email: str) -> str:
    return email.strip().lower()


def _live(key: str, now: float) -> tuple[float, int] | None:
    entry = _entries.get(key)
    if entry is not None and now - entry[0] >= WINDOW_SECONDS:
        del _entries[key]
        return None
    return entry


def blocked(email: str, now: float | None = None) -> int | None:
    now = time.monotonic() if now is None else now
    with _lock:
        entry = _live(_key(email), now)
        if entry is None or entry[1] < MAX_FAILURES:
            return None
        return max(1, math.ceil(entry[0] + WINDOW_SECONDS - now))


def record_failure(email: str, now: float | None = None) -> None:
    now = time.monotonic() if now is None else now
    key = _key(email)
    with _lock:
        entry = _live(key, now)
        if entry is None:
            if len(_entries) >= MAX_TRACKED:
                for k in [k for k, (t, _) in _entries.items() if now - t >= WINDOW_SECONDS]:
                    del _entries[k]
                while len(_entries) >= MAX_TRACKED:
                    del _entries[next(iter(_entries))]  # dicts keep insertion order: oldest
            _entries[key] = (now, 1)
        else:
            _entries[key] = (entry[0], entry[1] + 1)


def reset(email: str) -> None:
    with _lock:
        _entries.pop(_key(email), None)


def reset_all() -> None:
    with _lock:
        _entries.clear()
