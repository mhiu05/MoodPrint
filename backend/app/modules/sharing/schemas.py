from datetime import datetime
from typing import Literal
from uuid import UUID

from moodprint_shared.contracts.base import FrozenDTO
from pydantic import Field, JsonValue, field_validator

SharedField = Literal[
    "title", "summary", "occurredAt", "place", "events", "people", "impactTags", "tried"
]


class ShareCreate(FrozenDTO):
    id: UUID
    case_id: UUID
    school_id: UUID
    identity_mode: Literal["alias", "disclose"] = "alias"
    shared_fields: list[SharedField] = Field(default_factory=list, max_length=8)
    evidence_ids: list[UUID] = Field(default_factory=list, max_length=100)


class SharePatch(FrozenDTO):
    version: int = Field(ge=1)
    school_id: UUID | None = None
    identity_mode: Literal["alias", "disclose"] | None = None
    shared_fields: list[SharedField] | None = Field(default=None, max_length=8)
    evidence_ids: list[UUID] | None = Field(default=None, max_length=100)

    @field_validator("school_id", "identity_mode", "shared_fields", "evidence_ids", mode="before")
    @classmethod
    def no_null(cls, value):
        if value is None:
            raise ValueError("This field cannot be null")
        return value


class ShareSubmit(FrozenDTO):
    confirmed: Literal[True]
    confirmation_version: str = Field(min_length=1, max_length=80)
    preview_hash: str = Field(min_length=1, max_length=128)


class ShareRead(FrozenDTO):
    id: UUID
    owner_id: UUID
    case_id: UUID | None
    school_id: UUID
    status: Literal["draft", "submitted", "in_review", "closed", "withdrawn"]
    identity_mode: Literal["alias", "disclose"]
    shared_fields: list[SharedField]
    evidence_ids: list[UUID] = Field(default_factory=list)
    snapshot: dict[str, JsonValue] | None
    confirmation_version: str | None
    confirmed_at: datetime | None
    submitted_at: datetime | None
    withdrawn_at: datetime | None
    version: int
    created_at: datetime
    updated_at: datetime


class SharePreview(FrozenDTO):
    snapshot: dict[str, JsonValue]
    preview_hash: str
    alias_notice: str = (
        "Bí danh giúp hạn chế định danh; nội dung bạn chọn vẫn có thể giúp người nhận nhận ra bạn."
    )


class SchoolRead(FrozenDTO):
    id: UUID
    name: str
    verification_status: Literal["synthetic", "verified"]
    created_at: datetime


class SchoolShareRead(FrozenDTO):
    id: UUID
    school_id: UUID
    status: Literal["submitted", "in_review", "closed"]
    snapshot: dict[str, JsonValue]
    submitted_at: datetime
