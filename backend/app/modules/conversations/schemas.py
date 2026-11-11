"""Public REST representations; SDK checkpoints remain internal."""

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from safevoice_shared.contracts.base import FrozenDTO
from safevoice_shared.contracts.conversations import RunStatus, RunUsage


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
        "description": "SafeVoice v1 SSE events; each data field contains a StreamEvent JSON object.",
        "content": {"text/event-stream": {"schema": {"type": "string"}}},
    }
}


class ApprovalRead(FrozenDTO):
    """A decision the user still has to make; the preview is the server-stored content."""

    id: UUID
    run_id: UUID
    tool: str
    tool_call_id: str
    preview: dict[str, Any]
    expires_at: datetime
    status: Literal["pending", "approved", "rejected", "expired"]


class MessageAttachmentsRead(FrozenDTO):
    message_id: UUID
    evidence_ids: list[UUID]
