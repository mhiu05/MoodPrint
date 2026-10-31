"""Check-in API DTOs (phase-1/05 §2). Times travel as "HH:MM" wall-clock strings."""

from datetime import date, datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field, field_validator

from app.contracts import DTO, BotId

Slot = Literal["morning", "evening"]
HHMM = Annotated[str, Field(pattern=r"^([01]\d|2[0-3]):[0-5]\d$")]
EligibilityReason = Literal[
    "teen_social_unavailable",
    "social_not_enabled",
    "social_restricted",
    "history_unavailable",
    "ai_unavailable",
]


class ProactiveSettingsView(DTO):
    timezone: str
    quiet_start: str
    quiet_end: str
    badges_enabled: bool
    journal_context_enabled: bool
    version: int
    policy_version: str


class Eligibility(DTO):
    allowed: bool
    reason: EligibilityReason | None = None


class ScheduleView(DTO):
    bot_id: BotId
    slot: Slot
    enabled: bool
    local_time: str
    weekdays: list[int]
    paused_until: date | None = None
    auto_paused: bool = False
    next_delivery_at: datetime | None = None
    version: int
    eligibility: Eligibility


class ProactiveLimits(DTO):
    daily_cap: int
    enabled_slots: int
    windows: dict[str, list[str]]
    step_minutes: int


class ProactiveView(DTO):
    available: bool
    settings: ProactiveSettingsView
    schedules: list[ScheduleView]
    limits: ProactiveLimits


class ProactiveSettingsInput(DTO):
    timezone: str = Field(min_length=1, max_length=64)
    quiet_start: HHMM
    quiet_end: HHMM
    badges_enabled: bool
    journal_context_enabled: bool
    expected_version: int = Field(ge=0)
    # The consent text the client showed; bumping it requires re-consent.
    policy_version: Literal["proactive-v1"]


class ScheduleInput(DTO):
    enabled: bool
    local_time: HHMM
    weekdays: list[int] = Field(min_length=1, max_length=7)
    paused_until: date | None = None
    expected_version: int = Field(ge=0)

    @field_validator("weekdays")
    @classmethod
    def iso_weekdays(cls, value: list[int]) -> list[int]:
        if len(set(value)) != len(value) or any(day not in range(1, 8) for day in value):
            raise ValueError("weekdays must be distinct ISO weekdays 1..7")
        return sorted(value)


class InboxLatest(DTO):
    conversation_id: UUID
    run_id: UUID
    slot: Slot
    delivered_at: datetime
    first_sequence: int


class InboxBot(DTO):
    bot_id: BotId
    unread: int
    latest: InboxLatest


class InboxView(DTO):
    """Counts and navigation only; never message text or a preview."""

    badges_enabled: bool
    unread_total: int
    bots: list[InboxBot]


class ConversationReadInput(DTO):
    last_read_sequence: int = Field(ge=0, le=1_000_000)


class ConversationReadView(DTO):
    conversation_id: UUID
    last_read_sequence: int
