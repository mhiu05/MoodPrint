from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, Integer, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class SupportDraft(Base):
    __tablename__ = "support_drafts"
    __table_args__ = {"schema": "app"}
    id: Mapped[UUID] = mapped_column(primary_key=True)
    owner_id: Mapped[UUID]
    case_id: Mapped[UUID | None]
    recipient_type: Mapped[str] = mapped_column(Text)
    identity_mode: Mapped[str] = mapped_column(Text)
    content: Mapped[str] = mapped_column(Text)
    compose: Mapped[dict] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(Text)
    version: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
