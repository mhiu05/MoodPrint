"""Handwritten Phase 0 mappings; schema creation belongs to SQL migrations."""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import Boolean, DateTime, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class Profile(Base):
    __tablename__ = "profiles"
    __table_args__ = {"schema": "app"}
    user_id: Mapped[UUID] = mapped_column(primary_key=True)
    nickname: Mapped[str] = mapped_column(Text)
    age_band: Mapped[str | None] = mapped_column(Text)
    locale: Mapped[str] = mapped_column(Text, server_default="vi")
    start_interest: Mapped[str | None] = mapped_column(Text)
    reduced_motion: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    deletion_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AuditEvent(Base):
    __tablename__ = "audit_events"
    __table_args__ = {"schema": "app"}
    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=text("gen_random_uuid()"))
    actor_id: Mapped[UUID | None]
    action: Mapped[str] = mapped_column(Text)
    entity_type: Mapped[str] = mapped_column(Text)
    entity_id: Mapped[UUID]
    school_id: Mapped[UUID | None]
    event_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONB, server_default=text("'{}'::jsonb")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
