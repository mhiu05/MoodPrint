"""Approved memory and candidate mappings; no automatic schema creation."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import Computed, DateTime, Integer, Text, func, text
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class MemoryCandidate(Base):
    __tablename__ = "memory_candidates"
    __table_args__ = {"schema": "app"}
    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=text("gen_random_uuid()"))
    owner_id: Mapped[UUID]
    category: Mapped[str] = mapped_column(Text)
    content: Mapped[str] = mapped_column(Text)
    source_kind: Mapped[str] = mapped_column(Text)
    source_conversation_id: Mapped[UUID | None]
    source_message_id: Mapped[UUID | None]
    supersedes_memory_id: Mapped[UUID | None]
    approved_memory_id: Mapped[UUID | None]
    status: Mapped[str] = mapped_column(Text, server_default="pending")
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()+interval '30 days'")
    )
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class UserMemory(Base):
    __tablename__ = "user_memories"
    __table_args__ = {"schema": "app"}
    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=text("gen_random_uuid()"))
    owner_id: Mapped[UUID]
    category: Mapped[str] = mapped_column(Text)
    content: Mapped[str] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, server_default="active")
    supersedes_id: Mapped[UUID | None]
    source_kind: Mapped[str] = mapped_column(Text)
    source_candidate_id: Mapped[UUID | None]
    source_conversation_id: Mapped[UUID | None]
    last_retrieved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(Integer, server_default="1")
    search: Mapped[str | None] = mapped_column(
        TSVECTOR,
        Computed(
            "to_tsvector('simple'::regconfig,app_private.f_unaccent(content))", persisted=True
        ),
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
