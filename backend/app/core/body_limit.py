from uuid import uuid4

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send


class BodyLimitMiddleware:
    """Bound actual bytes, including chunked requests with no Content-Length."""

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] == "http" and self._school_denied(scope):
            response = JSONResponse(
                {
                    "error": {
                        "code": "NOT_FOUND",
                        "message": "Không tìm thấy.",
                        "retryable": False,
                        "requestId": str(uuid4()),
                    }
                },
                status_code=404,
                headers={"Cache-Control": "no-store"},
            )
            return await response(scope, receive, send)
        if scope["type"] != "http" or scope["method"] not in ("POST", "PUT", "PATCH", "DELETE"):
            return await self.app(scope, receive, send)
        limit = 3_000_000 if scope["path"] == "/api/v1/voice/transcriptions" else 65536
        chunks: list[bytes] = []
        size = 0
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            chunk = message.get("body", b"")
            size += len(chunk)
            if size > limit:
                response = JSONResponse(
                    {
                        "error": {
                            "code": "BODY_TOO_LARGE",
                            "message": "Nội dung yêu cầu quá lớn.",
                            "retryable": False,
                            "requestId": str(uuid4()),
                        }
                    },
                    status_code=413,
                    headers={"Cache-Control": "no-store"},
                )
                chunks.clear()
                return await response(scope, receive, send)
            chunks.append(chunk)
            if not message.get("more_body", False):
                break
        body = b"".join(chunks)
        chunks.clear()
        sent = False

        async def bounded_receive():
            nonlocal sent
            if not sent:
                sent = True
                return {"type": "http.request", "body": body, "more_body": False}
            return await receive()

        try:
            await self.app(scope, bounded_receive, send)
        finally:
            body = b""

    @staticmethod
    def _school_denied(scope: Scope) -> bool:
        from app.core.profile import is_school_safety, legacy_route_denied

        app = scope.get("app")
        settings = getattr(getattr(app, "state", None), "settings", None)
        return settings is not None and is_school_safety(settings) and legacy_route_denied(scope["path"])
