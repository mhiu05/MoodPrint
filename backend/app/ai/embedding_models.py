"""Derived vectors and content-free retry coordination; no transcript/mood indexing."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.dialects.postgresql.base import ischema_names
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import UserDefinedType

from app.infrastructure.database.models import Base, Memory, User, now


class Vector(UserDefinedType[list[float]]):
    cache_ok = True

    def get_col_spec(self, **kw) -> str:
        return "extensions.vector"

    def bind_processor(self, dialect):
        def process(value):
            return None if value is None else "[" + ",".join(str(float(v)) for v in value) + "]"

        return process

    def result_processor(self, dialect, coltype):
        def process(value):
            if value is None or isinstance(value, list):
                return value
            return [float(v) for v in value.strip("[]").split(",")]

        return process


# Match PostgreSQL reflection both with and without schema qualification. This
# keeps Alembic's drift check meaningful without adding the pgvector Python SDK.
ischema_names["vector"] = Vector
ischema_names["extensions.vector"] = Vector


class EmbeddingJob(Base):
    __tablename__ = "memory_embedding_jobs"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    memory_id: Mapped[UUID] = mapped_column(ForeignKey(Memory.id, ondelete="CASCADE"))
    user_id: Mapped[UUID] = mapped_column(ForeignKey(User.id, ondelete="CASCADE"))
    bot_id: Mapped[str] = mapped_column(String(16))
    memory_version: Mapped[int]
    data_version: Mapped[int]
    preference_version: Mapped[int]
    ai_consent_version: Mapped[int]
    mem_consent_version: Mapped[int]
    model: Mapped[str] = mapped_column(String(100))
    dimensions: Mapped[int]
    status: Mapped[str] = mapped_column(String(16), default="pending")
    attempts: Mapped[int] = mapped_column(default=0)
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    lease_token: Mapped[UUID | None]
    last_error: Mapped[str | None] = mapped_column(String(48))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (
        UniqueConstraint(
            "memory_id",
            "memory_version",
            "preference_version",
            "ai_consent_version",
            "mem_consent_version",
            "model",
            "dimensions",
            name="uq_memory_embedding_jobs_snapshot",
        ),
        Index("ix_memory_embedding_jobs_due", "status", "available_at", "lease_until"),
        Index("ix_memory_embedding_jobs_owner", "user_id", "memory_id"),
        CheckConstraint(
            "status in ('pending','running','retry','succeeded','cancelled','failed')",
            name="status",
        ),
        CheckConstraint("attempts between 0 and 8", name="attempts"),
        CheckConstraint("dimensions in (256,512,1024,2048)", name="dimensions"),
        CheckConstraint("bot_id in ('may','guong','nhip','rure')", name="bot"),
    )


class MemoryEmbedding(Base):
    __tablename__ = "memory_embeddings"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    memory_id: Mapped[UUID] = mapped_column(ForeignKey(Memory.id, ondelete="CASCADE"))
    user_id: Mapped[UUID] = mapped_column(ForeignKey(User.id, ondelete="CASCADE"))
    bot_id: Mapped[str] = mapped_column(String(16))
    memory_version: Mapped[int]
    data_version: Mapped[int]
    preference_version: Mapped[int]
    ai_consent_version: Mapped[int]
    mem_consent_version: Mapped[int]
    model: Mapped[str] = mapped_column(String(100))
    dimensions: Mapped[int]
    embedding: Mapped[list[float]] = mapped_column(Vector())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (
        UniqueConstraint("memory_id", "model", "dimensions", name="uq_memory_embeddings_config"),
        Index("ix_memory_embeddings_scope", "user_id", "bot_id", "model", "dimensions"),
        CheckConstraint(
            "dimensions in (256,512,1024,2048) and extensions.vector_dims(embedding) = dimensions",
            name="dimensions",
        ),
        CheckConstraint("bot_id in ('may','guong','nhip','rure')", name="bot"),
    )
