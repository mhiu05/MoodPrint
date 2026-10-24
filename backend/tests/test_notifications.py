import json
from uuid import uuid4

import pytest
from sqlalchemy import select
from starlette.requests import Request

from app.core.security import Actor
from app.infrastructure.database.models import AuthSession
from tests.test_social import key, open_room

pytestmark = pytest.mark.postgres


async def test_id_only_notification_rechecks_block_before_returning_another_event(clients):
    from app.modules.social.notifications import event_stream

    app, actors, refs, room = await open_room(clients)
    client, uid = actors[1]
    async with app.state.database.sessions() as db:
        own = await db.scalar(select(AuthSession).where(AuthSession.user_id == uid))
        actor = Actor(uid, own.id, 1)
    request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/",
            "headers": [],
            "app": app,
            "query_string": b"",
        }
    )
    generator = event_stream(request, actor, __import__("uuid").UUID(room), after_seq=0)
    first = await anext(generator)
    assert "PRIVATE-MESSAGE" not in first
    message = await actors[0][0].post(
        f"/api/v1/connections/{room}/messages",
        json={"text": "PRIVATE-MESSAGE", "clientMessageId": str(uuid4())},
        headers=key(),
    )
    assert message.status_code == 201
    next_event = await anext(generator)
    assert "PRIVATE-MESSAGE" not in next_event
    envelope = json.loads(
        next(line[6:] for line in next_event.splitlines() if line.startswith("data: "))
    )
    assert envelope["highWaterSeq"] == "1"
    await actors[0][0].post("/api/v1/blocks", json={"peerRef": refs[0]}, headers=key())
    ended = await anext(generator)
    assert "access_revoked" in ended and "PRIVATE-MESSAGE" not in ended
    await generator.aclose()


async def test_social_stream_slots_are_capped_per_user_and_released(clients):
    from app.modules.social.notifications import STREAM_SLOTS

    app, actors, _, room = await open_room(clients)
    client, uid = actors[1]
    STREAM_SLOTS.active[uid] = STREAM_SLOTS.limit
    capped = await client.get(f"/api/v1/connections/{room}/events")
    assert capped.status_code == 429 and capped.json()["error"]["code"] == "STREAM_LIMIT"
    STREAM_SLOTS.active.pop(uid)
    gone = await client.get(f"/api/v1/connections/{uuid4()}/events")
    assert gone.status_code == 404
    # A rejected request must not leak its reservation.
    assert STREAM_SLOTS.active.get(uid, 0) == 0
