"""Check-in execution E1–E5 with a scripted SDK model (P1-13/P1-14)."""

import asyncio
import json
from datetime import time, timedelta
from uuid import uuid4

from sqlalchemy import func, select, update

from app.jobs import proactive as worker
from tests.fakes import ScriptedModel, message_output


def reply(*texts, **extra):
    payload = {"messages": [{"text": text, "cards": []} for text in texts], **extra}
    return ScriptedModel([[message_output(json.dumps(payload, ensure_ascii=False))]])


def ready(app, model, **overrides):
    app.state.settings.proactive_enabled = True
    app.state.settings.proactive_worker_enabled = True
    app.state.ai.model_override = model
    for name, value in overrides.items():
        setattr(app.state.settings, name, value)


async def due_schedule(app, uid, *, bot="may", slot="morning", local_time=None, journal=False):
    from app.ai.proactive.models import AiProactiveSchedule, AiProactiveSettings
    from app.infrastructure.database.models import now

    async with app.state.database.sessions.begin() as db:
        prefs = await db.get(AiProactiveSettings, uid)
        if prefs is None:
            db.add(AiProactiveSettings(user_id=uid, timezone="Asia/Ho_Chi_Minh",
                                       journal_context_enabled=journal))
        db.add(AiProactiveSchedule(
            user_id=uid, bot_id=bot, slot=slot, enabled=True,
            local_time=local_time or (time(7, 30) if slot == "morning" else time(20, 0)),
            next_due_at=now() - timedelta(seconds=5),
        ))


async def tick(app):
    return await worker.proactive_tick(app.state.ai)


async def only_job(app, uid):
    from app.ai.proactive.models import AiProactiveJob

    async with app.state.database.sessions() as db:
        return (await db.scalars(select(AiProactiveJob).where(AiProactiveJob.user_id == uid))).one()


async def proactive_messages(app, uid):
    from app.ai.models import AiMessageRecord
    from app.infrastructure.database.models import AiRun

    async with app.state.database.sessions() as db:
        return (await db.execute(
            select(AiMessageRecord, AiRun).join(AiRun, AiRun.id == AiMessageRecord.run_id)
            .where(AiRun.user_id == uid, AiRun.origin == "proactive")
            .order_by(AiMessageRecord.sequence)
        )).all()


async def make_conversation(app, uid, *, bot="may", expires_in=timedelta(days=20), texts=()):
    from app.ai.models import AiConversation, AiMessageRecord
    from app.infrastructure.database.models import AiRun, now

    async with app.state.database.sessions.begin() as db:
        conversation = AiConversation(user_id=uid, bot_id=bot, expires_at=now() + expires_in, version=1)
        db.add(conversation)
        await db.flush()
        for text in texts:
            run = AiRun(id=uuid4(), user_id=uid, conversation_id=conversation.id, bot_id=bot,
                        status="completed")
            db.add(run)
            await db.flush()
            conversation.version += 1
            db.add(AiMessageRecord(conversation_id=conversation.id, sequence=conversation.version,
                                   actor="self", text=text, cards=[], run_id=run.id,
                                   created_at=now() - timedelta(hours=2)))
    return conversation.id


async def test_check_in_is_delivered_without_a_user_message_or_session(clients):
    from app.ai.models import AiConversation, AiTurn

    app, [(_client, uid), _] = clients
    model = reply("Sáng nay trời mát ghê.", "Chúc bạn một ngày nhẹ nhàng nha ☀")
    ready(app, model)
    await due_schedule(app, uid)
    assert (await tick(app))["claimed"] == 1
    job = await only_job(app, uid)
    assert job.status == "delivered" and job.run_id and job.conversation_id
    rows = await proactive_messages(app, uid)
    assert [(m.actor, m.part_index, m.part_count) for m, _ in rows] == [("bot", 0, 2), ("bot", 1, 2)]
    run = rows[0][1]
    assert (run.status, run.origin, run.proactive_slot, run.conversation_id) == (
        "completed", "proactive", "morning", job.conversation_id)
    async with app.state.database.sessions() as db:
        turn = await db.get(AiTurn, run.id)
        conversation = await db.get(AiConversation, job.conversation_id)
    assert turn.session_id is None and turn.origin == "proactive"
    assert turn.context_policy == "proactive-text-v1"
    assert conversation.title.startswith("Lời hỏi thăm buổi sáng")
    assert conversation.version == max(m.sequence for m, _ in rows)


