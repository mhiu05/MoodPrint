"""Activity persistence, locking and limits (06 section 10).

Lock order everywhere: users (pair_transaction) -> pair and room (live_room) ->
session. The sweeper and the lifecycle hooks take only the room -> session suffix.
"""

from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy import func, select

from app.core.errors import DomainError
from app.core.security import Actor
from app.infrastructure.database.models import now
from app.modules.activities import focus, icebreaker, quiz  # noqa: F401  (register kind rules)
from app.modules.activities.machine import (
    MachineError,
    ParticipantState,
    ResponseState,
    SessionState,
)
from app.modules.activities.models import (
    OPEN_STATES,
    ActivityParticipant,
    ActivityResponse,
    ActivitySession,
)
from app.modules.social import service as svc
from app.modules.social.models import Connection

INVITES_PER_CONNECTION_HOUR = 6
INVITES_PER_USER_DAY = 20
DECLINE_COOLDOWN = timedelta(minutes=10)
RECENT_SUMMARY = timedelta(minutes=15)


def refuse(error: MachineError) -> DomainError:
    return DomainError(error.status, error.code, error.message)


def require_enabled(request, kind: str | None = None) -> None:
    settings = request.app.state.settings
    if not settings.activities_enabled:
        raise DomainError(503, "ACTIVITIES_DISABLED", "Hoạt động chung đang tạm tắt.", True)
    if kind is not None and kind not in settings.activity_kinds:
        raise DomainError(422, "ACTIVITY_UNAVAILABLE", "Hoạt động này chưa được mở.")


async def load_state(
    db, row: ActivitySession
) -> tuple[SessionState, dict[UUID, ActivityParticipant]]:
    participants = {
        p.user_id: p
        for p in (
            await db.scalars(
                select(ActivityParticipant).where(ActivityParticipant.session_id == row.id)
            )
        ).all()
    }
    responses = (
        await db.scalars(select(ActivityResponse).where(ActivityResponse.session_id == row.id))
    ).all()
    state = SessionState(
        id=row.id,
        kind=row.kind,
        state=row.state,
        round=row.round,
        phase=row.phase,
        inviter_id=row.inviter_id,
        invitee_id=row.invitee_id,
        content=dict(row.content or {}),
        timer=row.timer,
        score=row.score,
        version=row.version,
        participants={
            uid: ParticipantState(
                uid, p.role, p.accepted_at, p.ready_round, p.feedback, p.feedback_at
            )
            for uid, p in participants.items()
        },
        responses={
            (r.user_id, r.round): ResponseState(
                r.user_id, r.round, r.item_id, r.choice, r.text, r.skipped, r.submitted_at
            )
            for r in responses
        },
        end_reason=row.end_reason,
        created_at=row.created_at,
        started_at=row.started_at,
        ended_at=row.ended_at,
        deadline_at=row.deadline_at,
    )
    return state, participants


async def store(
    db,
    row: ActivitySession,
    rows: dict[UUID, ActivityParticipant],
    before: SessionState,
    after: SessionState,
    room: Connection,
) -> SessionState:
    """Persist `after`, bump the session version and the room's activity watermark."""
    for name in (
        "state",
        "end_reason",
        "round",
        "phase",
        "content",
        "timer",
        "score",
        "started_at",
        "ended_at",
        "deadline_at",
    ):
        setattr(row, name, getattr(after, name))
    for uid, participant in after.participants.items():
        target = rows[uid]
        target.accepted_at, target.ready_round = participant.accepted_at, participant.ready_round
        target.feedback, target.feedback_at = participant.feedback, participant.feedback_at
    for key, response in after.responses.items():
        if key not in before.responses:
            db.add(
                ActivityResponse(
                    session_id=row.id,
                    user_id=response.user_id,
                    round=response.round,
                    item_id=response.item_id,
                    choice=response.choice,
                    text=response.text,
                    skipped=response.skipped,
                    submitted_at=response.submitted_at or now(),
                )
            )
    row.version += 1
    room.activity_seq += 1
    await db.flush()
    after.version = row.version
    return after


async def session_peer(request, actor: Actor, session_id: UUID) -> tuple[UUID, UUID]:
    async with request.app.state.database.require()() as db:
        row = await db.get(ActivitySession, session_id)
        if not row or actor.user_id not in (row.inviter_id, row.invitee_id):
            svc.missing()
        peer = row.invitee_id if row.inviter_id == actor.user_id else row.inviter_id
        return peer, row.connection_id


@asynccontextmanager
async def activity_transaction(request, actor: Actor, session_id: UUID, lock: bool = True):
    """Yields (db, user, peer, room, session_row) under the canonical lock order."""
    peer_id, connection_id = await session_peer(request, actor, session_id)
    async with svc.pair_transaction(request, actor, peer_id, lock=lock) as (db, user, peer):
        room = await svc.live_room(db, user, peer, connection_id, lock=lock)
        statement = select(ActivitySession).where(ActivitySession.id == session_id)
        row = await db.scalar(statement.with_for_update() if lock else statement)
        yield db, user, peer, room, row


async def open_session(db, connection_id: UUID, lock: bool = False) -> ActivitySession | None:
    statement = select(ActivitySession).where(
        ActivitySession.connection_id == connection_id,
        ActivitySession.state.in_(OPEN_STATES),
    )
    return await db.scalar(statement.with_for_update() if lock else statement)


async def latest_session(db, connection_id: UUID, at: datetime) -> ActivitySession | None:
    """The open session, or a just-finished one so both screens can show its summary."""
    row = await db.scalar(
        select(ActivitySession)
        .where(ActivitySession.connection_id == connection_id)
        .order_by(ActivitySession.created_at.desc())
        .limit(1)
    )
    if row and (row.state in OPEN_STATES or (row.ended_at and row.ended_at > at - RECENT_SUMMARY)):
        return row
    return None


async def check_invite_limits(db, user_id: UUID, connection_id: UUID, kind: str, at: datetime):
    per_connection = await db.scalar(
        select(func.count())
        .select_from(ActivitySession)
        .where(
            ActivitySession.connection_id == connection_id,
            ActivitySession.created_at > at - timedelta(hours=1),
        )
    )
    per_user = await db.scalar(
        select(func.count())
        .select_from(ActivitySession)
        .where(
            ActivitySession.inviter_id == user_id,
            ActivitySession.created_at > at - timedelta(hours=24),
        )
    )
    if per_connection >= INVITES_PER_CONNECTION_HOUR or per_user >= INVITES_PER_USER_DAY:
        raise DomainError(
            429,
            "ACTIVITY_INVITE_QUOTA",
            "Bạn đã mời khá nhiều lần. Hãy thử lại sau ít phút.",
            True,
            retry_after=600,
        )
    declined_at = await db.scalar(
        select(func.max(ActivitySession.ended_at)).where(
            ActivitySession.inviter_id == user_id,
            ActivitySession.connection_id == connection_id,
            ActivitySession.kind == kind,
            ActivitySession.state == "declined",
        )
    )
    if declined_at and declined_at > at - DECLINE_COOLDOWN:
        wait = int((declined_at + DECLINE_COOLDOWN - at).total_seconds()) + 1
        raise DomainError(
            429,
            "ACTIVITY_COOLDOWN",
            "Bạn kia chưa muốn chơi hoạt động này lúc này. Hãy thử lại sau.",
            True,
            retry_after=wait,
        )
