from datetime import datetime
from typing import Any, Literal, Protocol
from uuid import UUID

from pydantic import Field

from .agent import CompanionTurn
from .auth import AuthContext
from .base import FrozenDTO
from .knowledge import SourceCitation

SessionItem = Any
RunStatus = Literal[
    "running", "awaiting_approval", "completed", "failed", "cancelled", "interrupted"
]


class AgentSession(Protocol):
    async def get_items(self, limit: int | None = None) -> list[SessionItem]: ...
    async def add_items(self, items: list[SessionItem]) -> None: ...
    async def pop_item(self) -> SessionItem | None: ...
    async def clear_session(self) -> None: ...


class ChatMessage(FrozenDTO):
    id: UUID
    conversation_id: UUID
    role: Literal["user", "assistant", "system"]
    content: str
    citations: list[SourceCitation] = Field(default_factory=list[SourceCitation])
    client_message_id: UUID | None = None
    run_id: UUID | None = None
    created_at: datetime


class TurnHandle(FrozenDTO):
    run_id: UUID
    conversation_id: UUID
    message_id: UUID
    client_message_id: UUID
    replay: bool = False
    existing_result: "TurnResult | None" = None


class RunUsage(FrozenDTO):
    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    total_tokens: int = Field(default=0, ge=0)
    requests: int = Field(default=0, ge=0)
    tool_calls: int = Field(default=0, ge=0)
    latency_ms: int = Field(default=0, ge=0)


class TurnResult(FrozenDTO):
    status: RunStatus
    content: str = ""
    citations: list[SourceCitation] = Field(default_factory=list[SourceCitation])
    structured: CompanionTurn | None = None
    usage: RunUsage = Field(default_factory=RunUsage)
    error_code: str | None = None
    message_id: UUID | None = None


class ConversationService(Protocol):
    async def begin_turn(
        self, auth: AuthContext, conversation_id: UUID, client_message_id: UUID, content: str
    ) -> TurnHandle: ...
    async def finish_turn(
        self, auth: AuthContext, turn: TurnHandle, result: TurnResult
    ) -> None: ...
    async def open_session(self, auth: AuthContext, conversation_id: UUID) -> AgentSession: ...
    async def recent_messages(
        self, auth: AuthContext, conversation_id: UUID, limit: int
    ) -> list[ChatMessage]: ...
