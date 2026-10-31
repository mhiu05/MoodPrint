"""Public DTOs of AI groups (06 §3). A group is one user and 2–3 of the three V3 agents."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field, field_validator

from app.ai.schemas import AIMessage
from app.contracts import DTO, MessageText

AgentId = Literal["dieuphoi", "nhatky", "hoatdong"]


def _visible(value: str) -> str:
    value = " ".join(value.split())
    if not value:
        raise ValueError("name must contain visible text")
    return value


class GroupMemberView(DTO):
    bot_id: AgentId
    status: Literal["active", "removed"]
    journal_access: bool
    shares_history: bool
    joined_at: datetime


class GroupHeader(DTO):
    group_id: UUID
    name: str
    members: list[GroupMemberView]
    version: int
    created_at: datetime
    updated_at: datetime
    expires_at: datetime
    unread: int = 0


class GroupView(GroupHeader):
    messages: list[AIMessage]
    active_turn_id: UUID | None = None
    has_more_messages: bool = False


class GroupCreate(DTO):
    name: str = Field(min_length=1, max_length=60)
    members: list[AgentId] = Field(min_length=2, max_length=3)

    @field_validator("name")
    @classmethod
    def visible_name(cls, value: str) -> str:
        return _visible(value)

    @field_validator("members")
    @classmethod
    def unique(cls, value: list[str]) -> list[str]:
        if len(set(value)) != len(value):
            raise ValueError("duplicate member")
        return value


class GroupRename(DTO):
    name: str = Field(min_length=1, max_length=60)
    expected_version: int = Field(ge=1)

    @field_validator("name")
    @classmethod
    def visible_name(cls, value: str) -> str:
        return _visible(value)


class GroupMemberAdd(DTO):
    bot_id: AgentId
    # Default: the new member sees only messages from now on (06 §6).
    share_history: bool = False
    expected_version: int = Field(ge=1)


class GroupJournalAccess(DTO):
    enabled: bool
    expected_version: int = Field(ge=1)


class GroupMessageInput(DTO):
    text: MessageText
    client_message_id: UUID
    expected_version: int = Field(ge=1)
    # Stable ids chosen in the mention picker; text mentions are parsed by the server too.
    mentions: list[AgentId | Literal["all"]] = Field(default_factory=list, max_length=4)


class GroupTurnAccepted(DTO):
    turn_id: UUID
    group_id: UUID
    version: int
    events_url: str


class GroupReadInput(DTO):
    sequence: int = Field(ge=0)
