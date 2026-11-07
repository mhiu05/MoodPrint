"""Public REST representations; SDK checkpoints remain internal."""

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from moodprint_shared.contracts.base import FrozenDTO
from moodprint_shared.contracts.conversations import RunStatus, RunUsage


class ConversationRead(FrozenDTO):
    id: UUID
    owner_id: UUID
    title: str
    linked_case_id: UUID | None
    source_article_id: str | None
    summary: str | None
    status: Literal["active", "archived"]
    last_message_at: datetime | None
    created_at: datetime
    updated_at: datetime


class RunRead(FrozenDTO):
    id: UUID
    conversation_id: UUID
    status: RunStatus
    model: str
    prompt_version: str
    tools_version: str
    error_code: str | None
    usage: RunUsage


class RunCancelRead(FrozenDTO):
    status: RunStatus


SSE_RESPONSES: dict[int | str, dict[str, Any]] = {
    200: {
        "description": "MoodPrint v1 SSE events; each data field contains a StreamEvent JSON object.",
        "content": {"text/event-stream": {"schema": {"type": "string"}}},
    }
}
