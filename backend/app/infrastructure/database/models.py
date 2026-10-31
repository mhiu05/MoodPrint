from datetime import UTC, date, datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    SmallInteger,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def now() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    metadata = MetaData(
        schema="moodprint",
        naming_convention={
            "ix": "ix_%(table_name)s_%(column_0_name)s",
            "uq": "uq_%(table_name)s_%(column_0_name)s",
            "ck": "ck_%(table_name)s_%(constraint_name)s",
            "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
            "pk": "pk_%(table_name)s",
        },
    )


class User(Base):
    __tablename__ = "users"
    id: Mapped[UUID] = mapped_column(PGUUID, primary_key=True, default=uuid4)
    auth_subject: Mapped[UUID] = mapped_column(PGUUID, unique=True)
    alias: Mapped[str] = mapped_column(String(40), default="Bạn")
    age_band: Mapped[str] = mapped_column(String(12), default="unknown")
    status: Mapped[str] = mapped_column(String(16), default="active")
    timezone: Mapped[str] = mapped_column(String(64), default="Asia/Bangkok")
    auth_version: Mapped[int] = mapped_column(default=1)
    data_version: Mapped[int] = mapped_column(default=1)
    profile_version: Mapped[int] = mapped_column(default=0)
    deletion_pending: Mapped[bool] = mapped_column(default=False, server_default="false")
    # Written with the sliding session refresh (at most every 15 minutes); NULL = unknown.
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Moderation outcomes (I-03): restricted users leave social features; suspended
    # users cannot sign in or use any session until the time passes or staff lift it.
    social_restricted_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    suspended_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Server-owned lifecycle (guest trial). Existing rows are registered; kind and the 7200s
    # deadline are immutable (database trigger), so no later request can renew or promote them.
    account_kind: Mapped[str] = mapped_column(
        String(10), default="registered", server_default="registered"
    )
    guest_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    guest_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        CheckConstraint("age_band in ('unknown','under16','teen','adult')", name="age_band"),
        CheckConstraint("account_kind in ('registered','guest')", name="account_kind"),
        CheckConstraint(
            "(account_kind = 'registered' AND guest_started_at IS NULL AND guest_expires_at IS NULL)"
            " OR (account_kind = 'guest' AND guest_started_at IS NOT NULL"
            " AND guest_expires_at IS NOT NULL"
            " AND guest_expires_at = guest_started_at + interval '7200 seconds')",
            name="guest_lifetime",
        ),
        Index(
            "ix_users_guest_expires_at",
            "guest_expires_at",
            postgresql_where=text("account_kind = 'guest'"),
        ),
    )


class AuthSession(Base):
    __tablename__ = "auth_sessions"
    id: Mapped[UUID] = mapped_column(PGUUID, primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey(User.id), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    csrf_hash: Mapped[str] = mapped_column(String(64))
    provider_session_id: Mapped[UUID] = mapped_column(PGUUID)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    revoked: Mapped[bool] = mapped_column(default=False)
    auth_version: Mapped[int] = mapped_column(default=1)
    reauthenticated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now, server_default="1970-01-01 00:00:00+00"
    )
    # Database clock at insert; a guest session is additionally capped at users.guest_expires_at.
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("clock_timestamp()")
    )


class AgeDeclaration(Base):
    __tablename__ = "age_declarations"
    user_id: Mapped[UUID] = mapped_column(ForeignKey(User.id), primary_key=True)
    birth_year: Mapped[int] = mapped_column(SmallInteger)
    version: Mapped[int] = mapped_column(default=1)
    policy_version: Mapped[str] = mapped_column(String(32))
    declared_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    adult_confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        CheckConstraint("birth_year between 1900 and 9999", name="birth_year_range"),
        CheckConstraint("version >= 1", name="age_declaration_version"),
    )


class Consent(Base):
    __tablename__ = "consents"
    user_id: Mapped[UUID] = mapped_column(ForeignKey(User.id), primary_key=True)
    purpose: Mapped[str] = mapped_column(String(8), primary_key=True)
    enabled: Mapped[bool] = mapped_column(default=False)
    version: Mapped[int] = mapped_column(default=1)
    policy_version: Mapped[str] = mapped_column(String(32), default="v1")
    __table_args__ = (CheckConstraint("purpose in ('AI','MEM','MATCH','VOICE')", name="purpose"),)


