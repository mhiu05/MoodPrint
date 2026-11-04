"""Private, disposable journal derivatives; entry deletion is the shared erasure boundary."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    CHAR,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.ai.embedding_models import Vector
from app.infrastructure.database.models import Base, now


class JournalAiSettings(Base):
    __tablename__ = "journal_ai_settings"
    user_id: Mapped[UUID] = mapped_column(ForeignKey("moodprint.users.id", ondelete="CASCADE"), primary_key=True)
    embedding_enabled: Mapped[bool] = mapped_column(default=True, server_default=text("true"))
    auto_memory_enabled: Mapped[bool] = mapped_column(default=True, server_default=text("true"))
    notice_version: Mapped[str] = mapped_column(String(32), default="journal-ai-v1", server_default="journal-ai-v1")
    version: Mapped[int] = mapped_column(default=1, server_default="1")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, server_default=text("clock_timestamp()"))
    __table_args__ = (CheckConstraint("version >= 1", name="version"),)


class JournalEntryEmbedding(Base):
    __tablename__ = "journal_entry_embeddings"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    entry_id: Mapped[UUID] = mapped_column(ForeignKey("moodprint.journal_entries.id", ondelete="CASCADE"))
    user_id: Mapped[UUID] = mapped_column(ForeignKey("moodprint.users.id", ondelete="CASCADE"))
    entry_version: Mapped[int]
    settings_version: Mapped[int]
    content_sha256: Mapped[str] = mapped_column(CHAR(64))
    model: Mapped[str] = mapped_column(String(100))
    dimensions: Mapped[int]
    embedding: Mapped[list[float]] = mapped_column(Vector())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, server_default=text("clock_timestamp()"))
    __table_args__ = (
        UniqueConstraint("entry_id", "model", "dimensions", name="uq_journal_entry_embeddings_config"),
        Index("ix_journal_entry_embeddings_scope", "user_id", "model", "dimensions"),
        CheckConstraint("dimensions in (256,512,1024,2048) and extensions.vector_dims(embedding) = dimensions", name="dimensions"),
    )


class JournalAiJob(Base):
    __tablename__ = "journal_ai_jobs"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    entry_id: Mapped[UUID] = mapped_column(ForeignKey("moodprint.journal_entries.id", ondelete="CASCADE"))
    user_id: Mapped[UUID] = mapped_column(ForeignKey("moodprint.users.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(String(16))
    entry_version: Mapped[int]
    settings_version: Mapped[int]
    model: Mapped[str] = mapped_column(String(100))
    dimensions: Mapped[int | None]
    status: Mapped[str] = mapped_column(String(16), default="pending", server_default="pending")
    attempts: Mapped[int] = mapped_column(default=0, server_default="0")
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    lease_token: Mapped[UUID | None]
    last_error: Mapped[str | None] = mapped_column(String(48))
    run_id: Mapped[UUID | None] = mapped_column(ForeignKey("moodprint.ai_runs.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, server_default=text("clock_timestamp()"))
    __table_args__ = (
        UniqueConstraint("entry_id", "kind", "entry_version", "settings_version", "model", name="uq_journal_ai_jobs_snapshot"),
        Index("ix_journal_ai_jobs_due", "status", "available_at", "lease_until"),
        Index("ix_journal_ai_jobs_owner", "user_id", "kind", "created_at"),
        CheckConstraint("kind in ('embed','memories')", name="kind"),
        CheckConstraint("(dimensions is null) = (kind = 'memories')", name="dimensions"),
        CheckConstraint("status in ('pending','running','retry','succeeded','cancelled','failed','skipped')", name="status"),
        CheckConstraint("attempts between 0 and 8", name="attempts"),
    )
