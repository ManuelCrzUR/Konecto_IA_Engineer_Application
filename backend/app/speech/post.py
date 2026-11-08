"""Bounded JSON POST over urllib, shared by the transcription and speech clients.

Contract:
- post_bounded(url, headers, body, timeout, max_bytes, deadline) -> (status, body, content_type,
  retry_after). `timeout` is urllib's per-socket-operation timeout; `deadline` is the total
  seconds allowed for the whole read, checked between 64 KB chunks (TimeoutError when exceeded).
  The body is read at most max_bytes + 1 bytes, so a caller detects "too big" without buffering it.
- HTTP error statuses are returned (empty body), not raised. retry_after is the raw
  Retry-After header or "".
- Raises only OSError subclasses (TimeoutError included): http.client.HTTPException, such as
  IncompleteRead, is converted to OSError.
"""

from __future__ import annotations

import http.client
import time
import urllib.error
import urllib.request

CHUNK = 64 * 1024


def post_bounded(
    url: str,
    headers: dict[str, str],
    body: bytes,
    timeout: float,
    max_bytes: int,
    deadline: float,
) -> tuple[int, bytes, str, str]:
    start = time.monotonic()
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            chunks: list[bytes] = []
            size = 0
            while size <= max_bytes:
                if time.monotonic() - start > deadline:
                    raise TimeoutError("provider read exceeded the overall deadline")
                chunk = resp.read(min(CHUNK, max_bytes + 1 - size))
                if not chunk:
                    break
                chunks.append(chunk)
                size += len(chunk)
            return (
                resp.status,
                b"".join(chunks),
                resp.headers.get("Content-Type", ""),
                resp.headers.get("Retry-After", ""),
            )
    except urllib.error.HTTPError as exc:
        return exc.code, b"", "", exc.headers.get("Retry-After", "") if exc.headers else ""
    except http.client.HTTPException as exc:
        raise OSError(type(exc).__name__) from None
