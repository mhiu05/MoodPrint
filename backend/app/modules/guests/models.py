"""Temporary-trial lifecycle, admission and detached financial tables (private schema).

Guest identity, cleanup coordination and per-trial counters belong to a user and are purged with it.
Budget days and cost reservations deliberately carry no user, run, provider or network identifier,
so purging every guest can never reopen a spent daily budget.
"""

from datetime import date, datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    CHAR,
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    PrimaryKeyConstraint,
    String,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.models import Base, User

# Database time is the authority for every guest deadline, lease and window.
DB_NOW = text("clock_timestamp()")

ATTEMPT_STATES = (
    "intent",
    "signup_started",
    "granted",
    "ambiguous",
    "orphan_pending",
    "resolved",
    "rejected",
    "incident_required",
)
CLEANUP_STATES = ("pending", "running", "retry", "incident_required")
ABUSE_SCOPES = (
    "intent",
    "intent_global",
    "creation_hour",
    "creation_day",
    "failed_signup",
    "feedback",
    "feedback_attempt",
    "ai_minute",
    "voice_minute",
)
RESERVATION_KINDS = ("ai", "voice", "embed")
RESERVATION_STATES = ("reserved", "dispatched", "settled", "uncertain", "cancelled")
LINK_STATES = ("claimed", "dispatched", "completed", "interrupted")


def _in(column: str, values: tuple[str, ...]) -> str:
    return f"{column} in ({','.join(repr(value) for value in values)})"


class GuestProvisioningAttempt(Base):
    """One browser-owned creation attempt. Holds hashes and a random correlation, never tokens."""

    __tablename__ = "guest_provisioning_attempts"
    id: Mapped[UUID] = mapped_column(PGUUID, primary_key=True, default=uuid4)
    intent_hash: Mapped[str] = mapped_column(CHAR(64), unique=True)
    idempotency_hash: Mapped[str | None] = mapped_column(CHAR(64))
    payload_digest: Mapped[str | None] = mapped_column(CHAR(64))
    provider_correlation: Mapped[str] = mapped_column(CHAR(64), unique=True)
    provider_subject: Mapped[UUID | None] = mapped_column(PGUUID)
    provider_session_id: Mapped[UUID | None] = mapped_column(PGUUID)
    user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey(User.id, ondelete="SET NULL"), unique=True
    )
    state: Mapped[str] = mapped_column(String(24), default="intent", server_default="intent")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=DB_NOW)
    intent_expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("clock_timestamp() + interval '600 seconds'")
    )
    signup_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reconcile_until: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("clock_timestamp() + interval '600 seconds'")
    )
    lease_token: Mapped[UUID | None] = mapped_column(PGUUID)
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    attempts: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    next_attempt_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=DB_NOW
    )
    last_error: Mapped[str | None] = mapped_column(String(40))
    __table_args__ = (
        CheckConstraint(_in("state", ATTEMPT_STATES), name="state"),
        CheckConstraint("(lease_token IS NULL) = (lease_until IS NULL)", name="lease_pair"),
        CheckConstraint("attempts >= 0", name="attempts"),
        CheckConstraint(
            "signup_started_at IS NULL"
            " OR reconcile_until >= signup_started_at + interval '24 hours'",
            name="reconcile_window",
        ),
        Index("ix_guest_provisioning_attempts_state_next", "state", "next_attempt_at"),
    )


class GuestCleanupJob(Base):
    """Durable purge coordination; created at grant so cleanup never waits for a late request."""

    __tablename__ = "guest_cleanup_jobs"
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey(User.id, ondelete="CASCADE"), primary_key=True
    )
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    state: Mapped[str] = mapped_column(String(20), default="pending", server_default="pending")
    attempts: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    next_attempt_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=DB_NOW
    )
    lease_token: Mapped[UUID | None] = mapped_column(PGUUID)
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(String(40))
    alerted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        CheckConstraint(_in("state", CLEANUP_STATES), name="state"),
        CheckConstraint("(lease_token IS NULL) = (lease_until IS NULL)", name="lease_pair"),
        CheckConstraint("attempts >= 0", name="attempts"),
        Index("ix_guest_cleanup_jobs_state_next", "state", "next_attempt_at"),
    )


class GuestUsage(Base):
    """Lifetime accepted counters for one trial; never per day and never refunded after dispatch."""

    __tablename__ = "guest_usage"
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey(User.id, ondelete="CASCADE"), primary_key=True
    )
    ai_turns: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    voice_clips: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    voice_milliseconds: Mapped[int] = mapped_column(BigInteger, default=0, server_default="0")
    semantic_memories: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    __table_args__ = (
        CheckConstraint("ai_turns >= 0", name="ai_turns"),
        CheckConstraint("voice_clips >= 0", name="voice_clips"),
        CheckConstraint("voice_milliseconds >= 0", name="voice_milliseconds"),
        CheckConstraint("semantic_memories >= 0", name="semantic_memories"),
    )