async def test_model_input_is_one_data_item_without_transcript_or_tools(clients):
    app, [(_client, uid), _] = clients
    model = reply("Tối nay thế nào rồi? Muốn kể gì thì Mây nghe nha 🌙")
    ready(app, model)
    await make_conversation(app, uid, texts=["SECRET-TRANSCRIPT-CANARY"])
    await due_schedule(app, uid, slot="evening")
    await tick(app)
    [call] = model.calls
    sent = json.dumps(call["input"], ensure_ascii=False)
    assert "SECRET-TRANSCRIPT-CANARY" not in sent
    assert len(call["input"]) == 1 and call["input"][0]["role"] == "user"
    assert call["input"][0]["content"].startswith("Dữ liệu cho lời hỏi thăm")
    data = json.loads(call["input"][0]["content"].split(": ", 1)[1])
    assert data["companion"] == "may" and data["slot"] == "evening" and data["journal"] is None
    assert call["tools"] == []
    assert call["tracing"].name == "DISABLED" or "disabled" in str(call["tracing"]).lower()
    assert "LỜI HỎI THĂM" in call["instructions"]
    assert "16–17 tuổi" not in call["instructions"]


async def test_teen_instructions_add_the_age_layer(clients):
    from tests.conftest import add_actor

    app, _ = clients
    model = reply("Chào buổi sáng nha.")
    ready(app, model)
    _client, uid = await add_actor(app, 5, age_band="teen")
    await due_schedule(app, uid)
    await tick(app)
    assert "16–17 tuổi" in model.calls[0]["instructions"]


async def test_check_in_joins_the_latest_saved_conversation(clients):
    app, [(_client, uid), _] = clients
    ready(app, reply("Một lời chào nhỏ."))
    existing = await make_conversation(app, uid, texts=["chuyện cũ"])
    await due_schedule(app, uid)
    await tick(app)
    assert (await only_job(app, uid)).conversation_id == existing


async def test_conversation_expiring_soon_is_not_reused(clients):
    app, [(_client, uid), _] = clients
    ready(app, reply("Một lời chào nhỏ."))
    expiring = await make_conversation(app, uid, expires_in=timedelta(hours=24))
    await due_schedule(app, uid)
    await tick(app)
    job = await only_job(app, uid)
    assert job.status == "delivered" and job.conversation_id != expiring


async def test_recent_user_message_defers_without_spending_an_attempt(clients):
    from app.ai.models import AiMessageRecord
    from app.infrastructure.database.models import AiRun, now

    app, [(_client, uid), _] = clients
    model = reply("Một lời chào nhỏ.")
    ready(app, model)
    conversation = await make_conversation(app, uid, texts=["vừa nhắn"])
    async with app.state.database.sessions.begin() as db:
        await db.execute(update(AiMessageRecord).where(AiMessageRecord.conversation_id == conversation)
                         .values(created_at=now()))
    await due_schedule(app, uid)
    await tick(app)
    job = await only_job(app, uid)
    assert (job.status, job.attempts, job.last_error) == ("retry", 0, "active_chat")
    assert await proactive_messages(app, uid) == []
    async with app.state.database.sessions() as db:
        statuses = (await db.scalars(select(AiRun.status).where(AiRun.origin == "proactive"))).all()
    assert statuses == ["cancelled"]


async def test_running_chat_with_the_same_companion_defers_before_the_model(clients):
    from app.infrastructure.database.models import AiRun

    app, [(_client, uid), _] = clients
    model = reply("Một lời chào nhỏ.")
    ready(app, model)
    conversation = await make_conversation(app, uid)
    async with app.state.database.sessions.begin() as db:
        db.add(AiRun(user_id=uid, conversation_id=conversation, bot_id="may", status="running"))
    await due_schedule(app, uid)
    await tick(app)
    assert model.calls == []
    assert (await only_job(app, uid)).status == "retry"


async def test_unreceipted_claim_is_never_shown(clients):
    app, [(_client, uid), _] = clients
    ready(app, reply("Mình đã lưu lịch tập cho bạn rồi nhé."))
    await due_schedule(app, uid)
    await tick(app)
    job = await only_job(app, uid)
    assert (job.status, job.skip_reason) == ("skipped", "guardrail")
    assert await proactive_messages(app, uid) == []


