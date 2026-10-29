from datetime import date, datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    SmallInteger,
    String,
    Text,
)
from sqlalchemy import text as sql_text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.models import Base, User, now


class JournalEntry(Base):
    __tablename__ = "journal_entries"
    id: Mapped[UUID] = mapped_column(PGUUID, primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey(User.id))
    local_date: Mapped[date] = mapped_column(Date)
    timezone: Mapped[str] = mapped_column(String(64))
    mood: Mapped[int] = mapped_column(SmallInteger)
    text: Mapped[str] = mapped_column(Text, default="", server_default="")
    emotions: Mapped[list[str]] = mapped_column(
        JSONB, default=list, server_default=sql_text("'[]'::jsonb")
    )
    factors: Mapped[list[str]] = mapped_column(
        JSONB, default=list, server_default=sql_text("'[]'::jsonb")
    )
    status: Mapped[str] = mapped_column(String(8), default="saved", server_default="saved")
    version: Mapped[int] = mapped_column(default=1, server_default="1")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now, server_default=sql_text("clock_timestamp()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now, server_default=sql_text("clock_timestamp()")
    )
    __table_args__ = (
        CheckConstraint("mood between 1 and 5", name="mood"),
        CheckConstraint("char_length(text) <= 10000", name="text_length"),
        CheckConstraint(
            "jsonb_typeof(emotions) = 'array' AND jsonb_array_length(emotions) <= 12",
            name="emotions",
        ),
        CheckConstraint(
            "jsonb_typeof(factors) = 'array' AND jsonb_array_length(factors) <= 12", name="factors"
        ),
        CheckConstraint("status in ('draft','saved')", name="status"),
        CheckConstraint("version >= 1", name="version"),
        Index("ix_journal_entries_owner_date", "user_id", "local_date", "created_at", "id"),
        Index("ix_journal_entries_owner_status_updated", "user_id", "status", "updated_at"),
    )


class JournalMedia(Base):
    __tablename__ = "journal_media"
    id: Mapped[UUID] = mapped_column(PGUUID, primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey(User.id), index=True)
    entry_id: Mapped[UUID] = mapped_column(
        ForeignKey(JournalEntry.id, ondelete="CASCADE"), index=True
    )
    type: Mapped[str] = mapped_column(String(8))
    object_path: Mapped[str] = mapped_column(String(512), unique=True)
    mime_type: Mapped[str] = mapped_column(String(127))
    size_bytes: Mapped[int] = mapped_column(BigInteger)
    duration_seconds: Mapped[float | None] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(8), default="pending", server_default="pending")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now, server_default=sql_text("clock_timestamp()")
    )
    __table_args__ = (
        CheckConstraint("type in ('image','audio','video')", name="type"),
        CheckConstraint("size_bytes > 0", name="size"),
        CheckConstraint("duration_seconds is null or duration_seconds >= 0", name="duration"),
        CheckConstraint("status in ('pending','ready')", name="status"),
        Index("ix_journal_media_status_created", "status", "created_at"),
    )


class JournalStorageDeletion(Base):
    """Durable cleanup survives account erasure; it deliberately has no user FK."""

    __tablename__ = "journal_storage_deletions"
    id: Mapped[UUID] = mapped_column(PGUUID, primary_key=True, default=uuid4)
    object_path: Mapped[str] = mapped_column(String(512), unique=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now, server_default=sql_text("clock_timestamp()")
    )
    attempts: Mapped[int] = mapped_column(default=0, server_default="0")
    __table_args__ = (CheckConstraint("attempts >= 0", name="attempts"),)
