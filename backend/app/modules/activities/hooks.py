"""The only entry points social code may call (04 section 2).

Aborts lock the affected `connections` rows first (ORDER BY id FOR UPDATE) and only then
their sessions, the same room -> session order used by routes and the sweeper, so a hook
can never deadlock with them. Each abort bumps the room's activity watermark so open
panels close within about a second.
"""

from uuid import UUID

from sqlalchemy import func, or_, select

from app.infrastructure.database.models import now
from app.modules.social.models import Connection


async def _abort(db, rooms: list[Connection], reason: str) -> int:
    from app.modules.activities import machine
    from app.modules.activities import service as act
    from app.modules.activities.models import OPEN_STATES, ActivitySession

    if not rooms:
        return 0
    by_id = {room.id: room for room in rooms}
    rows = (
        await db.scalars(
            select(ActivitySession)
            .where(
                ActivitySession.connection_id.in_(list(by_id)),
                ActivitySession.state.in_(OPEN_STATES),
            )
            .order_by(ActivitySession.id)
            .with_for_update()
        )
    ).all()
    aborted = 0
    for row in rows:
        state, participants = await act.load_state(db, row)
        after = machine.abort(state, reason, now())
        if after is not None:
            await act.store(db, row, participants, state, after, by_id[row.connection_id])
            aborted += 1
    return aborted


async def abort_for_pair(db, pair_id: UUID, reason: str) -> int:
    rooms = (
        await db.scalars(
            select(Connection)
            .where(Connection.pair_id == pair_id)
            .order_by(Connection.id)
            .with_for_update()
        )
    ).all()
    return await _abort(db, list(rooms), reason)


async def abort_for_user(db, user_id: UUID, reason: str) -> int:
    rooms = (
        await db.scalars(
            select(Connection)
            .where(or_(Connection.low_user_id == user_id, Connection.high_user_id == user_id))
            .order_by(Connection.id)
            .with_for_update()
        )
    ).all()
    return await _abort(db, list(rooms), reason)


async def active_kinds(db, room_ids: list[UUID]) -> dict[UUID, str]:
    """Kind of each room's non-terminal session, in one query (ConnectionView.activeActivity)."""
    from app.modules.activities.models import OPEN_STATES, ActivitySession

    if not room_ids:
        return {}
    rows = await db.execute(
        select(ActivitySession.connection_id, ActivitySession.kind).where(
            ActivitySession.connection_id.in_(room_ids),
            ActivitySession.state.in_(OPEN_STATES),
        )
    )
    return {room_id: kind for room_id, kind in rows.all()}


async def pending_invites(db, user_id: UUID, room_ids: list[UUID]) -> int:
    from app.modules.activities.models import ActivitySession

    if not room_ids:
        return 0
    return (
        await db.scalar(
            select(func.count())
            .select_from(ActivitySession)
            .where(
                ActivitySession.connection_id.in_(room_ids),
                ActivitySession.invitee_id == user_id,
                ActivitySession.state == "invited",
                ActivitySession.deadline_at > now(),
            )
        )
        or 0
    )
