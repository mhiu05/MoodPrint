"""Per-edge sharing opt-in and content-free collaboration receipts (phase-2/05 §1).

Neither table stores a request, a specialist output, a prompt or any journal text: a receipt
is the auditable fact that a bounded consultation happened (edge, rule, status, digests). The
CHECK on (edge, requester, specialist) is a second line of defence behind ``policy.EDGES``.
Account deletion removes both tables explicitly (the users row is a tombstone).
"""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.models import AiRun, Base, User, now

SHARING_POLICY_VERSION = "sharing-v1"
LEGACY_EDGES = ("nhip_energy_for_rure", "nhip_habit_for_may", "rure_activity_for_guong")
# V3 (0024): Điều phối may consult or hand over to a specialist only through an enabled edge.
V3_EDGES = (
    "dieuphoi_consult_nhatky", "dieuphoi_consult_hoatdong", "dieuphoi_handoff_nhatky",
    "dieuphoi_handoff_hoatdong",
)
EDGE_VALUES = LEGACY_EDGES + V3_EDGES
STATUSES = ("authorized", "denied", "completed", "failed", "timeout", "cancelled", "discarded")
_EDGE_IN = "edge in (" + ", ".join(f"'{edge}'" for edge in EDGE_VALUES) + ")"


class AiSharingPermission(Base):
    """Explicit, default-off consent for one requester → specialist edge."""

    __tablename__ = "ai_sharing_permissions"
    user_id: Mapped[UUID] = mapped_column(ForeignKey(User.id, ondelete="CASCADE"), primary_key=True)
    edge: Mapped[str] = mapped_column(String(48), primary_key=True)
    enabled: Mapped[bool] = mapped_column(default=False, server_default=text("false"))
    version: Mapped[int] = mapped_column(default=1, server_default=text("1"))
    policy_version: Mapped[str] = mapped_column(
        String(32), default=SHARING_POLICY_VERSION, server_default=text(f"'{SHARING_POLICY_VERSION}'")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now, server_default=text("clock_timestamp()")
    )
    __table_args__ = (
        CheckConstraint(_EDGE_IN, name="edge"),
        CheckConstraint("version >= 1", name="version"),
        CheckConstraint(f"policy_version in ('{SHARING_POLICY_VERSION}')", name="policy"),
    )


class AiCollaboration(Base):
    """One receipt per consultation; the only source of a user-visible collaboration line."""

    __tablename__ = "ai_collaborations"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey(User.id, ondelete="CASCADE"))
    primary_run_id: Mapped[UUID] = mapped_column(ForeignKey(AiRun.id, ondelete="CASCADE"))
    specialist_run_id: Mapped[UUID | None] = mapped_column(ForeignKey(AiRun.id, ondelete="SET NULL"))
    edge: Mapped[str] = mapped_column(String(48))
    rule_id: Mapped[str] = mapped_column(String(8))
    requester_bot: Mapped[str] = mapped_column(String(16))
    specialist_bot: Mapped[str] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(16))
    deny_reason: Mapped[str | None] = mapped_column(String(32))
    # Content-free outcome code of an unsuccessful consultation (timeout, invalid_output, ...).
    failure_code: Mapped[str | None] = mapped_column(String(32))
    permission_version: Mapped[int]
    data_version: Mapped[int]
    input_schema: Mapped[str] = mapped_column(String(32))
    input_digest: Mapped[str] = mapped_column(String(64))
    output_digest: Mapped[str | None] = mapped_column(String(64))
    used_in_reply: Mapped[bool] = mapped_column(default=False, server_default=text("false"))
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now, server_default=text("clock_timestamp()")
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        UniqueConstraint("primary_run_id", "specialist_bot", "edge"),
        CheckConstraint(
            "status in ('authorized', 'denied', 'completed', 'failed', 'timeout', 'cancelled', 'discarded')",
            name="status",
        ),
        CheckConstraint(
            "(edge = 'nhip_energy_for_rure' and requester_bot = 'rure' and specialist_bot = 'nhip') "
            "or (edge = 'nhip_habit_for_may' and requester_bot = 'may' and specialist_bot = 'nhip') "
            "or (edge = 'rure_activity_for_guong' and requester_bot = 'guong' and specialist_bot = 'rure')",
            name="edge",
        ),
        CheckConstraint("rule_id in ('R1', 'R2', 'R3', 'R4')", name="rule"),
        CheckConstraint("(status = 'denied') = (deny_reason is not null)", name="deny"),
        CheckConstraint(
            "deny_reason is null or deny_reason in ('journal_consent_off', 'no_data', 'daily_cap', 'budget', 'time_budget', 'capacity')",
            name="deny_reason",
        ),
        CheckConstraint(
            "failure_code is null or status in ('failed', 'timeout', 'cancelled', 'discarded')",
            name="failure",
        ),
        CheckConstraint("not used_in_reply or status = 'completed'", name="used"),
        CheckConstraint(
            "input_digest ~ '^[0-9a-f]{64}$' and (output_digest is null or output_digest ~ '^[0-9a-f]{64}$')",
            name="digest",
        ),
        Index("ix_ai_collaborations_user_started", "user_id", "started_at"),
    )
