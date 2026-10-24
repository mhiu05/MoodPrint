from datetime import date, datetime, timedelta
from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field, model_validator

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


class ConversationInput(DTO):
    bot_id: BotId


class ConversationHeader(DTO):
    conversation_id: UUID
    bot_id: BotId
    version: int
    expires_at: datetime


class AIMessage(DTO):
    id: UUID
    actor: Literal["self", "bot"]
    text: str
    cards: list[Card] = Field(default_factory=list, max_length=3)


class ConversationView(ConversationHeader):
    messages: list[AIMessage]
    active_run_id: UUID | None
    active_run_version: int | None = None


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
