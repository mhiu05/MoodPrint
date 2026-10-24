from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.models import Base, User, now


class DataJob(Base):
    __tablename__ = "data_jobs"
    id: Mapped[UUID] = mapped_column(PGUUID, primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey(User.id), index=True)
    kind: Mapped[str] = mapped_column(String(16))
    scope: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(24), default="queued", index=True)
    version: Mapped[int] = mapped_column(default=1)
    attempts: Mapped[int] = mapped_column(default=0)
    lease_token: Mapped[UUID | None] = mapped_column(PGUUID, nullable=True)
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
