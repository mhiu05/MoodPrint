from datetime import datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import Field, JsonValue, TypeAdapter

from .agent import CompanionTurn
from .base import FrozenDTO
from .conversations import RunUsage
from .knowledge import SourceCitation

RunErrorCode = Literal[
    "model_timeout",
    "model_refusal",
    "max_turns",
    "tool_budget_exceeded",
    "run_timeout",
    "upstream_error",
    "internal_error",
]


class RunStartedData(FrozenDTO):
    run_id: UUID
    conversation_id: UUID
    message_id: UUID


class MessageDeltaData(FrozenDTO):
    message_id: UUID
    text: str


class MessageCompletedData(FrozenDTO):
    message_id: UUID
    content: str
    citations: list[SourceCitation] = Field(default_factory=list[SourceCitation])
    structured: CompanionTurn | None = None


class ToolStartedData(FrozenDTO):
    call_id: str
    tool: str
    label: str


class ToolCompletedData(FrozenDTO):
    call_id: str
    tool: str
    ok: bool


class ApprovalRequiredData(FrozenDTO):
    approval_id: UUID
    tool: str
    label: str
    preview: dict[str, JsonValue]
    expires_at: datetime


class RunCompletedData(FrozenDTO):
    status: Literal["completed", "awaiting_approval", "cancelled"]


class RunFailedData(FrozenDTO):
    code: RunErrorCode
    message: str
    retryable: bool


class HeartbeatData(FrozenDTO):
    pass


class EventBase(FrozenDTO):
    v: Literal[1] = 1
    seq: int = Field(ge=1)
    run_id: UUID


class RunStarted(EventBase):
    event: Literal["run.started"] = "run.started"
    data: RunStartedData


class MessageDelta(EventBase):
    event: Literal["message.delta"] = "message.delta"
    data: MessageDeltaData


class MessageCompleted(EventBase):
    event: Literal["message.completed"] = "message.completed"
    data: MessageCompletedData


class ToolStarted(EventBase):
    event: Literal["tool.started"] = "tool.started"
    data: ToolStartedData


class ToolCompleted(EventBase):
    event: Literal["tool.completed"] = "tool.completed"
    data: ToolCompletedData


class ApprovalRequired(EventBase):
    event: Literal["approval.required"] = "approval.required"
    data: ApprovalRequiredData


class RunUsageEvent(EventBase):
    event: Literal["run.usage"] = "run.usage"
    data: RunUsage


class RunCompleted(EventBase):
    event: Literal["run.completed"] = "run.completed"
    data: RunCompletedData


class RunFailed(EventBase):
    event: Literal["run.failed"] = "run.failed"
    data: RunFailedData


class Heartbeat(EventBase):
    event: Literal["heartbeat"] = "heartbeat"
    data: HeartbeatData = Field(default_factory=HeartbeatData)


StreamEvent = Annotated[
    RunStarted
    | MessageDelta
    | MessageCompleted
    | ToolStarted
    | ToolCompleted
    | ApprovalRequired
    | RunUsageEvent
    | RunCompleted
    | RunFailed
    | Heartbeat,
    Field(discriminator="event"),
]
STREAM_EVENT_ADAPTER: TypeAdapter[StreamEvent] = TypeAdapter(StreamEvent)


def make_event(event: str, *, seq: int, run_id: UUID, data: dict[str, Any]) -> StreamEvent:
    return STREAM_EVENT_ADAPTER.validate_python(
        {"event": event, "seq": seq, "run_id": run_id, "data": data}
    )
