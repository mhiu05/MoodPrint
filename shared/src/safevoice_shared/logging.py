"""Content-free structured logging with recursive credential redaction."""

import json
import logging
import re
from collections.abc import Generator, Mapping
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any, cast

request_id: ContextVar[str | None] = ContextVar("request_id", default=None)
REDACTED = "[REDACTED]"
_SENSITIVE = {
    "authorization",
    "apikey",
    "api_key",
    "token",
    "password",
    "content",
    "message_data",
    "original_text",
    "claims_json",
    "database_url",
    "supabase_db_url",
    "openai_api_key",
    "supabase_secret_key",
    "memory",
    "tool_arguments",
}
_CREDENTIAL = re.compile(
    r"eyJ[A-Za-z0-9_-]*\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+|\bsk-[A-Za-z0-9_-]+|\bsb_secret_[A-Za-z0-9_-]+",
    re.IGNORECASE,
)
_RECORD_KEYS = set(logging.makeLogRecord({}).__dict__) | {
    "message",
    "asctime",
    "request_id",
    "exception_type",
}


def redact(value: Any) -> Any:
    if isinstance(value, Mapping):
        mapping = cast(Mapping[Any, Any], value)
        return {
            str(key): REDACTED if str(key).lower() in _SENSITIVE else redact(item)
            for key, item in mapping.items()
        }
    if isinstance(value, (list, tuple)):
        return [redact(item) for item in cast(list[Any] | tuple[Any, ...], value)]
    if isinstance(value, str):
        return _CREDENTIAL.sub(REDACTED, value)
    return value


@contextmanager
def request_id_context(value: str) -> Generator[None]:
    token = request_id.set(value)
    try:
        yield
    finally:
        request_id.reset(token)


class RedactingFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = redact(record.msg)
        record.msg = redact(record.getMessage())
        record.args = ()
        record.request_id = request_id.get()
        record.exception_type = (
            record.exc_info[0].__name__ if record.exc_info and record.exc_info[0] else None
        )
        record.exc_info = None
        record.exc_text = None
        record.stack_info = None
        for key in list(record.__dict__):
            if key not in _RECORD_KEYS:
                record.__dict__[key] = (
                    REDACTED if key.lower() in _SENSITIVE else redact(record.__dict__[key])
                )
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": redact(record.getMessage()),
            "request_id": getattr(record, "request_id", request_id.get()),
        }
        for key, value in record.__dict__.items():
            if key not in _RECORD_KEYS:
                payload[key] = REDACTED if key.lower() in _SENSITIVE else redact(value)
        exception_type = getattr(record, "exception_type", None)
        if exception_type:
            payload["exception_type"] = exception_type
        return json.dumps(payload, ensure_ascii=False, default=str)


def configure_logging(*, production: bool = False, level: str = "INFO") -> None:
    handler = logging.StreamHandler()
    handler.addFilter(RedactingFilter())
    handler.setFormatter(
        JsonFormatter() if production else logging.Formatter("%(levelname)s %(name)s %(message)s")
    )
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)
    # Uvicorn installs non-propagating handlers before the application lifespan.
    # Route them through the same filter so ASGI exception tracebacks cannot
    # bypass content and credential redaction.
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        server_logger = logging.getLogger(name)
        server_logger.handlers.clear()
        server_logger.propagate = True
