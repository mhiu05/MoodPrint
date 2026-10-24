from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.models import Base, User, now
from app.modules.social.models import Connection


class IdentityField(Base):
    __tablename__ = "identity_fields"
    user_id: Mapped[UUID] = mapped_column(ForeignKey(User.id), primary_key=True)
    field: Mapped[str] = mapped_column(String(16), primary_key=True)
    value: Mapped[str] = mapped_column(String(40))
    version: Mapped[int] = mapped_column(default=1)


class RevealAccess(Base):
    __tablename__ = "reveal_access"
    id: Mapped[UUID] = mapped_column(PGUUID, primary_key=True, default=uuid4)
    connection_id: Mapped[UUID] = mapped_column(ForeignKey(Connection.id), index=True)
    owner_id: Mapped[UUID] = mapped_column(ForeignKey(User.id), index=True)
    recipient_id: Mapped[UUID] = mapped_column(ForeignKey(User.id), index=True)
    field: Mapped[str] = mapped_column(String(16))
    identity_version: Mapped[int]
    status: Mapped[str] = mapped_column(String(16), default="pending")
    version: Mapped[int] = mapped_column(default=1)
    preview_digest: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    cooldown_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    __table_args__ = (
        Index(
            "uq_active_reveal",
            "connection_id",
            "owner_id",
            "recipient_id",
            "field",
            unique=True,
            postgresql_where=(status == "granted"),
        ),
    )


class Report(Base):
    __tablename__ = "reports"
    id: Mapped[UUID] = mapped_column(PGUUID, primary_key=True, default=uuid4)
    reporter_id: Mapped[UUID] = mapped_column(ForeignKey(User.id), index=True)
    subject_id: Mapped[UUID] = mapped_column(ForeignKey(User.id), index=True)
    reason: Mapped[str] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(String(16), default="received")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    # At most two explicit selections; never a whole transcript or model context.
    evidence: Mapped[list] = mapped_column(JSONB, default=list)
