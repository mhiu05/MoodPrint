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
    # V3: the companion is one of the five legacy companions (history may be read-only).
    legacy: bool = False
    # V3 handoff: the specialist currently answering this conversation (None = bot_id).
    active_agent: Literal["dieuphoi", "nhatky", "hoatdong"] | None = None


class CollaborationSummary(DTO):
    """Public line of a completed, used consultation. ``summary`` is a backend template chosen
    by (edge, rule); never model text (ADR-11)."""

    kind: Literal["nhip_energy_for_rure", "nhip_habit_for_may", "rure_activity_for_guong"]
    companions: list[BotId] = Field(min_length=2, max_length=2)
    summary: str = Field(min_length=1, max_length=200)


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
    # Phase 2: backend-rendered line, only on part 0 of a run whose receipt is completed and used.
    collaboration: CollaborationSummary | None = None
    # V3: the companion whose run produced this bubble (handoff/group); None for the user.
    speaker: BotId | None = None


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
    version: Literal["ai-events-v1", "ai-events-v2"] = "ai-events-v1"
    seq: str = Field(pattern=r"^[1-9][0-9]*$")
    type: Literal["progress", "final", "completed", "failed", "cancelled"]
    data: dict


class AIReplyBubble(DTO):
    """One validated bubble of an ai-events-v2 final event."""

    message_id: UUID
    part_index: int = Field(ge=0, le=MAX_BUBBLES - 1)
    text: str
    cards: list[Card] = Field(default_factory=list, max_length=3)


class AIFinalV2(DTO):
    """ai-events-v2 final data; v1 receives the bubbles joined as {text, cards}."""

    part_count: int = Field(ge=1, le=MAX_BUBBLES)
    messages: list[AIReplyBubble] = Field(min_length=1, max_length=MAX_BUBBLES)


def final_v2(bubbles: list[tuple[UUID, str, list]]) -> dict:
    """Normalized final payload from (message id, text, JSON cards) in part order."""
    return AIFinalV2(
        part_count=len(bubbles),
        messages=[
            AIReplyBubble(message_id=identity, part_index=index, text=text, cards=cards)
            for index, (identity, text, cards) in enumerate(bubbles)
        ],
    ).model_dump(mode="json", by_alias=True)


def as_protocol(event: AIEvent, protocol: int, final: dict | None = None) -> AIEvent:
    """Render one stored event for the requested SSE protocol (default v1).

    ``final`` is the v2 final data of a live (temporary) run whose stored event is v1.
    """
    if protocol == 2:
        update: dict = {"version": "ai-events-v2"}
        if event.type == "final" and "messages" not in event.data:
            if final is None:
                raise ValueError("v2 final requires its bubbles")
            update["data"] = final
        return event.model_copy(update=update)
    if event.type == "final" and "messages" in event.data:
        messages = event.data["messages"]
        joined = {
            "text": "\n\n".join(message["text"] for message in messages),
            "cards": [card for message in messages for card in message["cards"]],
        }
        return event.model_copy(update={"data": joined})
    return event


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
