"""Opted-in transcripts and content-free cross-worker delivery coordination."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, UniqueConstraint
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
    __table_args__ = (
        UniqueConstraint("conversation_id", "sequence"),
        UniqueConstraint("run_id", "actor"),
        CheckConstraint("actor in ('self','bot')", name="actor"),
        CheckConstraint("sequence >= 1", name="sequence"),
    )


class AiTurn(Base):
    __tablename__ = "ai_turns"
    run_id: Mapped[UUID] = mapped_column(ForeignKey(AiRun.id, ondelete="CASCADE"), primary_key=True)
    user_id: Mapped[UUID] = mapped_column(ForeignKey(User.id, ondelete="CASCADE"), index=True)
    scope_id: Mapped[UUID]
    conversation_id: Mapped[UUID | None] = mapped_column(
        ForeignKey(AiConversation.id, ondelete="CASCADE"), index=True
    )
    session_id: Mapped[UUID]
    client_message_id: Mapped[UUID]
    input_digest: Mapped[str] = mapped_column(String(64))
    data_version: Mapped[int]
    worker_id: Mapped[UUID]
    lease_until: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    __table_args__ = (UniqueConstraint("scope_id", "client_message_id"),)
