"""Pure ASGI middleware: reject oversized uploads before the body is read (D-53).

Contract:
- BodyLimitMiddleware(app, path="/api/transcribe", max_bytes=MAX_BODY_BYTES)
  Applies to POST on `path` only; every other request passes through untouched.
  - no Content-Length (chunked)            -> 411 {error: length_required}
  - Content-Length > max_bytes             -> 413 {error: audio_too_large}
  - body streamed past max_bytes anyway    -> 413 (a lying Content-Length cannot exceed the cap)
  Bodies are never buffered here; bytes are only counted as they stream to the route.
  `too_large` = (error, detail) used in the 413 body (D-54: POST /api/speech uses a 16 KB cap
  with text_too_long).
  max_bytes = 2 MB audio + 64 KB multipart overhead. Runs before auth, by design.
"""

from __future__ import annotations

import json

from starlette.types import ASGIApp, Message, Receive, Scope, Send

MAX_BODY_BYTES = 2 * 1024 * 1024 + 64 * 1024


class _TooLarge(Exception):
    pass


class BodyLimitMiddleware:
    def __init__(
        self,
        app: ASGIApp,
        path: str = "/api/transcribe",
        max_bytes: int = MAX_BODY_BYTES,
        too_large: tuple[str, str] = ("audio_too_large", "Audio is larger than 2 MB"),
    ) -> None:
        self.app, self.path, self.max_bytes = app, path, max_bytes
        self.too_large = too_large  # (error code, detail) of the 413 answer

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["method"] != "POST" or scope["path"] != self.path:
            await self.app(scope, receive, send)
            return
        raw = dict(scope["headers"]).get(b"content-length")
        if raw is None:
            await self._reject(send, 411, "length_required", "Content-Length is required")
            return
        if not raw.isdigit() or int(raw) > self.max_bytes:
            await self._reject(send, 413, *self.too_large)
            return

        seen = 0
        started = False

        async def counting_receive() -> Message:
            nonlocal seen
            message = await receive()
            if message["type"] == "http.request":
                seen += len(message.get("body", b""))
                if seen > self.max_bytes:
                    raise _TooLarge
            return message

        async def tracking_send(message: Message) -> None:
            nonlocal started
            started = True
            await send(message)

        try:
            await self.app(scope, counting_receive, tracking_send)
        except _TooLarge:
            if not started:
                await self._reject(send, 413, *self.too_large)

    @staticmethod
    async def _reject(send: Send, status: int, error: str, detail: str) -> None:
        body = json.dumps({"error": error, "detail": detail}).encode()
        headers = [(b"content-type", b"application/json"), (b"content-length", b"%d" % len(body))]
        await send({"type": "http.response.start", "status": status, "headers": headers})
        await send({"type": "http.response.body", "body": body})