class GuestAbuseBucket(Base):
    """Rotating-HMAC security counters. The key is never a raw address or a user identifier."""

    __tablename__ = "guest_abuse_buckets"
    scope: Mapped[str] = mapped_column(String(24))
    key_hash: Mapped[str] = mapped_column(CHAR(64))
    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    reserved: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        PrimaryKeyConstraint("scope", "key_hash", "window_start", name="pk_guest_abuse_buckets"),
        CheckConstraint(_in("scope", ABUSE_SCOPES), name="scope"),
        CheckConstraint("count >= 0", name="count"),
        CheckConstraint("reserved >= 0", name="reserved"),
        Index("ix_guest_abuse_buckets_expires_at", "expires_at"),
    )


class GuestBudgetDay(Base):
    """Identifier-free daily liability (Asia/Bangkok civil day). Survives every guest purge."""

    __tablename__ = "guest_budget_days"
    day: Mapped[date] = mapped_column(Date, primary_key=True)
    limit_nano_usd: Mapped[int] = mapped_column(BigInteger)
    spent_nano_usd: Mapped[int] = mapped_column(BigInteger, default=0, server_default="0")
    reserved_nano_usd: Mapped[int] = mapped_column(BigInteger, default=0, server_default="0")
    halted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        CheckConstraint("limit_nano_usd > 0", name="limit"),
        CheckConstraint("spent_nano_usd >= 0", name="spent"),
        CheckConstraint("reserved_nano_usd >= 0", name="reserved"),
    )


class GuestCostReservation(Base):
    """Random accounting token for one paid dispatch; no user, run, provider or network link."""

    __tablename__ = "guest_cost_reservations"
    id: Mapped[UUID] = mapped_column(PGUUID, primary_key=True, default=uuid4)
    day: Mapped[date] = mapped_column(ForeignKey(GuestBudgetDay.day, ondelete="RESTRICT"))
    kind: Mapped[str] = mapped_column(String(8))
    upper_nano_usd: Mapped[int] = mapped_column(BigInteger)
    charged_nano_usd: Mapped[int] = mapped_column(BigInteger, default=0, server_default="0")
    state: Mapped[str] = mapped_column(String(16), default="reserved", server_default="reserved")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=DB_NOW)
    lease_until: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("clock_timestamp() + interval '60 seconds'")
    )
    dispatched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        CheckConstraint(_in("kind", RESERVATION_KINDS), name="kind"),
        CheckConstraint(_in("state", RESERVATION_STATES), name="state"),
        CheckConstraint("upper_nano_usd >= 0", name="upper"),
        CheckConstraint("charged_nano_usd >= 0", name="charged"),
        Index("ix_guest_cost_reservations_state_lease", "state", "lease_until"),
    )


class GuestOperationLink(Base):
    """Short-lived owner/replay/concurrency mapping for one admitted paid operation."""

    __tablename__ = "guest_operation_links"
    user_id: Mapped[UUID] = mapped_column(ForeignKey(User.id, ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(String(8))
    operation_key_hash: Mapped[str] = mapped_column(CHAR(64))
    payload_digest: Mapped[str] = mapped_column(CHAR(64))
    reservation_id: Mapped[UUID | None] = mapped_column(
        ForeignKey(GuestCostReservation.id, ondelete="RESTRICT"), unique=True
    )
    state: Mapped[str] = mapped_column(String(16), default="claimed", server_default="claimed")
    worker_id: Mapped[UUID] = mapped_column(PGUUID)
    lease_token: Mapped[UUID] = mapped_column(PGUUID)
    lease_until: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    # Per-minute admission counts links by creation time, so no identity-keyed bucket is needed.
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=DB_NOW)
    __table_args__ = (
        PrimaryKeyConstraint("user_id", "kind", "operation_key_hash", name="pk_guest_operation_links"),
        CheckConstraint(_in("kind", RESERVATION_KINDS), name="kind"),
        CheckConstraint(_in("state", LINK_STATES), name="state"),
        CheckConstraint("state <> 'dispatched' OR reservation_id IS NOT NULL", name="dispatched"),
        Index("ix_guest_operation_links_kind_state_lease", "kind", "state", "lease_until"),
    )


GUEST_TABLES = (
    GuestProvisioningAttempt,
    GuestCleanupJob,
    GuestUsage,
    GuestAbuseBucket,
    GuestBudgetDay,
    GuestCostReservation,
    GuestOperationLink,
)
