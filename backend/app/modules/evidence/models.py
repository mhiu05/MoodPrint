from datetime import datetime
from uuid import UUID

from sqlalchemy import BigInteger, DateTime, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class EvidenceItem(Base):
    __tablename__ = "evidence_items"
    __table_args__ = {"schema": "app"}
    id: Mapped[UUID] = mapped_column(primary_key=True)
    owner_id: Mapped[UUID]
    case_id: Mapped[UUID | None]
    kind: Mapped[str] = mapped_column(Text)
    origin: Mapped[str] = mapped_column(Text)
    storage_bucket: Mapped[str | None] = mapped_column(Text)
    storage_key: Mapped[str | None] = mapped_column(Text)
    original_filename: Mapped[str | None] = mapped_column(Text)
    declared_mime_type: Mapped[str | None] = mapped_column(Text)
    stored_mime_type: Mapped[str | None] = mapped_column(Text)
    expected_byte_size: Mapped[int | None] = mapped_column(BigInteger)
    byte_size: Mapped[int | None] = mapped_column(BigInteger)
    client_sha256: Mapped[str | None] = mapped_column(Text)
    storage_etag: Mapped[str | None] = mapped_column(Text)
    original_text: Mapped[str | None] = mapped_column(Text)
    shown_timestamp: Mapped[str] = mapped_column(Text)
    captured_at_label: Mapped[str] = mapped_column(Text)
    user_edited_text: Mapped[str | None] = mapped_column(Text)
    review_status: Mapped[str] = mapped_column(Text)
    limitations: Mapped[list[str]] = mapped_column(ARRAY(Text))
    upload_status: Mapped[str] = mapped_column(Text)
    purge_claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    purged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class EvidenceDerivative(Base):
    __tablename__ = "evidence_derivatives"
    __table_args__ = {"schema": "app"}
    id: Mapped[UUID] = mapped_column(primary_key=True)
    evidence_id: Mapped[UUID]
    owner_id: Mapped[UUID]
    kind: Mapped[str] = mapped_column(Text)
    storage_key: Mapped[str | None] = mapped_column(Text)
    content: Mapped[dict | None] = mapped_column(JSONB)
    generator: Mapped[str] = mapped_column(Text)
    generator_version: Mapped[str] = mapped_column(Text)
    source_sha256: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class CaseEventEvidence(Base):
    __tablename__ = "case_event_evidence"
    __table_args__ = {"schema": "app"}
    event_id: Mapped[UUID] = mapped_column(primary_key=True)
    evidence_id: Mapped[UUID] = mapped_column(primary_key=True)
    owner_id: Mapped[UUID]
