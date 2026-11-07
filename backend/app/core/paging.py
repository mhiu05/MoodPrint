"""Versioned, opaque keyset positions scoped to one owner's collection."""

import base64
import binascii
import re
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, ValidationError

from app.core.errors import ApiError


class CursorPosition(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    v: Literal[1] = 1
    scope: str
    owner: UUID
    at: AwareDatetime | None
    id: UUID


def encode_cursor(*, scope: str, owner: UUID, at: datetime | None, id: UUID) -> str:
    position = CursorPosition(scope=scope, owner=owner, at=at, id=id)
    return base64.urlsafe_b64encode(position.model_dump_json().encode()).decode().rstrip("=")


def decode_cursor(cursor: str | None, *, scope: str, owner: UUID) -> CursorPosition | None:
    if cursor is None:
        return None
    try:
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,2048}", cursor):
            raise ValueError("invalid cursor encoding")
        raw = base64.b64decode(cursor + "=" * (-len(cursor) % 4), altchars=b"-_", validate=True)
        position = CursorPosition.model_validate_json(raw)
        if position.scope != scope or position.owner != owner:
            raise ValueError("cursor belongs to another collection")
        if position.at is None and scope != "conversations":
            raise ValueError("collection requires a timestamp")
        return position
    except (ValueError, ValidationError, binascii.Error):
        raise ApiError("validation_failed", "Con trỏ phân trang không hợp lệ.", 422) from None
