"""Private, owner-scoped proactive configuration and content-free delivery metadata.

No table stores message content: delivered text lives in ``ai_messages`` with the
conversation lifecycle. Account deletion removes every table explicitly because the
``users`` row is tombstoned (FK cascades never run for registered accounts).
"""

from datetime import date, datetime, time
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    SmallInteger,
    String,
    Time,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.ai.models import AiConversation
from app.infrastructure.database.models import AiRun, Base, User, now

POLICY_VERSION = "proactive-v1"
from app.ai.agents import BOT_CHECK  # noqa: E402

SLOT_CHECK = "slot in ('morning','evening')"


class AiProactiveSettings(Base):
    __tablename__ = "ai_proactive_settings"
    user_id: Mapped[UUID] = mapped_column(ForeignKey(User.id, ondelete="CASCADE"), primary_key=True)
    timezone: Mapped[str] = mapped_column(String(64))
    quiet_start: Mapped[time] = mapped_column(Time, default=time(22, 0))
    quiet_end: Mapped[time] = mapped_column(Time, default=time(7, 0))
    badges_enabled: Mapped[bool] = mapped_column(default=True)
    # Opt-in, default off: Nhịp may read yesterday's saved entries only while enabled.
    journal_context_enabled: Mapped[bool] = mapped_column(default=False)
    journal_context_version: Mapped[int] = mapped_column(default=0)
    version: Mapped[int] = mapped_column(default=1)
    policy_version: Mapped[str] = mapped_column(String(32), default=POLICY_VERSION)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (
        CheckConstraint("version >= 1 and journal_context_version >= 0", name="version"),
        CheckConstraint("policy_version in ('proactive-v1')", name="policy"),
    )


class AiProactiveSchedule(Base):
    __tablename__ = "ai_proactive_schedules"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey(User.id, ondelete="CASCADE"))
    bot_id: Mapped[str] = mapped_column(String(16))
    slot: Mapped[str] = mapped_column(String(16))
    enabled: Mapped[bool] = mapped_column(default=False)
    local_time: Mapped[time] = mapped_column(Time)
    # Bit 0 = Monday … bit 6 = Sunday.
    weekdays: Mapped[int] = mapped_column(SmallInteger, default=127)
    paused_until: Mapped[date | None] = mapped_column(Date)
    auto_paused_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    next_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (
        UniqueConstraint("user_id", "bot_id", "slot"),
        CheckConstraint(BOT_CHECK, name="bot"),
        CheckConstraint(SLOT_CHECK, name="slot"),
        CheckConstraint(
            "(slot = 'morning' and local_time between '05:00' and '11:30') "
            "or (slot = 'evening' and local_time between '17:00' and '22:30')",
            name="window",
        ),
        CheckConstraint(
            "mod(extract(minute from local_time)::int, 15) = 0 and extract(second from local_time) = 0",
            name="step",
        ),
        CheckConstraint("weekdays between 1 and 127", name="weekdays"),
        CheckConstraint("version >= 1", name="version"),
        Index(
            "ix_ai_proactive_schedules_due",
            "next_due_at",
            postgresql_where="enabled and next_due_at is not null",
        ),
    )


JOB_STATES = ("pending", "running", "retry", "delivered", "skipped", "cancelled", "failed")


class AiProactiveJob(Base):
    __tablename__ = "ai_proactive_jobs"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey(User.id, ondelete="CASCADE"))
    schedule_id: Mapped[UUID | None] = mapped_column(
        ForeignKey(AiProactiveSchedule.id, ondelete="SET NULL")
    )
    bot_id: Mapped[str] = mapped_column(String(16))
    slot: Mapped[str] = mapped_column(String(16))
    local_date: Mapped[date] = mapped_column(Date)
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(16), default="pending")
    skip_reason: Mapped[str | None] = mapped_column(String(32))
    attempts: Mapped[int] = mapped_column(SmallInteger, default=0)
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    lease_token: Mapped[UUID | None]
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    worker_id: Mapped[UUID | None]
    schedule_version: Mapped[int]
    settings_version: Mapped[int]
    run_id: Mapped[UUID | None] = mapped_column(ForeignKey(AiRun.id, ondelete="SET NULL"), index=True)
    conversation_id: Mapped[UUID | None] = mapped_column(
        ForeignKey(AiConversation.id, ondelete="SET NULL")
    )
    # Rủ Rê only: closed enum, content-free, for avoiding repeated challenge kinds.
    challenge_kind: Mapped[str | None] = mapped_column(String(24))
    last_error: Mapped[str | None] = mapped_column(String(48))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        # One job per companion, slot and local day, even across schedule delete/recreate.
        UniqueConstraint("user_id", "bot_id", "slot", "local_date"),
        CheckConstraint("status in " + str(JOB_STATES).replace('"', "'"), name="status"),
        CheckConstraint("attempts between 0 and 5", name="attempts"),
        CheckConstraint("expires_at > due_at", name="window"),
        CheckConstraint("(status = 'skipped') = (skip_reason is not null)", name="skip"),
        CheckConstraint("status <> 'delivered' or run_id is not null", name="delivery"),
        CheckConstraint(
            "status <> 'running' or (lease_token is not null and lease_until is not null)", name="lease"
        ),
        Index(
            "ix_ai_proactive_jobs_due",
            "status",
            "available_at",
            postgresql_where="status in ('pending','retry','running')",
        ),
        Index("ix_ai_proactive_jobs_owner", "user_id", "local_date"),
    )


class AiConversationRead(Base):
    __tablename__ = "ai_conversation_reads"
    conversation_id: Mapped[UUID] = mapped_column(
        ForeignKey(AiConversation.id, ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[UUID] = mapped_column(ForeignKey(User.id, ondelete="CASCADE"), index=True)
    last_read_sequence: Mapped[int] = mapped_column(default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (CheckConstraint("last_read_sequence >= 0", name="sequence"),)


class AiMessageSource(Base):
    """Content-free provenance: which entry revision a proactive message was derived from."""

    __tablename__ = "ai_message_sources"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    run_id: Mapped[UUID] = mapped_column(ForeignKey(AiRun.id, ondelete="CASCADE"))
    user_id: Mapped[UUID] = mapped_column(ForeignKey(User.id, ondelete="CASCADE"))
    source_kind: Mapped[str] = mapped_column(String(24))
    # No FK: deleting the entry must make revalidation fail, not erase the provenance.
    source_id: Mapped[UUID]
    source_revision: Mapped[int]
    source_local_date: Mapped[date | None] = mapped_column(Date)
    policy: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (
        UniqueConstraint("run_id", "source_kind", "source_id"),
        CheckConstraint("source_kind in ('journal_entry')", name="kind"),
        CheckConstraint("source_revision >= 1", name="revision"),
        Index("ix_ai_message_sources_user_id", "user_id", "source_id"),
    )
