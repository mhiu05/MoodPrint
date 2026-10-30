"""Classify transient database failures without logging driver text."""

from __future__ import annotations

import re
from typing import Final

from sqlalchemy.exc import InterfaceError, OperationalError, ProgrammingError
from sqlalchemy.exc import TimeoutError as PoolTimeout

_SQLSTATE: Final = re.compile(r"^[0-9A-Z]{5}$")
_LIMIT: Final = frozenset({"53300"})
_UNAVAILABLE: Final = frozenset({"08000", "08001", "08003", "08004", "08006", "08007", "57P01", "57P02", "57P03"})
_LIMIT_PHRASES: Final = (
    "too many connections for role",
    "too many connections",
    "remaining connection slots are reserved",
)
_UNAVAILABLE_PHRASES: Final = (
    "connection refused",
    "could not connect to server",
    "server closed the connection unexpectedly",
    "timeout expired",
    "ssl connection has been closed unexpectedly",
    "name or service not known",
    "temporary failure in name resolution",
)


def sqlstate_of(error: BaseException) -> str | None:
    current: BaseException | None = error
    seen: set[int] = set()
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        for candidate in (current, getattr(current, "orig", None)):
            state = getattr(candidate, "sqlstate", None) or getattr(candidate, "pgcode", None)
            if isinstance(state, str) and _SQLSTATE.fullmatch(state):
                return state
        cause = current.__cause__
        current = cause if isinstance(cause, BaseException) else None
    return None


def _chain(error: BaseException):
    current: BaseException | None = error
    seen: set[int] = set()
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        yield current
        orig = getattr(current, "orig", None)
        if isinstance(orig, BaseException) and id(orig) not in seen:
            yield orig
        cause = current.__cause__
        current = cause if isinstance(cause, BaseException) else None


def _text(error: BaseException) -> str:
    parts: list[str] = []
    for item in _chain(error):
        parts.append(str(item).lower())
    return "\n".join(parts)


def database_failure_category(error: BaseException) -> str | None:
    """Return connection_limit, connection_unavailable, pool_timeout, or None.

    Programming errors stay unclassified so they remain HTTP 500. Phrase matching
    is used only when the driver did not provide a SQLSTATE.
    """
    if any(isinstance(item, ProgrammingError) for item in _chain(error)):
        return None
    if any(isinstance(item, PoolTimeout) for item in _chain(error)):
        return "pool_timeout"
    state = sqlstate_of(error)
    if state in _LIMIT:
        return "connection_limit"
    if state in _UNAVAILABLE:
        return "connection_unavailable"
    if state is not None:
        return None
    if not any(isinstance(item, (OperationalError, InterfaceError, ConnectionError, OSError)) for item in _chain(error)):
        return None
    text = _text(error)
    if any(phrase in text for phrase in _LIMIT_PHRASES):
        return "connection_limit"
    if any(phrase in text for phrase in _UNAVAILABLE_PHRASES):
        return "connection_unavailable"
    return None
