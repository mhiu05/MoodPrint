"""Persistent published-profile and social state; no private AI content."""

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
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.models import Base, User, now


class MatchingDraft(Base):
    __tablename__ = "matching_drafts"
    user_id: Mapped[UUID] = mapped_column(ForeignKey(User.id), primary_key=True)
    payload: Mapped[dict] = mapped_column(JSONB)
    version: Mapped[int] = mapped_column(default=1)
    preview_digest: Mapped[str | None] = mapped_column(String(64))
    preview_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class PublishedProfile(Base):
    __tablename__ = "published_profiles"
    id: Mapped[UUID] = mapped_column(PGUUID, primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey(User.id), index=True)
    payload: Mapped[dict] = mapped_column(JSONB)
    version: Mapped[int]
    consent_version: Mapped[int]
    valid: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (
        UniqueConstraint("user_id", "version"),
        Index("uq_published_active_owner", "user_id", unique=True, postgresql_where=text("valid")),
    )


class CandidateReference(Base):
    __tablename__ = "candidate_references"
    id: Mapped[UUID] = mapped_column(PGUUID, primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey(User.id), index=True)
    peer_id: Mapped[UUID] = mapped_column(ForeignKey(User.id), index=True)
    profile_version: Mapped[int]
    peer_profile_version: Mapped[int]
    consent_version: Mapped[int]
    peer_consent_version: Mapped[int]
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    __table_args__ = (CheckConstraint("user_id <> peer_id", name="candidate_distinct"),)


class Pair(Base):
    __tablename__ = "pairs"
    id: Mapped[UUID] = mapped_column(PGUUID, primary_key=True, default=uuid4)
    low_user_id: Mapped[UUID] = mapped_column(ForeignKey(User.id), index=True)
    high_user_id: Mapped[UUID] = mapped_column(ForeignKey(User.id), index=True)
    version: Mapped[int] = mapped_column(default=1)
    cooldown_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        UniqueConstraint("low_user_id", "high_user_id"),
        CheckConstraint("low_user_id < high_user_id", name="canonical_pair"),
    )


class ConnectionRequest(Base):
    __tablename__ = "connection_requests"
    id: Mapped[UUID] = mapped_column(PGUUID, primary_key=True, default=uuid4)
    pair_id: Mapped[UUID] = mapped_column(ForeignKey(Pair.id), index=True)
    sender_id: Mapped[UUID] = mapped_column(ForeignKey(User.id), index=True)
    recipient_id: Mapped[UUID] = mapped_column(ForeignKey(User.id), index=True)
    status: Mapped[str] = mapped_column(String(16), default="pending")
    version: Mapped[int] = mapped_column(default=1)
    snapshots: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    connection_id: Mapped[UUID | None] = mapped_column(PGUUID)
    __table_args__ = (
        CheckConstraint("sender_id <> recipient_id", name="request_distinct"),
        CheckConstraint(
            "status in ('pending','accepted','declined','cancelled','expired','invalidated')",
            name="request_status",
        ),
        Index("uq_pending_pair", "pair_id", unique=True, postgresql_where=text("status='pending'")),
        Index("ix_connection_requests_recipient_status", "recipient_id", "status"),
    )


class Connection(Base):
    __tablename__ = "connections"
    id: Mapped[UUID] = mapped_column(PGUUID, primary_key=True, default=uuid4)
    pair_id: Mapped[UUID] = mapped_column(ForeignKey(Pair.id), index=True)
    low_user_id: Mapped[UUID] = mapped_column(ForeignKey(User.id), index=True)
    high_user_id: Mapped[UUID] = mapped_column(ForeignKey(User.id), index=True)
    status: Mapped[str] = mapped_column(String(16), default="open")
    version: Mapped[int] = mapped_column(default=1)
    snapshots: Mapped[dict] = mapped_column(JSONB)
    next_seq: Mapped[int] = mapped_column(BigInteger, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (
        CheckConstraint("low_user_id < high_user_id", name="connection_canonical"),
        CheckConstraint("status in ('open','closed','blocked')", name="connection_status"),
        Index("uq_open_pair", "pair_id", unique=True, postgresql_where=text("status='open'")),
    )


class HumanMessage(Base):
    __tablename__ = "human_messages"
    id: Mapped[UUID] = mapped_column(PGUUID, primary_key=True, default=uuid4)
    connection_id: Mapped[UUID] = mapped_column(ForeignKey(Connection.id), index=True)
    sender_id: Mapped[UUID] = mapped_column(ForeignKey(User.id), index=True)
    client_message_id: Mapped[UUID] = mapped_column(PGUUID)
    seq: Mapped[int] = mapped_column(BigInteger)
    text: Mapped[str] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (
        UniqueConstraint(
            "connection_id", "sender_id", "client_message_id", name="uq_human_messages_client_id"
        ),
        UniqueConstraint("connection_id", "seq", name="uq_human_messages_sequence"),
        CheckConstraint("char_length(text) between 1 and 500", name="message_length"),
    )


class Block(Base):
    __tablename__ = "blocks"
    blocker_id: Mapped[UUID] = mapped_column(ForeignKey(User.id), primary_key=True)
    blocked_id: Mapped[UUID] = mapped_column(ForeignKey(User.id), primary_key=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (CheckConstraint("blocker_id <> blocked_id", name="block_distinct"),)


class ConnectionRead(Base):
    """Private read marker for unread counts; never shown to the peer (DR-13)."""

    __tablename__ = "connection_reads"
    connection_id: Mapped[UUID] = mapped_column(ForeignKey(Connection.id), primary_key=True)
    user_id: Mapped[UUID] = mapped_column(ForeignKey(User.id), primary_key=True, index=True)
    last_read_seq: Mapped[int] = mapped_column(BigInteger, default=0, server_default="0")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now, server_default=func.now()
    )
    __table_args__ = (CheckConstraint("last_read_seq >= 0", name="read_seq"),)
