from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, text
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
    # Workflow: received -> in_review (claim) -> resolved, compare-and-set on version.
    version: Mapped[int] = mapped_column(default=1, server_default="1")
    connection_id: Mapped[UUID | None] = mapped_column(ForeignKey(Connection.id))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolution: Mapped[str | None] = mapped_column(String(16))
    __table_args__ = (
        CheckConstraint(
            "resolution IS NULL OR resolution IN ('dismissed','warned','restricted','suspended')",
            name="resolution",
        ),
        Index("ix_reports_status_created", "status", "created_at"),
    )


class StaffRole(Base):
    """Granted by an operator only (reviewed SQL or local scripts), never via the API."""

    __tablename__ = "staff_roles"
    user_id: Mapped[UUID] = mapped_column(ForeignKey(User.id), primary_key=True)
    role: Mapped[str] = mapped_column(String(16))
    granted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now, server_default=text("now()")
    )
    # An operator label, not a user id.
    granted_by: Mapped[str] = mapped_column(String(64))
    __table_args__ = (CheckConstraint("role IN ('moderator','admin')", name="role"),)


class ModerationAction(Base):
    """Append-only audit of every moderation decision (kept one year)."""

    __tablename__ = "moderation_actions"
    id: Mapped[UUID] = mapped_column(PGUUID, primary_key=True, default=uuid4)
    report_id: Mapped[UUID | None] = mapped_column(ForeignKey(Report.id))
    subject_id: Mapped[UUID] = mapped_column(ForeignKey(User.id))
    staff_id: Mapped[UUID] = mapped_column(ForeignKey(User.id))
    action: Mapped[str] = mapped_column(String(16))
    until_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    note: Mapped[str] = mapped_column(String(500), default="", server_default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now, server_default=text("now()")
    )
    __table_args__ = (
        CheckConstraint("action IN ('dismiss','warn','restrict','suspend','lift')", name="action"),
        Index("ix_moderation_actions_subject", "subject_id", "created_at"),
    )
