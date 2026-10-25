from datetime import datetime, timedelta
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import select

from app.infrastructure.database.models import Mood, now
from app.modules.social.models import HumanMessage
from tests.social_helpers import key, open_room

pytestmark = pytest.mark.postgres


async def test_mood_retention_boundaries_hide_reject_and_physically_purge(clients):
    app, actors = clients
    client, owner = actors[0]
    today = datetime.now(ZoneInfo("Asia/Bangkok")).date()
    old_date, kept_date = today - timedelta(days=90), today - timedelta(days=89)
    async with app.state.database.sessions.begin() as db:
        db.add_all(
            [
                Mood(
                    user_id=owner,
                    local_date=day,
                    value=3,
                    note="retention canary",
                    timezone="Asia/Bangkok",
                )
                for day in (old_date, kept_date)
            ]
        )
    assert [row["localDate"] for row in (await client.get("/api/v1/moods")).json()] == [
        str(kept_date)
    ]
    response = await client.put(
        f"/api/v1/moods/{old_date}",
        json={"value": 2, "note": "", "timezone": "Asia/Bangkok", "expectedVersion": 1},
        headers=key(),
    )
    assert response.status_code == 422
    exported = await client.post("/api/v1/exports", json={"scopes": ["moods"]}, headers=key())
    download = await client.get(f"/api/v1/exports/{exported.json()['id']}/download")
    assert [row["localDate"] for row in download.json()["moods"]] == [str(kept_date)]
    from app.jobs.retention import purge_expired

    await purge_expired(app)
    await purge_expired(app)
    async with app.state.database.sessions() as db:
        assert (await db.scalars(select(Mood.local_date))).all() == [kept_date]


async def test_expired_human_messages_are_purged_without_deleting_current_messages(clients):
    app, actors, _, room = await open_room(clients)
    async with app.state.database.sessions.begin() as db:
        db.add_all(
            [
                HumanMessage(
                    connection_id=UUID(room),
                    sender_id=actors[0][1],
                    client_message_id=uuid4(),
                    seq=index,
                    text="retention canary",
                    created_at=timestamp,
                )
                for index, timestamp in enumerate((now() - timedelta(days=91), now()), 1)
            ]
        )
    from app.jobs.retention import purge_expired

    await purge_expired(app)
    async with app.state.database.sessions() as db:
        assert (await db.scalars(select(HumanMessage.seq))).all() == [2]


async def test_old_ai_run_metadata_is_purged_unless_a_saved_message_needs_it(clients):
    from uuid import uuid4

    from sqlalchemy import select

    from app.ai.models import AiConversation, AiMessageRecord
    from app.infrastructure.database.models import AiRun, now
    from app.jobs.retention import purge_expired

    app, actors = clients
    uid = actors[0][1]
    old = now() - timedelta(days=91)
    async with app.state.database.sessions.begin() as db:
        stale = AiRun(user_id=uid, conversation_id=uuid4(), bot_id="may", status="completed", created_at=old)
        recent = AiRun(user_id=uid, conversation_id=uuid4(), bot_id="may", status="completed")
        anchored = AiRun(user_id=uid, conversation_id=uuid4(), bot_id="may", status="completed", created_at=old)
        db.add_all([stale, recent, anchored])
        conversation = AiConversation(user_id=uid, bot_id="may", title="t", expires_at=now() + timedelta(days=1))
        db.add(conversation)
        await db.flush()
        db.add(AiMessageRecord(conversation_id=conversation.id, sequence=1, actor="self", text="x", cards=[], run_id=anchored.id))
    await purge_expired(app)
    async with app.state.database.sessions() as db:
        left = set((await db.scalars(select(AiRun.id).where(AiRun.user_id == uid))).all())
    assert left == {recent.id, anchored.id}
