"""Deadline sweeper (06 section 10): invite expiry, idle expiry and focus phase changes.

Due ids are read without locks; each one is then handled in its own short transaction
that locks the room (SKIP LOCKED: a busy room is retried next tick) and then the
session. It never locks users, so it cannot invert the routes' lock order.
"""

import logging
from datetime import datetime

from sqlalchemy import select

from app.infrastructure.database.models import now
from app.modules.activities import machine
from app.modules.activities import service as act
from app.modules.activities.models import OPEN_STATES, ActivitySession
from app.modules.social.models import Connection

BATCH = 50
log = logging.getLogger("moodprint")


async def advance_due(app, at: datetime | None = None) -> int:
    at = at or now()
    sessions = app.state.database.require()
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
            if after.terminal:
                log.info("metric=activity_ended kind=%s reason=%s", after.kind, after.end_reason)
    return advanced
