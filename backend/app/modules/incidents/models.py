from datetime import date, datetime
from uuid import UUID

from sqlalchemy import Computed, Date, DateTime, Integer, Text, func
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class Case(Base):
    __tablename__ = "cases"
    __table_args__ = {"schema": "app"}
    id: Mapped[UUID] = mapped_column(primary_key=True)
    owner_id: Mapped[UUID]
    title: Mapped[str] = mapped_column(Text, server_default="")
    template: Mapped[str] = mapped_column(Text)
    perspective: Mapped[str] = mapped_column(Text, server_default="self")
    summary: Mapped[str] = mapped_column(Text, server_default="")
    category_tags: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default="{}")
    impact_tags: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default="{}")
    status: Mapped[str] = mapped_column(Text, server_default="draft")
    people: Mapped[str] = mapped_column(Text, server_default="")
    place: Mapped[str] = mapped_column(Text, server_default="")
    occurred_label: Mapped[str] = mapped_column(Text, server_default="")
    tried: Mapped[str] = mapped_column(Text, server_default="")
    trusted_person: Mapped[str] = mapped_column(Text, server_default="")
    search_text: Mapped[str | None] = mapped_column(
        Text, Computed("lower(app_private.f_unaccent(title || ' ' || summary))", persisted=True)
    )
    version: Mapped[int] = mapped_column(Integer, server_default="1")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CaseEvent(Base):
    __tablename__ = "case_events"
    __table_args__ = {"schema": "app"}
    id: Mapped[UUID] = mapped_column(primary_key=True)
    case_id: Mapped[UUID]
    owner_id: Mapped[UUID]
    occurred_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    occurred_on: Mapped[date | None] = mapped_column(Date)
    time_precision: Mapped[str] = mapped_column(Text, server_default="unknown")
    place: Mapped[str] = mapped_column(Text, server_default="")
    description: Mapped[str] = mapped_column(Text)
    provenance: Mapped[str] = mapped_column(Text, server_default="user_entered")
    needs_review: Mapped[bool] = mapped_column(server_default="false")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
