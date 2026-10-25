"""Server-authoritative shared activity state; exactly two participants per session.

Content columns hold item ids and options only, never user text; answers live in
activity_responses (retained 90 days like messages).
"""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    SmallInteger,
    String,
)
from sqlalchemy import text as sql
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.models import Base, User, now
from app.modules.social.models import Connection, Pair

OPEN_STATES = ("invited", "active", "paused")
OPEN = "state IN ('invited','active','paused')"


class ActivitySession(Base):
    __tablename__ = "activity_sessions"
    id: Mapped[UUID] = mapped_column(PGUUID, primary_key=True, default=uuid4)
    connection_id: Mapped[UUID] = mapped_column(ForeignKey(Connection.id))
    pair_id: Mapped[UUID] = mapped_column(ForeignKey(Pair.id))
    kind: Mapped[str] = mapped_column(String(16))
    definition_version: Mapped[str] = mapped_column(String(24))
    inviter_id: Mapped[UUID] = mapped_column(ForeignKey(User.id))
    invitee_id: Mapped[UUID] = mapped_column(ForeignKey(User.id))
    state: Mapped[str] = mapped_column(String(12))
    end_reason: Mapped[str | None] = mapped_column(String(24))
    round: Mapped[int] = mapped_column(SmallInteger, default=0, server_default="0")
    phase: Mapped[str] = mapped_column(String(12), default="invited", server_default="invited")
    content: Mapped[dict] = mapped_column(JSONB, default=dict, server_default=sql("'{}'::jsonb"))
    timer: Mapped[dict | None] = mapped_column(JSONB)
    score: Mapped[dict | None] = mapped_column(JSONB)
    version: Mapped[int] = mapped_column(default=1, server_default="1")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now, server_default=sql("now()")
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deadline_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        CheckConstraint("kind IN ('icebreaker','coop_quiz','focus')", name="kind"),
        CheckConstraint(
            "state IN ('invited','active','paused','completed','ended','declined',"
            "'cancelled','expired','aborted')",
            name="state",
        ),
        CheckConstraint("inviter_id <> invitee_id", name="distinct_participants"),
        Index(
            "uq_activity_open_per_connection",
            "connection_id",
            unique=True,
            postgresql_where=sql(OPEN),
        ),
        Index("ix_activity_sessions_deadline", "deadline_at", postgresql_where=sql(OPEN)),
        Index(
            "ix_activity_sessions_connection_created",
            "connection_id",
            sql("created_at DESC"),
        ),
        Index("ix_activity_sessions_inviter_created", "inviter_id", "created_at"),
    )


class ActivityParticipant(Base):
    __tablename__ = "activity_participants"
    session_id: Mapped[UUID] = mapped_column(
        ForeignKey(ActivitySession.id, ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[UUID] = mapped_column(ForeignKey(User.id), primary_key=True, index=True)
    role: Mapped[str] = mapped_column(String(8))
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ready_round: Mapped[int] = mapped_column(SmallInteger, default=0, server_default="0")
    feedback: Mapped[str | None] = mapped_column(String(12))
    feedback_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        CheckConstraint("role IN ('inviter','invitee')", name="role"),
        CheckConstraint(
            "feedback IS NULL OR feedback IN ('liked','neutral','not_for_me')", name="feedback"
        ),
    )


class ActivityResponse(Base):
    __tablename__ = "activity_responses"
    session_id: Mapped[UUID] = mapped_column(
        ForeignKey(ActivitySession.id, ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[UUID] = mapped_column(ForeignKey(User.id), primary_key=True, index=True)
    round: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    item_id: Mapped[str] = mapped_column(String(32))
    choice: Mapped[int | None] = mapped_column(SmallInteger)
    text: Mapped[str | None] = mapped_column(String(140))
    skipped: Mapped[bool] = mapped_column(default=False, server_default="false")
    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now, server_default=sql("now()")
    )
    __table_args__ = (
        CheckConstraint("round BETWEEN 1 AND 10", name="round"),
        CheckConstraint("skipped OR choice IS NOT NULL OR text IS NOT NULL", name="answer"),
    )
