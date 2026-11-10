from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, Integer, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class School(Base):
    __tablename__ = "schools"
    __table_args__ = {"schema": "app"}
    id: Mapped[UUID] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(Text)
    verification_status: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class SchoolMembership(Base):
    __tablename__ = "school_memberships"
    __table_args__ = {"schema": "app"}
    school_id: Mapped[UUID] = mapped_column(primary_key=True)
    user_id: Mapped[UUID] = mapped_column(primary_key=True)
    role: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class CaseShare(Base):
    __tablename__ = "case_shares"
    __table_args__ = {"schema": "app"}
    id: Mapped[UUID] = mapped_column(primary_key=True)
    owner_id: Mapped[UUID]
    case_id: Mapped[UUID | None]
    school_id: Mapped[UUID]
    status: Mapped[str] = mapped_column(Text)
    identity_mode: Mapped[str] = mapped_column(Text)
    shared_fields: Mapped[list[str]] = mapped_column(ARRAY(Text))
    snapshot: Mapped[dict | None] = mapped_column(JSONB)
    confirmation_version: Mapped[str | None] = mapped_column(Text)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    withdrawn_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class CaseShareEvidence(Base):
    __tablename__ = "case_share_evidence"
    __table_args__ = {"schema": "app"}
    share_id: Mapped[UUID] = mapped_column(primary_key=True)
    evidence_id: Mapped[UUID] = mapped_column(primary_key=True)
    owner_id: Mapped[UUID]
