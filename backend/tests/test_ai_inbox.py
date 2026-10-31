"""Unread check-ins and read markers (P1-15): counted per delivery, owner-only, no preview."""

import statistics
import time
from datetime import timedelta
from uuid import uuid4

from sqlalchemy import update

INBOX = "/api/v1/ai/inbox"


def key():
    return {"Idempotency-Key": str(uuid4())}


async def delivered(app, uid, *, bot="nhip", slot="morning", parts=1, expires_in=timedelta(days=20),
                    conversation_id=None, created_ago=timedelta(0)):
    """A completed check-in of ``parts`` bubbles; returns (conversation_id, run_id, first_sequence)."""
    from app.ai.models import AiConversation, AiMessageRecord
    from app.infrastructure.database.models import AiRun, now

    async with app.state.database.sessions.begin() as db:
        if conversation_id is None:
            conversation = AiConversation(user_id=uid, bot_id=bot, expires_at=now() + expires_in, version=1)
            db.add(conversation)
            await db.flush()
        else:
            conversation = await db.get(AiConversation, conversation_id)
        run = AiRun(id=uuid4(), user_id=uid, conversation_id=conversation.id, bot_id=bot, status="completed",
                    origin="proactive", proactive_slot=slot, created_at=now() - created_ago)
        db.add(run)
        await db.flush()
        first = conversation.version + 1
        for index in range(parts):
            db.add(AiMessageRecord(conversation_id=conversation.id, sequence=first + index, actor="bot",
                                   text=f"PRIVATE-TEXT-{index}", cards=[], run_id=run.id,
                                   part_index=index, part_count=parts))
        conversation.version += parts
    return conversation.id, run.id, first


def enable(app):
    from tests.fakes import make_test_model

    app.state.settings.proactive_enabled = True
    app.state.ai.model_override = make_test_model("ok")


async def test_three_bubbles_count_as_one_unread_without_preview(clients):
    app, [(client, uid), _] = clients
    enable(app)
    conversation, run, first = await delivered(app, uid, parts=3)
    view = (await client.get(INBOX)).json()
    assert view["unreadTotal"] == 1 and view["badgesEnabled"] is True
    [bot] = view["bots"]
    assert bot["botId"] == "nhip" and bot["unread"] == 1
    assert bot["latest"]["conversationId"] == str(conversation)
    assert bot["latest"]["runId"] == str(run) and bot["latest"]["firstSequence"] == first
    assert bot["latest"]["slot"] == "morning"
    assert "PRIVATE-TEXT" not in str(view)


async def test_read_marker_is_monotonic_and_clamped(clients):
    app, [(client, uid), _] = clients
    enable(app)
    conversation, _run, first = await delivered(app, uid, parts=2)
    url = f"/api/v1/ai/conversations/{conversation}/read"
    marked = await client.put(url, json={"lastReadSequence": 999}, headers=key())
    assert marked.status_code == 200
    assert marked.json() == {"conversationId": str(conversation), "lastReadSequence": first + 1}
    assert (await client.get(INBOX)).json()["unreadTotal"] == 0
    back = await client.put(url, json={"lastReadSequence": 1}, headers=key())
    assert back.json()["lastReadSequence"] == first + 1
    await delivered(app, uid, conversation_id=conversation)
    assert (await client.get(INBOX)).json()["unreadTotal"] == 1


async def test_partial_read_keeps_later_check_ins_unread(clients):
    app, [(client, uid), _] = clients
    enable(app)
    conversation, _r1, first = await delivered(app, uid)
    await delivered(app, uid, conversation_id=conversation, slot="evening")
    await client.put(f"/api/v1/ai/conversations/{conversation}/read", json={"lastReadSequence": first},
                     headers=key())
    view = (await client.get(INBOX)).json()
    assert view["unreadTotal"] == 1 and view["bots"][0]["latest"]["slot"] == "evening"


async def test_expired_and_old_conversations_are_not_counted(clients):
    from app.ai.models import AiConversation
    from app.infrastructure.database.models import now

    app, [(client, uid), _] = clients
    enable(app)
    conversation, _run, _first = await delivered(app, uid)
    await delivered(app, uid, bot="may", created_ago=timedelta(days=31))
    async with app.state.database.sessions.begin() as db:
        await db.execute(update(AiConversation).where(AiConversation.id == conversation)
                         .values(expires_at=now() - timedelta(minutes=1)))
    assert (await client.get(INBOX)).json()["unreadTotal"] == 0


