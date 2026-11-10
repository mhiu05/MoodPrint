from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class TrustedContact(Base):
    __tablename__ = "trusted_contacts"
    __table_args__ = {"schema": "app"}
    id: Mapped[UUID] = mapped_column(primary_key=True)
    owner_id: Mapped[UUID]
    label: Mapped[str] = mapped_column(Text)
    role: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
