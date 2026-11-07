from datetime import date, datetime
from uuid import UUID

from sqlalchemy import Date, DateTime, Integer, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class ActionPlanRecord(Base):
    __tablename__ = "action_plans"
    __table_args__ = {"schema": "app"}
    id: Mapped[UUID] = mapped_column(primary_key=True)
    case_id: Mapped[UUID]
    owner_id: Mapped[UUID]
    goal: Mapped[str] = mapped_column(Text, server_default="")
    chosen_option_id: Mapped[str] = mapped_column(Text, server_default="")
    status: Mapped[str] = mapped_column(Text, server_default="draft")
    next_review_date: Mapped[date | None] = mapped_column(Date)
    outcome_notes: Mapped[str] = mapped_column(Text, server_default="")
    version: Mapped[int] = mapped_column(Integer, server_default="1")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PlanItemRecord(Base):
    __tablename__ = "plan_items"
    __table_args__ = {"schema": "app"}
    id: Mapped[UUID] = mapped_column(primary_key=True)
    plan_id: Mapped[UUID]
    owner_id: Mapped[UUID]
    label: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, server_default="not_started")
    notes: Mapped[str] = mapped_column(Text, server_default="")
    priority: Mapped[str] = mapped_column(Text, server_default="normal")
    reason: Mapped[str] = mapped_column(Text, server_default="")
    position: Mapped[int] = mapped_column(Integer)
