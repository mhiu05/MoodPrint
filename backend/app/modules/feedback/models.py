"""Voluntary product feedback (private schema), deliberately unlinked from any identity.

``AppFeedback`` has no user, session, address, conversation, device or URL column and no foreign
key. Only ``FeedbackSubmissionReceipt`` (owner + idempotency key + payload digest) points at it, and
that link is short-lived: it cascades from the feedback and from the user, never the other way, so a
guest purge deletes the receipt and the independently retained feedback survives. Value rules are
enforced by private immutable database functions so direct SQL meets the same policy as the API.
"""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    ARRAY,
    CHAR,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.models import Base, User

# Database time is the authority for every retention cutoff and daily window.
DB_NOW = text("clock_timestamp()")

CATEGORIES = (
    "ease_of_use",
    "ai_quality",
    "interface",
    "performance",
    "bug",
    "missing_feature",
    "privacy_trust",
    "other",
)
CONTEXTS = ("general", "assistants", "mood", "memory", "privacy", "activities", "trial_end")
STATUSES = ("new", "reviewed", "planned", "resolved", "spam")
ACCOUNT_KINDS = ("guest", "registered")
REVIEW_ACTIONS = ("status", "redact")


def _in(column: str, values: tuple[str, ...]) -> str:
    return f"{column} in ({','.join(repr(value) for value in values)})"


class AppFeedback(Base):
    """One rating with optional categories/comment. Nothing here identifies who sent it."""

    __tablename__ = "app_feedback"
    id: Mapped[UUID] = mapped_column(PGUUID, primary_key=True, default=uuid4)
    rating: Mapped[int] = mapped_column(SmallInteger)
    categories: Mapped[list[str]] = mapped_column(
        ARRAY(Text), default=list, server_default=text("'{}'::text[]")
    )
    comment: Mapped[str | None] = mapped_column(Text)
    app_version: Mapped[str] = mapped_column(String(64))
    context: Mapped[str] = mapped_column(String(16), default="general", server_default="general")
    account_kind: Mapped[str] = mapped_column(String(10))
    disclosure_version: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=DB_NOW)
    status: Mapped[str] = mapped_column(String(12), default="new", server_default="new")
    version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        CheckConstraint("rating between 1 and 5", name="rating"),
        CheckConstraint("moodprint.feedback_categories_valid(categories)", name="categories"),
        CheckConstraint("moodprint.feedback_comment_valid(comment)", name="comment"),
        CheckConstraint(_in("context", CONTEXTS), name="context"),
        CheckConstraint(_in("account_kind", ACCOUNT_KINDS), name="account_kind"),
        CheckConstraint("disclosure_version ~ '^feedback-v[0-9]+$'", name="disclosure_version"),
        CheckConstraint(_in("status", STATUSES), name="status"),
        CheckConstraint("version > 0", name="version"),
        Index("ix_app_feedback_created_at", "created_at", "id"),
        Index("ix_app_feedback_status", "status", "created_at", "id"),
    )


class FeedbackSubmissionReceipt(Base):
    """Ephemeral owner link used only for idempotency and per-owner limits; purged with the owner."""

    __tablename__ = "feedback_submission_receipts"
    id: Mapped[UUID] = mapped_column(PGUUID, primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey(User.id, ondelete="CASCADE"))
    idempotency_key: Mapped[str] = mapped_column(String(128))
    payload_digest: Mapped[str] = mapped_column(CHAR(64))
    feedback_id: Mapped[UUID] = mapped_column(ForeignKey(AppFeedback.id, ondelete="CASCADE"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=DB_NOW)
    __table_args__ = (
        UniqueConstraint("user_id", "idempotency_key"),
        Index("ix_feedback_submission_receipts_user_created", "user_id", "created_at"),
        Index("ix_feedback_submission_receipts_feedback_id", "feedback_id"),
    )


class FeedbackReviewEvent(Base):
    """Content-free audit of a staff status change or redaction (never a copy of the comment)."""

    __tablename__ = "feedback_review_events"
    id: Mapped[UUID] = mapped_column(PGUUID, primary_key=True, default=uuid4)
    feedback_id: Mapped[UUID] = mapped_column(ForeignKey(AppFeedback.id, ondelete="CASCADE"))
    staff_id: Mapped[UUID] = mapped_column(ForeignKey(User.id, ondelete="RESTRICT"))
    action: Mapped[str] = mapped_column(String(8))
    from_status: Mapped[str | None] = mapped_column(String(12))
    to_status: Mapped[str | None] = mapped_column(String(12))
    resulting_version: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=DB_NOW)
    __table_args__ = (
        CheckConstraint(_in("action", REVIEW_ACTIONS), name="action"),
        CheckConstraint(
            f"(from_status IS NULL OR {_in('from_status', STATUSES)})"
            f" AND (to_status IS NULL OR {_in('to_status', STATUSES)})",
            name="statuses",
        ),
        CheckConstraint(
            "action <> 'status' OR (from_status IS NOT NULL AND to_status IS NOT NULL)",
            name="status_pair",
        ),
        CheckConstraint("resulting_version > 0", name="version"),
        Index("ix_feedback_review_events_feedback_created", "feedback_id", "created_at"),
        Index("ix_feedback_review_events_staff_id", "staff_id"),
    )