async def test_invalid_output_retries_once_then_fails(clients):
    from app.ai.proactive.models import AiProactiveJob

    app, [(_client, uid), _] = clients
    model = reply("Bạn ngủ ngon không? Hôm nay định làm gì?")
    ready(app, model)
    await due_schedule(app, uid)
    await tick(app)
    job = await only_job(app, uid)
    assert (job.status, job.last_error) == ("retry", "too_many_questions")
    async with app.state.database.sessions.begin() as db:
        await db.execute(update(AiProactiveJob).values(available_at=func.now()))
    await tick(app)
    job = await only_job(app, uid)
    assert (job.status, job.last_error, job.attempts) == ("failed", "invalid_output", 2)
    assert len(model.calls) == 2
    assert await proactive_messages(app, uid) == []


class TimeoutModel(ScriptedModel):
    async def stream_response(self, *args, **kwargs):
        self.calls.append({"input": args[1]})
        raise TimeoutError()
        yield  # pragma: no cover


async def test_transient_provider_error_retries_with_backoff(clients):
    app, [(_client, uid), _] = clients
    ready(app, TimeoutModel([]))
    await due_schedule(app, uid)
    await tick(app)
    job = await only_job(app, uid)
    assert (job.status, job.last_error, job.attempts) == ("retry", "AI_TIMEOUT", 1)
    assert job.available_at > job.due_at + timedelta(seconds=50)


async def test_rure_avoids_recent_kinds_and_records_the_choice(clients):
    from app.ai.proactive.models import AiProactiveJob
    from app.infrastructure.database.models import AiRun, now

    app, [(_client, uid), _] = clients
    model = reply("Thử thách 5 phút: tìm 5 đồ vật màu xanh lá quanh bạn nhé 😄", challenge_kind="observation")
    ready(app, model)
    async with app.state.database.sessions.begin() as db:
        for days, kind in ((1, "riddle"), (2, "drawing")):
            run = AiRun(id=uuid4(), user_id=uid, bot_id="rure", status="completed", origin="proactive",
                        proactive_slot="evening")
            db.add(run)
            await db.flush()
            at = now() - timedelta(days=days)
            db.add(AiProactiveJob(user_id=uid, bot_id="rure", slot="evening",
                                  local_date=at.date(), due_at=at, expires_at=at + timedelta(hours=1),
                                  available_at=at, status="delivered", run_id=run.id, challenge_kind=kind,
                                  schedule_version=1, settings_version=1))
    await due_schedule(app, uid, bot="rure")
    await tick(app)
    data = json.loads(model.calls[0]["input"][0]["content"].split(": ", 1)[1])
    assert data["avoidChallengeKinds"] == ["riddle", "drawing"]
    async with app.state.database.sessions() as db:
        job = await db.scalar(select(AiProactiveJob).where(AiProactiveJob.slot == "morning"))
    assert job.status == "delivered" and job.challenge_kind == "observation"


async def test_rure_repeating_an_avoided_kind_is_regenerated(clients):
    from app.ai.proactive.models import AiProactiveJob
    from app.infrastructure.database.models import AiRun, now

    app, [(_client, uid), _] = clients
    ready(app, reply("Câu đố: cái gì càng lau càng ướt?", challenge_kind="riddle"))
    async with app.state.database.sessions.begin() as db:
        run = AiRun(id=uuid4(), user_id=uid, bot_id="rure", status="completed", origin="proactive",
                    proactive_slot="evening")
        db.add(run)
        await db.flush()
        at = now() - timedelta(days=1)
        db.add(AiProactiveJob(user_id=uid, bot_id="rure", slot="evening", local_date=at.date(),
                              due_at=at, expires_at=at + timedelta(hours=1), available_at=at,
                              status="delivered", run_id=run.id, challenge_kind="riddle",
                              schedule_version=1, settings_version=1))
    await due_schedule(app, uid, bot="rure")
    await tick(app)
    async with app.state.database.sessions() as db:
        job = await db.scalar(select(AiProactiveJob).where(AiProactiveJob.slot == "morning"))
    assert (job.status, job.last_error) == ("retry", "repeated_challenge")


