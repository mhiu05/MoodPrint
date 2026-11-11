from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field, JsonValue, field_validator
from safevoice_shared.contracts.base import FrozenDTO


class DraftCreate(FrozenDTO):
    id: UUID
    case_id: UUID | None = None
    recipient_type: str = Field(min_length=1, max_length=80)
    identity_mode: Literal["alias", "disclose"] = "alias"
    content: str = Field(default="", max_length=20000)
    compose: dict[str, JsonValue] = Field(default_factory=dict)
    status: Literal["draft", "prepared"] = "draft"


class DraftPatch(FrozenDTO):
    version: int = Field(ge=1)
    case_id: UUID | None = None
    recipient_type: str | None = Field(default=None, min_length=1, max_length=80)
    identity_mode: Literal["alias", "disclose"] | None = None
    content: str | None = Field(default=None, max_length=20000)
    compose: dict[str, JsonValue] | None = None
    status: Literal["draft", "prepared"] | None = None

    @field_validator(
        "recipient_type", "identity_mode", "content", "compose", "status", mode="before"
    )
    @classmethod
    def reject_null(cls, value):
        if value is None:
            raise ValueError("This field cannot be null")
        return value


class DraftRead(DraftCreate):
    owner_id: UUID
    version: int
    created_at: datetime
    updated_at: datetime
