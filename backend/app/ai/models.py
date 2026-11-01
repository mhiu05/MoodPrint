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

from app.ai.agents import ALL_IDS, V3_IDS, sql_in
from app.infrastructure.database.models import AiRun, Base, User, now

# A direct conversation belongs to one companion; a group (V3) carries the marker 'group'.
CONVERSATION_BOT_CHECK = (
    f"(kind = 'direct' and bot_id in {sql_in(ALL_IDS)}) or (kind = 'group' and bot_id = 'group')"
)
ACTIVE_AGENT_CHECK = f"active_agent is null or active_agent in {sql_in(V3_IDS)}"


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
    kind: Mapped[str] = mapped_column(String(8), default="direct", server_default=sql_text("'direct'"))
    # V3 handoff: the specialist that keeps answering this direct conversation, and the user
    # message sequence from which it may read the transcript. NULL = the conversation's bot.
    active_agent: Mapped[str | None] = mapped_column(String(16))
    active_agent_since: Mapped[int | None]
    version: Mapped[int] = mapped_column(default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        Index("ix_ai_conversations_owner_activity", "user_id", "updated_at", "id"),
        Index("ix_ai_conversations_expiry", "expires_at"),
        CheckConstraint(CONVERSATION_BOT_CHECK, name="bot"),
        CheckConstraint("kind in ('direct','group')", name="kind"),
        CheckConstraint(
            "(active_agent is null) = (active_agent_since is null) and (active_agent is null or kind = 'direct')",
            name="active_agent_pair",
        ),
        CheckConstraint(ACTIVE_AGENT_CHECK, name="active_agent"),
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
    # V3 group chat: companions a user message addressed (resolved, member-checked bot ids).
    mentions: Mapped[list] = mapped_column(JSONB, default=list, server_default=sql_text("'[]'::jsonb"))
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
        CheckConstraint(
            "jsonb_typeof(mentions) = 'array' and jsonb_array_length(mentions) <= 4 "
            "and (actor = 'self' or jsonb_array_length(mentions) = 0)",
            name="mentions",
        ),
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