async def test_caunoi_gets_only_own_counts_and_rejects_matching_claims(clients):
    from app.infrastructure.database.models import Consent

    app, [(_client, uid), _] = clients
    model = reply("Có một bạn hợp với bạn tới 92% đó!")
    ready(app, model)
    async with app.state.database.sessions.begin() as db:
        await db.execute(update(Consent).where(Consent.user_id == uid, Consent.purpose == "MATCH")
                         .values(enabled=True))
    await due_schedule(app, uid, bot="caunoi")
    await tick(app)
    data = json.loads(model.calls[0]["input"][0]["content"].split(": ", 1)[1])
    assert data["social"] == {"pendingIncomingRequests": 0, "hasPublishedProfile": False}
    job = await only_job(app, uid)
    assert (job.status, job.last_error) == ("retry", "matching_claim")


async def test_no_database_connection_is_held_during_the_model_call(clients):
    app, [(_client, uid), _] = clients
    model = reply("Một lời chào nhỏ.")
    model.hold = True
    ready(app, model)
    await due_schedule(app, uid)
    task = asyncio.create_task(tick(app))
    await asyncio.wait_for(model.started.wait(), 10)
    checked_out = app.state.database.engine.pool.checkedout()
    model.release.set()
    await task
    assert checked_out == 0
    assert (await only_job(app, uid)).status == "delivered"


async def test_schedule_change_during_generation_cancels_publication(clients):
    from app.ai.proactive.models import AiProactiveSchedule

    app, [(_client, uid), _] = clients
    model = reply("Một lời chào nhỏ.")
    model.hold = True
    ready(app, model)
    await due_schedule(app, uid)
    task = asyncio.create_task(tick(app))
    await asyncio.wait_for(model.started.wait(), 10)
    async with app.state.database.sessions.begin() as db:
        await db.execute(update(AiProactiveSchedule).values(version=AiProactiveSchedule.version + 1))
    model.release.set()
    await task
    job = await only_job(app, uid)
    assert (job.status, job.last_error) == ("cancelled", "version_changed")
    assert await proactive_messages(app, uid) == []


