"""D-01: database invariants for shared activities (one open session per connection)."""

from datetime import timedelta
from uuid import UUID

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.infrastructure.database.models import now
from app.modules.activities.models import ActivityResponse, ActivitySession
from app.modules.social.models import Connection
from tests.social_helpers import open_room

pytestmark = pytest.mark.postgres


async def session_row(app, room_id, inviter, invitee, state="invited"):
    async with app.state.database.sessions() as db:
        room = await db.get(Connection, UUID(room_id))
    return ActivitySession(
        connection_id=room.id,
        pair_id=room.pair_id,
        kind="icebreaker",
        definition_version="icebreaker-v1",
        inviter_id=inviter,
        invitee_id=invitee,
        state=state,
        deadline_at=now() + timedelta(minutes=10),
    )


async def test_only_one_open_session_per_connection(clients):
    app, actors, _, room = await open_room(clients)
    a, b = actors[0][1], actors[1][1]
    async with app.state.database.sessions.begin() as db:
        db.add(await session_row(app, room, a, b))
    with pytest.raises(IntegrityError):
        async with app.state.database.sessions.begin() as db:
            db.add(await session_row(app, room, b, a, "active"))
    async with app.state.database.sessions.begin() as db:
        db.add(await session_row(app, room, b, a, "completed"))
        db.add(await session_row(app, room, a, b, "declined"))
    async with app.state.database.sessions() as db:
        states = sorted((await db.scalars(select(ActivitySession.state))).all())
        version = await db.scalar(select(Connection.activity_seq))
    assert states == ["completed", "declined", "invited"]
    assert version == 0


async def test_a_response_must_answer_or_skip(clients):
    app, actors, _, room = await open_room(clients)
    a, b = actors[0][1], actors[1][1]
    async with app.state.database.sessions.begin() as db:
        row = await session_row(app, room, a, b, "active")
        db.add(row)
        await db.flush()
        session_id = row.id
    with pytest.raises(IntegrityError):
        async with app.state.database.sessions.begin() as db:
            db.add(ActivityResponse(session_id=session_id, user_id=a, round=1, item_id="x"))
    async with app.state.database.sessions.begin() as db:
        db.add(
            ActivityResponse(session_id=session_id, user_id=a, round=1, item_id="x", skipped=True)
        )
