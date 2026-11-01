"""Content-free receipts of V3 multi-agent work and group membership (migration 0024).

``ai_orchestration_steps`` is the auditable fact that a planner ran, a specialist was consulted
(``Agent.as_tool``), a handoff happened or a group member spoke. It stores no prompt, message,
journal text or model output: only closed values, digests and the child run that carries the
step's real usage. A user-visible collaboration line or speaker change rests on a row with
``status='completed'`` and ``used_in_reply``.
"""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    SmallInteger,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.ai.agents import V3_IDS, sql_in
from app.ai.models import AiConversation
from app.infrastructure.database.models import AiRun, Base, User, now

STEP_KINDS = ("plan", "consult", "handoff", "group_select", "group_reply")
STEP_STATUSES = ("authorized", "denied", "completed", "failed", "timeout", "cancelled", "discarded")
DENY_REASONS = (
    "edge_disabled", "journal_consent_off", "daily_cap", "budget", "time_budget", "capacity",
    "low_confidence", "not_member", "limit",
)
V3_IN = sql_in(V3_IDS)


class AiOrchestrationStep(Base):
    __tablename__ = "ai_orchestration_steps"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey(User.id, ondelete="CASCADE"))
    workflow_run_id: Mapped[UUID] = mapped_column(ForeignKey(AiRun.id, ondelete="CASCADE"))
    child_run_id: Mapped[UUID | None] = mapped_column(ForeignKey(AiRun.id, ondelete="SET NULL"))
    kind: Mapped[str] = mapped_column(String(16))
    requester_bot: Mapped[str] = mapped_column(String(16))
    target_bot: Mapped[str | None] = mapped_column(String(16))
    edge: Mapped[str | None] = mapped_column(String(48))
    ordinal: Mapped[int] = mapped_column(SmallInteger)
    status: Mapped[str] = mapped_column(String(16))
    deny_reason: Mapped[str | None] = mapped_column(String(32))
    failure_code: Mapped[str | None] = mapped_column(String(32))
    permission_version: Mapped[int] = mapped_column(default=0, server_default=text("0"))
    data_version: Mapped[int]
    # Closed values only (intent/workflow/task enums, counts); validated before every write.
    detail: Mapped[dict] = mapped_column(JSONB, default=dict, server_default=text("'{}'::jsonb"))
    input_digest: Mapped[str | None] = mapped_column(String(64))
    output_digest: Mapped[str | None] = mapped_column(String(64))
    used_in_reply: Mapped[bool] = mapped_column(default=False, server_default=text("false"))
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now, server_default=text("clock_timestamp()")
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        UniqueConstraint("workflow_run_id", "kind", "ordinal", name="uq_ai_orchestration_steps_ordinal"),
        CheckConstraint("kind in " + sql_in(STEP_KINDS), name="kind"),
        CheckConstraint("status in " + sql_in(STEP_STATUSES), name="status"),
        CheckConstraint("requester_bot in " + sql_in(V3_IDS + ("group",)), name="requester"),
        CheckConstraint(f"target_bot is null or target_bot in {V3_IN}", name="target"),
        CheckConstraint(
            "(kind in ('plan', 'group_select')) = (target_bot is null)", name="target_kind"
        ),
        CheckConstraint("(status = 'denied') = (deny_reason is not null)", name="deny"),
        CheckConstraint("deny_reason is null or deny_reason in " + sql_in(DENY_REASONS), name="deny_reason"),
        CheckConstraint(
            "failure_code is null or status in ('failed', 'timeout', 'cancelled', 'discarded')", name="failure"
        ),
        CheckConstraint("not used_in_reply or status = 'completed'", name="used"),
        CheckConstraint("status = 'denied' or child_run_id is not null or finished_at is not null", name="child"),
        CheckConstraint("ordinal between 0 and 15", name="ordinal"),
        CheckConstraint("jsonb_typeof(detail) = 'object'", name="detail"),
        CheckConstraint(
            "(input_digest is null or input_digest ~ '^[0-9a-f]{64}$') "
            "and (output_digest is null or output_digest ~ '^[0-9a-f]{64}$')",
            name="digest",
        ),
        Index("ix_ai_orchestration_steps_user_started", "user_id", "started_at"),
        Index("ix_ai_orchestration_steps_workflow", "workflow_run_id", "ordinal"),
    )


class AiGroupMember(Base):
    """One V3 agent's membership in a group conversation. Removal keeps the row (attribution)."""

    __tablename__ = "ai_group_members"
    conversation_id: Mapped[UUID] = mapped_column(
        ForeignKey(AiConversation.id, ondelete="CASCADE"), primary_key=True
    )
    bot_id: Mapped[str] = mapped_column(String(16), primary_key=True)
    user_id: Mapped[UUID] = mapped_column(ForeignKey(User.id, ondelete="CASCADE"))
    status: Mapped[str] = mapped_column(String(8), default="active", server_default=text("'active'"))
    # Default off: Nhật ký reads the journal in this group only after an explicit opt-in.
    journal_access: Mapped[bool] = mapped_column(default=False, server_default=text("false"))
    # The member sees group messages from this sequence on (0 = shared history).
    history_from_sequence: Mapped[int] = mapped_column(default=0, server_default=text("0"))
    version: Mapped[int] = mapped_column(default=1, server_default=text("1"))
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now, server_default=text("clock_timestamp()")
    )
    removed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        CheckConstraint(f"bot_id in {V3_IN}", name="bot"),
        CheckConstraint("status in ('active', 'removed')", name="status"),
        CheckConstraint("(status = 'removed') = (removed_at is not null)", name="removed"),
        CheckConstraint("journal_access = false or bot_id = 'nhatky'", name="journal"),
        CheckConstraint("history_from_sequence >= 0 and version >= 1", name="bounds"),
        Index("ix_ai_group_members_user_id", "user_id"),
    )
