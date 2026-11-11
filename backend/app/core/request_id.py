import re
from uuid import uuid4

from safevoice_shared.logging import request_id_context
from starlette.middleware.base import BaseHTTPMiddleware


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        supplied = request.headers.get("X-Request-ID", "")
        request.state.request_id = (
            supplied if re.fullmatch(r"[A-Za-z0-9_-]{1,64}", supplied) else str(uuid4())
        )
        with request_id_context(request.state.request_id):
            response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.request_id
        return response