async def test_replying_after_a_check_in_counts_as_read(clients):
    from app.ai.models import AiMessageRecord
    from app.infrastructure.database.models import AiRun

    app, [(client, uid), _] = clients
    enable(app)
    conversation, _run, first = await delivered(app, uid)
    async with app.state.database.sessions.begin() as db:
        run = AiRun(id=uuid4(), user_id=uid, conversation_id=conversation, bot_id="nhip", status="completed")
        db.add(run)
        await db.flush()
        db.add(AiMessageRecord(conversation_id=conversation, sequence=first + 1, actor="self", text="ừ",
                               cards=[], run_id=run.id))
    assert (await client.get(INBOX)).json()["unreadTotal"] == 0


async def test_user_initiated_replies_are_never_unread(clients):
    from app.ai.models import AiConversation, AiMessageRecord
    from app.infrastructure.database.models import AiRun, now

    app, [(client, uid), _] = clients
    enable(app)
    async with app.state.database.sessions.begin() as db:
        conversation = AiConversation(user_id=uid, bot_id="may", expires_at=now() + timedelta(days=5), version=2)
        db.add(conversation)
        await db.flush()
        run = AiRun(id=uuid4(), user_id=uid, conversation_id=conversation.id, bot_id="may", status="completed")
        db.add(run)
        await db.flush()
        db.add(AiMessageRecord(conversation_id=conversation.id, sequence=2, actor="bot", text="x", cards=[],
                               run_id=run.id))
    assert (await client.get(INBOX)).json()["unreadTotal"] == 0


async def test_another_users_conversation_is_not_found(clients):
    app, [(client, _uid), (_other, other_uid)] = clients
    enable(app)
    conversation, _run, _first = await delivered(app, other_uid)
    response = await client.put(f"/api/v1/ai/conversations/{conversation}/read",
                                json={"lastReadSequence": 3}, headers=key())
    assert response.status_code == 404
    assert (await client.get(INBOX)).json()["unreadTotal"] == 0


async def test_read_all_clears_every_unread_check_in(clients):
    app, [(client, uid), _] = clients
    enable(app)
    await delivered(app, uid)
    await delivered(app, uid, bot="rure")
    assert (await client.get(INBOX)).json()["unreadTotal"] == 2
    response = await client.post(f"{INBOX}/read-all", json={}, headers=key())
    assert response.status_code == 200 and response.json()["unreadTotal"] == 0
    assert (await client.get(INBOX)).json()["unreadTotal"] == 0


async def test_badges_setting_and_guest_and_flag(clients):
    from app.ai.proactive.models import AiProactiveSettings
    from tests.guest_helpers import add_guest

    app, [(client, uid), _] = clients
    await delivered(app, uid)
    assert (await client.get(INBOX)).json() == {"badgesEnabled": False, "unreadTotal": 0, "bots": []}
    enable(app)
    async with app.state.database.sessions.begin() as db:
        db.add(AiProactiveSettings(user_id=uid, timezone="Asia/Ho_Chi_Minh", badges_enabled=False))
    view = (await client.get(INBOX)).json()
    assert view["badgesEnabled"] is False and view["unreadTotal"] == 1
    guest = await add_guest(app)
    assert (await guest.client.get(INBOX)).json() == {"badgesEnabled": False, "unreadTotal": 0, "bots": []}


async def test_inbox_query_p95_under_50ms_with_500_conversations(clients):
    from app.ai.proactive.routes import inbox_rows

    app, [(_client, uid), _] = clients
    enable(app)
    for index in range(500):
        await delivered(app, uid, bot=("nhip", "rure", "may", "guong", "caunoi")[index % 5],
                        parts=1 + index % 3)
    from sqlalchemy import text

    async with app.state.database.engine.connect() as conn:
        # Autovacuum keeps statistics on a live database; a fresh bulk insert has none.
        await conn.execute(text("analyze moodprint.ai_runs, moodprint.ai_messages,"
                                " moodprint.ai_conversations, moodprint.ai_conversation_reads"))
        await conn.commit()
    durations = []
    async with app.state.database.sessions() as db:
        for _ in range(25):
            started = time.perf_counter()
            rows = await inbox_rows(db, uid)
            durations.append((time.perf_counter() - started) * 1000)
    assert sum(row.unread for row in rows) == 500 and len(rows) == 5
    p95 = statistics.quantiles(durations, n=20)[-1]
    print(f"inbox_rows p50={statistics.median(durations):.1f}ms p95={p95:.1f}ms")
    assert p95 < 50
