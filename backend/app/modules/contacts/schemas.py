from datetime import datetime
from uuid import UUID

from pydantic import Field, field_validator
from safevoice_shared.contracts.base import FrozenDTO


class ContactCreate(FrozenDTO):
    id: UUID
    label: str = Field(min_length=2, max_length=80)
    role: str = Field(min_length=2, max_length=40)

    @field_validator("label", "role", mode="before")
    @classmethod
    def trim(cls, value):
        return value.strip() if isinstance(value, str) else value


class ContactPatch(FrozenDTO):
    label: str | None = Field(default=None, min_length=2, max_length=80)
    role: str | None = Field(default=None, min_length=2, max_length=40)

    @field_validator("label", "role", mode="before")
    @classmethod
    def trim(cls, value):
        if value is None:
            raise ValueError("This field cannot be null")
        return value.strip() if isinstance(value, str) else value


class ContactRead(ContactCreate):
    owner_id: UUID
    created_at: datetime
    updated_at: datetime
