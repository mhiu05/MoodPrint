from datetime import date, datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field, StringConstraints

from app.contracts import DTO, VersionInput

JournalTag = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=60)]
MediaType = Literal["image", "audio", "video"]


class JournalEntryInput(DTO):
    local_date: date
    mood: int = Field(ge=1, le=5, strict=True)
    text: str = Field(default="", max_length=10000)
    emotions: list[JournalTag] = Field(default_factory=list, max_length=12)
    factors: list[JournalTag] = Field(default_factory=list, max_length=12)
    status: Literal["draft", "saved"] = "saved"


class JournalEntryEdit(JournalEntryInput, VersionInput):
    pass


class JournalMediaDTO(DTO):
    id: UUID
    type: MediaType
    mime_type: str
    size_bytes: int
    duration_seconds: float | None = None
    status: Literal["pending", "ready"]
    created_at: datetime


class JournalEntryDTO(JournalEntryInput):
    id: UUID
    timezone: str
    version: int
    created_at: datetime
    updated_at: datetime
    media: list[JournalMediaDTO] = Field(default_factory=list)


class JournalEntryPage(DTO):
    items: list[JournalEntryDTO]
    total: int
    offset: int
    limit: int
