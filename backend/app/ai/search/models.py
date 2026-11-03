from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.models import AiRun, Base, User, now


class AiSearchUsage(Base):
    __tablename__ = "ai_search_usage"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID | None] = mapped_column(ForeignKey(User.id, ondelete="SET NULL"), index=True)
    parent_run_id: Mapped[UUID | None] = mapped_column(ForeignKey(AiRun.id, ondelete="SET NULL"), index=True)
    child_run_id: Mapped[UUID | None] = mapped_column(ForeignKey(AiRun.id, ondelete="SET NULL"), index=True)
    provider: Mapped[str] = mapped_column(String(16))
    ordinal: Mapped[int] = mapped_column(default=1)
    state: Mapped[str] = mapped_column(String(16), default="reserved")
    active: Mapped[bool] = mapped_column(default=True)
    reservation_nano_usd: Mapped[int] = mapped_column(BigInteger)
    actual_nano_usd: Mapped[int | None] = mapped_column(BigInteger)
    # Conservative fallback if a token row/identity is purged; never release unknown money.
    token_liability_nano_usd: Mapped[int] = mapped_column(BigInteger, default=0)
    tokens_uncertain: Mapped[bool] = mapped_column(default=False)
    pricing_version: Mapped[str] = mapped_column(String(100))
    call_count: Mapped[int] = mapped_column(default=0)
    item_count: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (
        UniqueConstraint("parent_run_id", "provider", "ordinal"),
        CheckConstraint("provider in ('openai_web','apify')", name="provider"),
        CheckConstraint("state in ('reserved','dispatched','settled','uncertain')", name="state"),
        CheckConstraint("(state = 'settled') = (actual_nano_usd is not null)", name="settlement"),
        CheckConstraint("reservation_nano_usd >= 0 and (actual_nano_usd is null or actual_nano_usd >= 0) and token_liability_nano_usd >= 0", name="money"),
        CheckConstraint("ordinal = 1 and call_count between 0 and 1 and item_count between 0 and 5", name="counts"),
        Index("ix_ai_search_usage_active", "active", "created_at"),
    )


class AiMapsSearch(Base):
    __tablename__ = "ai_maps_searches"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID | None] = mapped_column(ForeignKey(User.id, ondelete="SET NULL"), index=True)
    parent_run_id: Mapped[UUID | None] = mapped_column(ForeignKey(AiRun.id, ondelete="SET NULL"), index=True)
    operation_id: Mapped[UUID] = mapped_column(ForeignKey(AiSearchUsage.id), unique=True)
    scope_id: Mapped[UUID | None]
    conversation_id: Mapped[UUID | None]
    session_id: Mapped[UUID | None]
    auth_version: Mapped[int]
    data_version: Mapped[int]
    status: Mapped[str] = mapped_column(String(16), default="starting")
    version: Mapped[int] = mapped_column(default=1)
    provider_ref: Mapped[dict | None] = mapped_column(JSONB)
    cancel_requested: Mapped[bool] = mapped_column(default=False)
    cleanup_done: Mapped[bool] = mapped_column(default=False)
    deadline: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    next_poll_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, index=True)
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    fence: Mapped[UUID | None]
    attempts: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (
        CheckConstraint("status in ('starting','pending','ready','empty','failed','timed_out','cancelled','expired')", name="status"),
        CheckConstraint("version >= 1 and attempts >= 0", name="version"),
    )
