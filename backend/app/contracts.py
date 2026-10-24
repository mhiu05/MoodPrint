from datetime import date, datetime
from typing import Annotated, Literal
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StringConstraints, field_validator
from pydantic.alias_generators import to_camel

Purpose = Literal["AI", "MEM", "MATCH", "VOICE"]
BotId = Literal["may", "guong", "nhip", "rure", "caunoi"]
ShortText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
MessageText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]


class DTO(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel, populate_by_name=True, extra="forbid", from_attributes=True
    )


class ErrorDetail(DTO):
    code: str
    message: str
    retryable: bool = False
    request_id: str


class ApiError(DTO):
    error: ErrorDetail


class VersionInput(DTO):
    expected_version: int = Field(ge=0)


class EmptyInput(DTO):
    pass


class ConsentView(DTO):
    enabled: bool
    version: int
    policy_version: str = "v1"


class FeatureView(DTO):
    ai: bool = False
    matching: bool = False
    voice: bool = False


class SessionView(DTO):
    user_id: UUID
    alias: str
    age_band: Literal["unknown", "under16", "teen", "adult"]
    eligible: bool
    consents: dict[Purpose, ConsentView]
    csrf_token: str
    server_time: datetime
    timezone: str
    features: FeatureView
    data_version: int = 1
    birth_year: int | None = None
    eligibility_version: int = 0


class EligibilityInput(VersionInput):
    birth_year: int = Field(ge=1900, le=9999, strict=True)
    confirmed_minimum_age: StrictBool
    confirmed_adult_age: StrictBool = False
    policy_version: Literal["self-declared-age-v1"]

    @field_validator("confirmed_minimum_age")
    @classmethod
    def minimum_age_confirmed(cls, value: bool) -> bool:
        if not value:
            raise ValueError("Explicit minimum-age confirmation is required")
        return value


class LoginInput(DTO):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=1024, repr=False)


class EmailInput(DTO):
    email: str = Field(min_length=3, max_length=254, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class SignupInput(EmailInput):
    # Supabase hashes with bcrypt, which ignores bytes beyond 72.
    password: str = Field(min_length=8, max_length=72, repr=False)


class PasswordResetInput(DTO):
    access_token: str = Field(min_length=20, max_length=4096, repr=False)
    password: str = Field(min_length=8, max_length=72, repr=False)


class AuthNotice(DTO):
    status: Literal["sent", "updated", "confirmed"]


class ConsentInput(VersionInput):
    enabled: bool
    policy_version: Literal["v1"]


class PrivateItemInput(DTO):
    text: ShortText


class PrivateItemEdit(PrivateItemInput, VersionInput):
    pass


class PrivateItemDTO(DTO):
    id: UUID
    text: str
    version: int
    origin: Literal["declared", "ai"]
    status: Literal["confirmed", "edited", "deleted"]


class MoodInput(VersionInput):
    value: int = Field(ge=1, le=5, strict=True)
    note: str = Field(default="", max_length=120)
    timezone: str = "Asia/Bangkok"

    @field_validator("timezone")
    @classmethod
    def timezone_exists(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError("Unknown IANA timezone") from exc
        return value


class MoodDTO(DTO):
    id: UUID
    local_date: date
    value: int
    note: str
    timezone: str
    version: int


class ActionReceipt(DTO):
    action_id: UUID
    status: Literal["succeeded"] = "succeeded"
    resource_id: str
    resource_version: int


class BotPublicDTO(DTO):
    bot_id: BotId
    name: str
    role: str
    description: str
    starters: list[str]
    avatar_key: str
