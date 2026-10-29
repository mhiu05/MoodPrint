"""Outermost ASGI guard: no private guest byte is dispatched at or after the trial deadline.

``require_actor`` records a conservative monotonic deadline in the request state for guests. This
middleware wraps the *outermost* ``send``: it holds response headers until the first body frame is
authorized and judges every body frame on a synchronous monotonic comparison made immediately
before the underlying send is invoked (no awaited queue sits between that check and the call; the
check repeats after the header send, which is a real await). Logical authorization is distinct from
physical TCP delivery: a frame cleared before T may still reach the client slightly later.
"""

import json
import time
from collections.abc import Callable

# The only bytes allowed after T on an already started stream: a content-free notice.
REVOKED_EVENT = b"event: revoked\ndata: {}\n\n"


class GuestOutputMiddleware:
    def __init__(self, app, clock: Callable[[], float] = time.monotonic):
        self.app, self.clock = app, clock

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        state = scope.setdefault("state", {})
        held: dict | None = None
        headers_sent = closed = False

        async def guarded(message):
            nonlocal held, headers_sent, closed
            guest = state.get("guest_output")
            if guest is None:
                await send(message)
                return
            if closed:
                return
            if message["type"] == "http.response.start":
                held = message  # not released until its first body frame is authorized
                return
            if message["type"] != "http.response.body":
                await send(message)
                return
            # Synchronous decision, then the send is invoked with nothing awaited in between.
            if self.clock() >= guest.monotonic_deadline:
                closed = True
                if headers_sent:
                    if message.get("body") == REVOKED_EVENT:
                        await send({**message, "more_body": True})
                    await send({"type": "http.response.body", "body": b"", "more_body": False})
                else:
                    await self._expired(state, send)
                return
            if not headers_sent and held is not None:
                headers_sent = True
                await send(held)  # a real await: the body frame is judged again afterwards
                if self.clock() >= guest.monotonic_deadline:
                    closed = True
                    await send({"type": "http.response.body", "body": b"", "more_body": False})
                    return
            await send(message)

        await self.app(scope, receive, guarded)

    @staticmethod
    async def _expired(state, send) -> None:
        body = json.dumps(
            {
                "error": {
                    "code": "GUEST_EXPIRED",
                    "message": "Lượt dùng thử đã kết thúc.",
                    "retryable": False,
                    "requestId": state.get("request_id", ""),
                }
            }
        ).encode()
        headers = [
            (b"content-type", b"application/json"),
            (b"content-length", str(len(body)).encode()),
            (b"cache-control", b"no-store"),
        ]
        for name, path in (
            ("moodprint_session", "/"),
            ("moodprint_csrf", "/"),
            ("moodprint_guest_intent", "/api/v1/auth"),
        ):
            headers.append(
                (b"set-cookie", f'{name}=""; Max-Age=0; Path={path}; SameSite=lax'.encode())
            )
        await send({"type": "http.response.start", "status": 401, "headers": headers})
        await send({"type": "http.response.body", "body": body, "more_body": False})
