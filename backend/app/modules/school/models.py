"""One row per account that may use the school safety release."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.models import Base, now


class SchoolProfile(Base):
    __tablename__ = "school_profiles"
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("moodprint.users.id", ondelete="CASCADE"), primary_key=True
    )
    age_group: Mapped[str] = mapped_column(String(8))
    terms_version: Mapped[str | None] = mapped_column(String(32))
    terms_accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    neutral_mode: Mapped[bool] = mapped_column(default=False, server_default=text("false"))
    version: Mapped[int] = mapped_column(default=1, server_default="1")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now, server_default=text("clock_timestamp()")
    )
    __table_args__ = (
        CheckConstraint("age_group in ('11-14', '15-17')", name="age_group"),
        CheckConstraint("(terms_version is null) = (terms_accepted_at is null)", name="terms_pair"),
        CheckConstraint("version >= 1", name="version"),
    )