async def test_crash_during_publish_redelivers_exactly_once(clients, monkeypatch):
    from app.ai.proactive import executor
    from app.ai.proactive.models import AiProactiveJob
    from app.infrastructure.database.models import AiRun

    app, [(_client, uid), _] = clients
    model = reply("Một lời chào nhỏ.")
    ready(app, model)
    await due_schedule(app, uid)
    real = executor.publish
    calls = {"n": 0}

    async def flaky(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            raise ConnectionError("db went away")
        return await real(*args, **kwargs)

    monkeypatch.setattr(executor, "publish", flaky)
    await tick(app)
    assert (await only_job(app, uid)).status == "retry"
    async with app.state.database.sessions.begin() as db:
        await db.execute(update(AiProactiveJob).values(available_at=func.now()))
    await tick(app)
    job = await only_job(app, uid)
    assert job.status == "delivered" and len(model.calls) == 2
    assert len(await proactive_messages(app, uid)) == 1
    async with app.state.database.sessions() as db:
        statuses = sorted((await db.scalars(select(AiRun.status).where(AiRun.origin == "proactive"))).all())
    assert statuses == ["completed", "failed"]


async def test_accounting_records_proactive_usage_under_its_prompt_version(clients):
    from app.infrastructure.database.models import AiUsage

    app, [(_client, uid), _] = clients
    ready(app, reply("Một lời chào nhỏ."), ai_accounting_enabled=True)
    await due_schedule(app, uid)
    await tick(app)
    async with app.state.database.sessions() as db:
        usage = (await db.scalars(select(AiUsage))).one()
    assert usage.prompt_version.endswith("+proactive-2026-11-a8")
    assert usage.state == "settled" and usage.requests_started == 1


async def test_no_user_turn_or_quota_is_consumed(clients):
    from app.ai.models import AiMessageRecord

    app, [(client, uid), _] = clients
    ready(app, reply("Một lời chào nhỏ."))
    before = (await client.get("/api/v1/session")).json()["features"]["aiQuotaRemaining"]
    await due_schedule(app, uid)
    await tick(app)
    async with app.state.database.sessions() as db:
        assert await db.scalar(select(func.count()).select_from(AiMessageRecord)
                               .where(AiMessageRecord.actor == "self")) == 0
    assert (await client.get("/api/v1/session")).json()["features"]["aiQuotaRemaining"] == before


async def test_delivered_check_in_appears_in_the_conversation_api(clients):
    app, [(client, uid), _] = clients
    ready(app, reply("Một lời chào nhỏ."))
    await due_schedule(app, uid)
    await tick(app)
    job = await only_job(app, uid)
    view = (await client.get(f"/api/v1/ai/conversations/{job.conversation_id}")).json()
    [message] = view["messages"]
    assert (message["origin"], message["proactiveSlot"], message["actor"]) == ("proactive", "morning", "bot")
    events = await client.get(f"/api/v1/ai/runs/{job.run_id}/events")
    assert events.status_code == 404  # check-ins arrive through the conversation, not a stream


async def test_expired_attempt_cannot_publish_after_another_worker_reclaims(clients):
    from app.ai.proactive.models import AiProactiveJob
    from app.ai.runtime import AiRuntime
    from app.infrastructure.database.models import now

    app, [(_client, uid), _] = clients
    model = reply("Một lời chào nhỏ.")
    model.hold = True
    ready(app, model)
    await due_schedule(app, uid)
    task = asyncio.create_task(tick(app))
    await asyncio.wait_for(model.started.wait(), 10)
    # The first worker stalls past its lease; a second worker takes the job over.
    async with app.state.database.sessions.begin() as db:
        await db.execute(update(AiProactiveJob).values(lease_until=now() - timedelta(seconds=1)))
    other = AiRuntime(app.state.settings, app.state.database)
    async with worker.transaction(app.state.database) as db:
        reclaimed = await worker.claim_job(db, app.state.settings, other.worker_id, now())
    assert reclaimed is not None and reclaimed.attempts == 2
    model.release.set()
    await task
    assert await proactive_messages(app, uid) == []
    job = await only_job(app, uid)
    assert job.status == "running" and job.lease_token == reclaimed.lease_token


async def test_rure_mislabelled_activity_of_an_avoided_kind_is_regenerated(clients):
    from app.ai.proactive.models import AiProactiveJob
    from app.infrastructure.database.models import AiRun, now

    app, [(_client, uid), _] = clients
    # Declared word_play, but the activity is drawing, which was used yesterday.
    ready(app, reply("Thử dành 5 phút tô nguệch ngoạc vài hình tròn trên giấy nhé.", challenge_kind="word_play"))
    async with app.state.database.sessions.begin() as db:
        run = AiRun(id=uuid4(), user_id=uid, bot_id="rure", status="completed", origin="proactive",
                    proactive_slot="evening")
        db.add(run)
        await db.flush()
        at = now() - timedelta(days=1)
        db.add(AiProactiveJob(user_id=uid, bot_id="rure", slot="evening", local_date=at.date(),
                              due_at=at, expires_at=at + timedelta(hours=1), available_at=at,
                              status="delivered", run_id=run.id, challenge_kind="drawing",
                              schedule_version=1, settings_version=1))
    await due_schedule(app, uid, bot="rure")
    await tick(app)
    async with app.state.database.sessions() as db:
        job = await db.scalar(select(AiProactiveJob).where(AiProactiveJob.slot == "morning"))
    assert (job.status, job.last_error) == ("retry", "repeated_challenge")


async def test_filler_about_not_replying_is_regenerated(clients):
    app, [(_client, uid), _] = clients
    ready(app, reply("Chào buổi sáng! Không cần trả lời đâu nhé."))
    await due_schedule(app, uid)
    await tick(app)
    job = await only_job(app, uid)
    assert (job.status, job.last_error) == ("retry", "filler")


def test_filler_detection_is_narrow():
    from app.ai.proactive.output import has_filler

    for text in ("Không cần trả lời đâu.", "Bạn có thể bỏ qua câu hỏi này nhé.", "không cần phải trả lời mình",
                 "Không trả lời cũng được.", "Nếu không tiện thì bỏ qua nhé."):
        assert has_filler(text), text
    for text in ("Muốn kể gì thì Mây nghe, còn không thì cứ nghỉ ngơi nha.", "Trả lời câu đố trong đầu thôi.",
                 "Thử ghi lại một khoảnh khắc nếu muốn.", "Bỏ qua phần khó, chọn một từ dễ trước."):
        assert not has_filler(text), text
