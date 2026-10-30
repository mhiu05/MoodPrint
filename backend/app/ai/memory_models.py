"""Authoritative user-approved proposal lifecycle; no model may approve a proposal."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.models import Base, User, now


class MemoryProposal(Base):
    __tablename__ = "memory_proposals"

    id: Mapped[UUID] = mapped_column(PGUUID, primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey(User.id))
    bot_id: Mapped[str] = mapped_column(String(16))
    text: Mapped[str] = mapped_column(String(120))
    data_version: Mapped[int]
    # Approval validity follows the consent grants, not unrelated data revisions.
    ai_consent_version: Mapped[int]
    mem_consent_version: Mapped[int]
    version: Mapped[int] = mapped_column(default=1)
    status: Mapped[str] = mapped_column(String(16), default="pending")
    decision_digest: Mapped[str | None] = mapped_column(String(64))
    receipt: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        Index("ix_memory_proposals_owner_status", "user_id", "status", "created_at"),
        Index("ix_memory_proposals_expires_at", "expires_at"),
        CheckConstraint("status in ('pending','approved','rejected','expired')", name="state"),
        CheckConstraint("bot_id in ('may','guong','nhip','rure')", name="bot"),
        CheckConstraint("version >= 1 and data_version >= 1", name="versions"),
        CheckConstraint("char_length(text) <= 120", name="text_length"),
    )
