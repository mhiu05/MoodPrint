"""Opted-in transcripts and content-free cross-worker delivery coordination."""

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
)
from sqlalchemy import text as sql_text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.models import AiRun, Base, User, now


class AiPreference(Base):
    __tablename__ = "ai_preferences"
    user_id: Mapped[UUID] = mapped_column(ForeignKey(User.id, ondelete="CASCADE"), primary_key=True)
    history_enabled: Mapped[bool] = mapped_column(default=False)
    semantic_memory_enabled: Mapped[bool] = mapped_column(default=False)
    version: Mapped[int] = mapped_column(default=1)
    policy_version: Mapped[str] = mapped_column(String(32), default="ai-data-v1")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class AiConversation(Base):
    __tablename__ = "ai_conversations"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey(User.id, ondelete="CASCADE"))
    bot_id: Mapped[str] = mapped_column(String(16))
    title: Mapped[str] = mapped_column(String(100), default="Cuộc trò chuyện mới")
    version: Mapped[int] = mapped_column(default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        Index("ix_ai_conversations_owner_activity", "user_id", "updated_at", "id"),
        Index("ix_ai_conversations_expiry", "expires_at"),
        CheckConstraint("bot_id in ('may','guong','nhip','rure','caunoi')", name="bot"),
        CheckConstraint("version >= 1", name="version"),
    )


class AiMessageRecord(Base):
    __tablename__ = "ai_messages"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    conversation_id: Mapped[UUID] = mapped_column(ForeignKey(AiConversation.id, ondelete="CASCADE"))
    sequence: Mapped[int]
    actor: Mapped[str] = mapped_column(String(8))
    text: Mapped[str] = mapped_column(String(6000))
    cards: Mapped[list] = mapped_column(JSONB, default=list)
    run_id: Mapped[UUID] = mapped_column(ForeignKey(AiRun.id, ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    # One row per bubble of a run; legacy rows are part 0 of 1 (server defaults).
    part_index: Mapped[int] = mapped_column(SmallInteger, default=0, server_default=sql_text("0"))
    part_count: Mapped[int] = mapped_column(SmallInteger, default=1, server_default=sql_text("1"))
    __table_args__ = (
        UniqueConstraint("conversation_id", "sequence"),
        # Explicit name: the convention would reuse uq_ai_messages_run_id.
        UniqueConstraint("run_id", "actor", "part_index", name="uq_ai_messages_run_part"),
        CheckConstraint("actor in ('self','bot')", name="actor"),
        CheckConstraint("sequence >= 1", name="sequence"),
        CheckConstraint(
            "part_index >= 0 and part_count between 1 and 4 and part_index < part_count", name="part"
        ),
        CheckConstraint("actor = 'bot' or (part_index = 0 and part_count = 1)", name="self_single"),
    )


class AiTurn(Base):
    __tablename__ = "ai_turns"
    run_id: Mapped[UUID] = mapped_column(ForeignKey(AiRun.id, ondelete="CASCADE"), primary_key=True)
    user_id: Mapped[UUID] = mapped_column(ForeignKey(User.id, ondelete="CASCADE"), index=True)
    scope_id: Mapped[UUID]
    conversation_id: Mapped[UUID | None] = mapped_column(
        ForeignKey(AiConversation.id, ondelete="CASCADE"), index=True
    )
    # NULL only for a server-originated (proactive) run, which never borrows a session.
    session_id: Mapped[UUID | None]
    client_message_id: Mapped[UUID]
    input_digest: Mapped[str] = mapped_column(String(64))
    data_version: Mapped[int]
    # NULL means legacy/unverified, never infer eligibility from saved text.
    context_policy: Mapped[str | None] = mapped_column(String(32))
    worker_id: Mapped[UUID]
    lease_until: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    origin: Mapped[str] = mapped_column(String(16), default="user", server_default=sql_text("'user'"))
    __table_args__ = (
        UniqueConstraint("scope_id", "client_message_id"),
        CheckConstraint("origin in ('user', 'proactive')", name="origin"),
        CheckConstraint("(origin = 'user') = (session_id is not null)", name="session"),
    )
