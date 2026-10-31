from datetime import date, datetime, timedelta
from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from app.contracts import DTO, BotId, MessageText, ShortText, VersionInput


class NavigateCard(DTO):
    kind: Literal["navigate_bot"]
    bot_id: BotId


class MoodCard(DTO):
    kind: Literal["mood_form"]


class DiscoveryCard(DTO):
    kind: Literal["discovery"]


Card = Annotated[NavigateCard | MoodCard | DiscoveryCard, Field(discriminator="kind")]


class AiOutput(DTO):
    text: str = Field(min_length=1, max_length=6000)
    cards: list[Card] = Field(default_factory=list, max_length=3)


MAX_BUBBLES = 4
MAX_BUBBLE_CHARS = 1500
# SSE v1 joins bubbles with "\n\n" and old clients reject a final text above 6000 chars.
MAX_REPLY_CHARS = 5900


class Bubble(DTO):
    """Model-facing: one short chat message of a multi-bubble reply."""

    text: str = Field(min_length=1, max_length=MAX_BUBBLE_CHARS)
    cards: list[Card] = Field(default_factory=list, max_length=3)

    @field_validator("text")
    @classmethod
    def visible(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("bubble must contain visible text")
        return value.strip()


class CompanionReply(DTO):
    """Model-facing: one turn is 1–4 bubbles, by default one. Not a public DTO."""

    messages: list[Bubble] = Field(min_length=1, max_length=MAX_BUBBLES)

    @model_validator(mode="after")
    def bounded(self):
        joined = sum(len(bubble.text) for bubble in self.messages) + 2 * (len(self.messages) - 1)
        if joined > MAX_REPLY_CHARS:
            raise ValueError("reply too long")
        if sum(len(bubble.cards) for bubble in self.messages) > 3:
            raise ValueError("at most 3 cards per reply")
        texts = [bubble.text.casefold() for bubble in self.messages]
        if len(set(texts)) != len(texts):
            raise ValueError("duplicate bubbles")
        return self


class AiReply(DTO):
    """Validated, backend-rendered reply: the parts persisted as one bubble each."""

    parts: list[AiOutput] = Field(min_length=1, max_length=MAX_BUBBLES)

    def joined(self) -> AiOutput:
        """The ai-events-v1 / legacy single-message representation."""
        return AiOutput(
            text="\n\n".join(part.text for part in self.parts),
            cards=[card for part in self.parts for card in part.cards],
        )


class ConversationInput(DTO):
    bot_id: BotId
    persistent: bool | None = None


class ConversationRename(DTO):
    title: str = Field(min_length=1, max_length=100)

    @field_validator("title")
    @classmethod
    def visible_title(cls, value: str) -> str:
        value = " ".join(value.split())
        if not value:
            raise ValueError("title must contain visible text")
        return value


class ConversationHeader(DTO):
    conversation_id: UUID
    bot_id: BotId
    version: int
    expires_at: datetime
    persistent: bool = False
    title: str = "Cuộc trò chuyện mới"
    created_at: datetime | None = None
    updated_at: datetime | None = None


class AIMessage(DTO):
    id: UUID
    actor: Literal["self", "bot"]
    text: str
    cards: list[Card] = Field(default_factory=list, max_length=3)
    created_at: datetime | None = None
    run_id: UUID | None = None
    status: str | None = None
    # Bubble position within its run (legacy rows: part 0 of 1).
    part_index: int = Field(default=0, ge=0, le=MAX_BUBBLES - 1)
    part_count: int = Field(default=1, ge=1, le=MAX_BUBBLES)
    origin: Literal["user", "proactive"] = "user"
    proactive_slot: Literal["morning", "evening"] | None = None


class ConversationView(ConversationHeader):
    messages: list[AIMessage]
    active_run_id: UUID | None
    active_run_version: int | None = None
    has_more_messages: bool = False


class AiPreferenceInput(DTO):
    history_enabled: bool
    semantic_memory_enabled: bool
    expected_version: int = Field(ge=1)
    policy_version: Literal["ai-data-v1"]


class AiPreferenceView(DTO):
    history_enabled: bool
    semantic_memory_enabled: bool
    version: int
    policy_version: str
    retention_days: int
    history_available: bool
    semantic_memory_available: bool


class MoodReadScope(DTO):
    from_date: date
    to_date: date

    @model_validator(mode="after")
    def bounded_range(self):
        if not timedelta(0) <= self.to_date - self.from_date <= timedelta(days=89):
            raise ValueError("Select between one and 90 consecutive days")
        return self


class StartRunInput(DTO):
    text: MessageText
    client_message_id: UUID
    expected_conversation_version: int = Field(ge=1)
    mood_scope: MoodReadScope | None = None


class AIRunAccepted(DTO):
    run_id: UUID
    conversation_id: UUID
    version: int
    run_version: int = 1
    events_url: str


class AIEvent(DTO):
    version: Literal["ai-events-v1"] = "ai-events-v1"
    seq: str = Field(pattern=r"^[1-9][0-9]*$")
    type: Literal["progress", "final", "completed", "failed", "cancelled"]
    data: dict


class ProposalConfirm(VersionInput):
    edited_text: ShortText | None = None


class MemoryDTO(DTO):
    id: UUID
    bot_id: BotId
    text: str
    version: int
    status: str


class MemoryEdit(VersionInput):
    text: ShortText
