"""In-memory login attempt limiter (D-52).

Contract:
- Keyed by make_key(email, client_ip): the lowercased, stripped email plus the client
  address. Unknown emails are tracked like real ones.
- try_begin(key, now=None) -> int | None. Atomic, under one lock: drops attempts older
  than WINDOW_SECONDS (sliding window); if MAX_FAILURES attempts remain it returns the
  seconds to wait (int >= 1) and records nothing; otherwise it records this attempt
  (counted before any password hashing) and returns None.
- succeed(key): forgets the key's attempts (called on a successful login).
- reset_all(): clears everything (tests).
- Env LOGIN_MAX_FAILURES (default 5) and LOGIN_WINDOW_SECONDS (default 300), read at
  import. State is per process, thread-safe, and bounded (MAX_TRACKED keys: expired keys
  are evicted first, then the oldest). `now` is a float for tests (default time.monotonic()).
"""

from __future__ import annotations

import math
import os
import threading
import time
from collections import deque

MAX_FAILURES = int(os.environ.get("LOGIN_MAX_FAILURES", "5"))
WINDOW_SECONDS = int(os.environ.get("LOGIN_WINDOW_SECONDS", "300"))
MAX_TRACKED = 10_000

_lock = threading.Lock()
_entries: dict[str, deque[float]] = {}  # key -> attempt timestamps, oldest first


def make_key(email: str, client_ip: str | None) -> str:
    return f"{email.strip().lower()}|{client_ip or '-'}"


def _prune(stamps: deque[float], now: float) -> None:
    while stamps and now - stamps[0] >= WINDOW_SECONDS:
        stamps.popleft()


def try_begin(key: str, now: float | None = None) -> int | None:
    now = time.monotonic() if now is None else now
    with _lock:
        stamps = _entries.get(key)
        if stamps is not None:
            _prune(stamps, now)
            if not stamps:
                del _entries[key]
                stamps = None
        if stamps is not None and len(stamps) >= MAX_FAILURES:
            return max(1, math.ceil(stamps[0] + WINDOW_SECONDS - now))
        if stamps is None:
            if len(_entries) >= MAX_TRACKED:
                for k in list(_entries):
                    _prune(_entries[k], now)
                    if not _entries[k]:
                        del _entries[k]
                while len(_entries) >= MAX_TRACKED:
                    del _entries[next(iter(_entries))]  # dicts keep insertion order: oldest
            stamps = _entries[key] = deque()
        stamps.append(now)
        return None


def succeed(key: str) -> None:
    with _lock:
        _entries.pop(key, None)


def reset_all() -> None:
    with _lock:
        _entries.clear()
