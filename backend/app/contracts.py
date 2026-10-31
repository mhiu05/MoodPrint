from datetime import date, datetime
from typing import Annotated, Literal
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StringConstraints, field_validator
from pydantic.alias_generators import to_camel

Purpose = Literal["AI", "MEM", "MATCH", "VOICE"]
BotId = Literal["may", "guong", "nhip", "rure", "caunoi", "dieuphoi", "nhatky", "hoatdong"]
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
    # Set with 409 ACTIVITY_IN_PROGRESS so the client can open the existing session.
    current_session_id: str | None = None


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
    # Service availability is independent of per-user AI consent and quota.
    ai_status: Literal["disabled", "configuration_missing", "configuration_invalid", "ready", "test_provider"] = "disabled"
    matching: bool = False
    voice: bool = False
    # Remaining AI turns today (Asia/Bangkok day); null when AI is unavailable.
    ai_quota_remaining: int | None = None
    # Voluntary ratings are open to live eligible visitors only while the rollout flag is on.
    feedback: bool = False
    # Scheduled check-ins: flag/cohort, registered, AI service and saved history available.
    proactive: bool = False
    # Companion collaboration (Phase 2): flag/cohort, registered adult, v2 stream, saved history.
    collaboration: bool = False
    # V3: the three default agents (flag/cohort); legacy companions become read-only history.
    three_agents: bool = False
    # V3: Điều phối may consult/hand over (registered adult, saved history, v2 stream).
    smart_orchestration: bool = False
    # V3: AI groups (registered adult, saved history, v2 stream).
    group_chat: bool = False


class NoticeView(DTO):
    kind: Literal["warning", "restricted"]
    until: datetime | None = None


class GuestQuota(DTO):
    """Durable remaining allowance for one trial (never per day, never reset by a new tab)."""

    ai_turns_remaining: int = Field(ge=0)
    voice_clips_remaining: int = Field(ge=0)
    voice_seconds_remaining: float = Field(ge=0)


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
    # Present only for operator-granted staff; drives the hidden /admin/reports route.
    staff: Literal["moderator", "admin"] | None = None
    notices: list[NoticeView] = Field(default_factory=list)
    # Server-owned lifecycle. Registered responses carry explicit nulls for the guest fields.
    account_kind: Literal["registered", "guest"] = "registered"
    guest_started_at: datetime | None = None
    guest_expires_at: datetime | None = None
    guest_quota: GuestQuota | None = None


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


class MoodInput(VersionInput):
    value: int = Field(ge=1, le=5, strict=True)
    note: Annotated[str, StringConstraints(strip_whitespace=True, max_length=120)] = ""
    # Accepted for compatibility; date boundaries always follow the account timezone.
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


class MoodBucket(DTO):
    local_date: date
    value: int | None


class MoodSummaryDTO(DTO):
    """Aggregates only recorded days; missing days stay null and are never imputed."""

    from_date: date = Field(alias="from")
    to_date: date = Field(alias="to")
    count: int
    mean: float | None
    min: int | None
    max: int | None
    insight_available: bool
    buckets: list[MoodBucket]


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
    # V3: a legacy companion (read-only history) and the agent that took over its purpose.
    legacy: bool = False
    replaced_by: BotId | None = None
