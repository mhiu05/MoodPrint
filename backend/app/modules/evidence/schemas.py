from datetime import datetime
from typing import Literal
from uuid import UUID

from moodprint_shared.contracts.base import FrozenDTO
from moodprint_shared.contracts.evidence import EvidenceMeta
from pydantic import Field, field_validator


class UploadCreate(FrozenDTO):
    id: UUID
    case_id: UUID | None = None
    filename: str = Field(min_length=1, max_length=255)
    mime_type: str | None = Field(default=None, max_length=255)
    byte_size: int = Field(ge=0)
    sha256: str | None = Field(default=None, pattern=r"^[a-fA-F0-9]{64}$")
    shown_timestamp: str = Field(default="", max_length=500)
    captured_at_label: str = Field(default="", max_length=500)

    @field_validator("sha256")
    @classmethod
    def normalize_hash(cls, value):
        return value.lower() if value else value


class NoteCreate(FrozenDTO):
    id: UUID
    case_id: UUID | None = None
    original_text: str = Field(min_length=1, max_length=20000)
    shown_timestamp: str = Field(default="", max_length=500)
    captured_at_label: str = Field(default="", max_length=500)


class EvidencePatch(FrozenDTO):
    user_edited_text: str | None = Field(default=None, max_length=20000)
    review_status: Literal["unreviewed", "corrected", "confirmed", "rejected"] | None = None
    limitations: list[str] | None = Field(default=None, max_length=50)

    @field_validator("review_status", "limitations", mode="before")
    @classmethod
    def reject_null(cls, value):
        if value is None:
            raise ValueError("This field cannot be null")
        return value


class UploadInfo(FrozenDTO):
    url: str
    token: str
    chunk_size: int
    object_name: str
    bucket_name: str
    expires_at: datetime


class UploadReply(FrozenDTO):
    evidence: EvidenceMeta
    upload: UploadInfo