class ConsentEvent(Base):
    __tablename__ = "consent_events"
    id: Mapped[UUID] = mapped_column(PGUUID, primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey(User.id), index=True)
    purpose: Mapped[str] = mapped_column(String(8))
    enabled: Mapped[bool]
    version: Mapped[int]
    policy_version: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Mood(Base):
    __tablename__ = "moods"
    id: Mapped[UUID] = mapped_column(PGUUID, primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey(User.id))
    local_date: Mapped[date] = mapped_column(Date)
    value: Mapped[int] = mapped_column(Integer)
    note: Mapped[str] = mapped_column(String(120), default="")
    timezone: Mapped[str] = mapped_column(String(64))
    version: Mapped[int] = mapped_column(default=1)
    __table_args__ = (
        UniqueConstraint("user_id", "local_date"),
        CheckConstraint("value between 1 and 5", name="value"),
    )


class Memory(Base):
    __tablename__ = "memories"
    id: Mapped[UUID] = mapped_column(PGUUID, primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey(User.id))
    bot_id: Mapped[str] = mapped_column(String(16))
    text: Mapped[str] = mapped_column(String(120))
    version: Mapped[int] = mapped_column(default=1)
    status: Mapped[str] = mapped_column(String(16), default="active")
    proposal_id: Mapped[UUID] = mapped_column(PGUUID, unique=True)
    __table_args__ = (Index("ix_memories_scope", "user_id", "bot_id", "status"),)


class Idempotency(Base):
    __tablename__ = "idempotency_keys"
    id: Mapped[UUID] = mapped_column(PGUUID, primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey(User.id))
    operation: Mapped[str] = mapped_column(String(120))
    key: Mapped[str] = mapped_column(String(128))
    digest: Mapped[str] = mapped_column(String(64))
    receipt: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (UniqueConstraint("user_id", "operation", "key"),)


class Outbox(Base):
    """Retired (DR-10): never written; retention drains old rows until a contract migration drops it."""

    __tablename__ = "outbox"
    id: Mapped[UUID] = mapped_column(PGUUID, primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey(User.id), index=True)
    kind: Mapped[str] = mapped_column(String(40))
    resource_id: Mapped[str] = mapped_column(String(64))
    version: Mapped[int]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    delivered: Mapped[bool] = mapped_column(default=False, index=True)


class AiRun(Base):
    __tablename__ = "ai_runs"
    id: Mapped[UUID] = mapped_column(PGUUID, primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey(User.id), index=True)
    conversation_id: Mapped[UUID] = mapped_column(PGUUID, index=True)
    bot_id: Mapped[str] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(16), default="running")
    version: Mapped[int] = mapped_column(default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (
        Index(
            "uq_ai_active_conversation",
            "conversation_id",
            unique=True,
            postgresql_where=(status == "running"),
        ),
    )


class AiUsage(Base):
    __tablename__ = "ai_usage"
    run_id: Mapped[UUID] = mapped_column(ForeignKey(AiRun.id, ondelete="CASCADE"), primary_key=True)
    user_id: Mapped[UUID] = mapped_column(ForeignKey(User.id), index=True)
    worker_id: Mapped[UUID] = mapped_column(PGUUID)
    model: Mapped[str] = mapped_column(String(100))
    prompt_version: Mapped[str] = mapped_column(String(60))
    pricing_version: Mapped[str] = mapped_column(String(60))
    input_nano_rate: Mapped[int | None] = mapped_column(BigInteger)
    cached_nano_rate: Mapped[int | None] = mapped_column(BigInteger)
    output_nano_rate: Mapped[int | None] = mapped_column(BigInteger)
    estimated_nano_usd: Mapped[int | None] = mapped_column(BigInteger)
    state: Mapped[str] = mapped_column(String(16), default="open")
    sequence: Mapped[int] = mapped_column(Integer, default=0)
    requests_started: Mapped[int] = mapped_column(Integer, default=0)
    responses_received: Mapped[int] = mapped_column(Integer, default=0)
    input_tokens: Mapped[int] = mapped_column(BigInteger, default=0)
    cached_input_tokens: Mapped[int] = mapped_column(BigInteger, default=0)
    output_tokens: Mapped[int] = mapped_column(BigInteger, default=0)
    tool_calls: Mapped[int] = mapped_column(Integer, default=0)
    lease_until: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (
        CheckConstraint("state in ('open','settled','uncertain')", name="state"),
        CheckConstraint("sequence >= 0 and requests_started >= responses_received and responses_received >= 0 and requests_started <= 3 and tool_calls between 0 and 2", name="counts"),
        CheckConstraint("input_tokens >= cached_input_tokens and cached_input_tokens >= 0 and output_tokens >= 0", name="tokens"),
        CheckConstraint("estimated_nano_usd is null or estimated_nano_usd >= 0", name="cost"),
    )
