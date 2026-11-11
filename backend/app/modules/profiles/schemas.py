from uuid import UUID

from pydantic import Field, field_validator
from safevoice_shared.contracts.base import AgeBand, FrozenDTO


class Profile(FrozenDTO):
    user_id: UUID
    nickname: str
    age_band: AgeBand | None = None
    locale: str = "vi"
    reduced_motion: bool = False


class ProfilePatch(FrozenDTO):
    nickname: str | None = Field(default=None, min_length=2, max_length=32)
    age_band: AgeBand | None = None
    reduced_motion: bool | None = None

    @field_validator("nickname", mode="before")
    @classmethod
    def clean_nickname(cls, value):
        return value.strip() if isinstance(value, str) else value
