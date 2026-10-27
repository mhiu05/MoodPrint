"""Deadline sweeper (06 section 10): invite expiry, idle expiry and focus phase changes.

Due ids are read without locks; each one is then handled in its own short transaction
that locks the room (SKIP LOCKED: a busy room is retried next tick) and then the
session. It never locks users, so it cannot invert the routes' lock order.
"""

import logging
from datetime import datetime

from sqlalchemy import or_, select

from app.infrastructure.database.models import User, now
from app.modules.activities import hooks, machine
from app.modules.activities import service as act
from app.modules.activities.models import OPEN_STATES, ActivitySession
from app.modules.social.models import Connection

BATCH = 50
log = logging.getLogger("moodprint")


async def abort_guest_sessions(app) -> int:
    """A guest can never take part in a shared activity; end any legacy or forged open session.

    The abort delivers no private event to the registered counterpart beyond the ordinary
    system-ended state, and locks the room first (the same room -> session order as routes).
    """
    sessions = app.state.database.require()
    async with sessions() as db:
        room_ids = (
            await db.scalars(
                select(ActivitySession.connection_id)
                .join(
                    User,
                    or_(
                        User.id == ActivitySession.inviter_id,
                        User.id == ActivitySession.invitee_id,
                    ),
                )
                .where(ActivitySession.state.in_(OPEN_STATES), User.account_kind == "guest")
                .distinct()
                .limit(BATCH)
            )
        ).all()
    aborted = 0
    for room_id in room_ids:
        async with sessions() as db, db.begin():
            room = await db.scalar(
                select(Connection).where(Connection.id == room_id).with_for_update(skip_locked=True)
            )
            if room is not None:
                aborted += await hooks.abort_rooms(db, [room], "guest_participant")
    return aborted


async def advance_due(app, at: datetime | None = None) -> int:
    at = at or now()
    sessions = app.state.database.require()
    aborted = await abort_guest_sessions(app)
    async with sessions() as db:
        due = (
            await db.execute(
                select(ActivitySession.id, ActivitySession.connection_id)
                .where(
                    ActivitySession.state.in_(OPEN_STATES),
                    ActivitySession.deadline_at <= at,
                )
                .order_by(ActivitySession.deadline_at)
                .limit(BATCH)
            )
        ).all()
    advanced = 0
    for session_id, connection_id in due:
        async with sessions() as db, db.begin():
            room = await db.scalar(
                select(Connection)
                .where(Connection.id == connection_id)
                .with_for_update(skip_locked=True)
            )
            if room is None:
                continue
            row = await db.scalar(
                select(ActivitySession).where(ActivitySession.id == session_id).with_for_update()
            )
            if (
                row is None
                or row.state not in OPEN_STATES
                or row.deadline_at is None
                or row.deadline_at > at
            ):
                continue  # a route changed it first
            state, participants = await act.load_state(db, row)
            after = machine.tick(state, at)
            if after is None:
                row.deadline_at = machine.deadline(state, at)
                continue
            await act.store(db, row, participants, state, after, room)
            advanced += 1
    return advanced + aborted
