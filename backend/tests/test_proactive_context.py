"""A delivered check-in as context for the user's next chat turn (ADR-08, P1-14)."""

import json
from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import delete, select, update

from app.ai.context import ContextStamp, model_messages
from app.ai.schemas import AIMessage
from app.jobs import proactive as worker
from tests.fakes import make_test_model
from tests.test_proactive_executor import due_schedule, only_job, ready, reply
from tests.test_proactive_journal import entry, scripted


def message(run_id, actor="bot", text="x"):
    return AIMessage(id=uuid4(), actor=actor, text=text, created_at=datetime.now(UTC), run_id=run_id,
                     status="completed")


def test_policy_projection_rules():
    old, check_in, current = uuid4(), uuid4(), uuid4()
    messages = [message(old, "self", "old q"), message(old, text="old a"), message(check_in, text="check-in"),
                message(current, "self", "now")]
    text_stamps = {old: ContextStamp(1, "text-v1"), check_in: ContextStamp(1, "proactive-text-v1"),
                   current: ContextStamp(1, "text-v1")}
    assert [m.text for m in model_messages(messages, text_stamps, current_run=current, data_version=1)] == [
        "old q", "old a", "check-in", "now"]
    journal = {**text_stamps, check_in: ContextStamp(1, "proactive-journal-v1")}
    # Unrevalidated journal check-in is a boundary: it and everything older are cut.
    assert [m.text for m in model_messages(messages, journal, current_run=current, data_version=1)] == ["now"]
    assert [m.text for m in model_messages(messages, journal, current_run=current, data_version=1,
                                           revalidated=frozenset({check_in}))] == [
        "old q", "old a", "check-in", "now"]
    # A stale data_version still cuts a revalidated run.
    stale = {**journal, check_in: ContextStamp(0, "proactive-journal-v1")}
    assert [m.text for m in model_messages(messages, stale, current_run=current, data_version=1,
                                           revalidated=frozenset({check_in}))] == ["now"]


async def deliver_journal_check_in(app, uid, text="CHECKIN-CANARY sáng nay thử đi bộ 10 phút nhé."):
    ok = await entry(app, uid, text="đi bộ với bạn")
    ready(app, scripted(["Hôm qua bạn ghi là đi bộ với bạn.", text], [ok]))
    await due_schedule(app, uid, bot="nhip", journal=True)
    await worker.proactive_tick(app.state.ai)
    job = await only_job(app, uid)
    assert job.status == "delivered"
    return job, ok


async def chat(app, client, conversation_id, text="Cảm ơn nhé"):
    model = make_test_model("Không có gì.")
    app.state.ai.model_override = model
    url = f"/api/v1/ai/conversations/{conversation_id}"
    view = (await client.get(url)).json()
    accepted = await client.post(url + "/messages", json={
        "text": text, "clientMessageId": str(uuid4()), "expectedConversationVersion": view["version"]},
        headers={"Idempotency-Key": str(uuid4())})
    assert accepted.status_code == 202, accepted.text
    run = app.state.ai.runs[UUID(accepted.json()["runId"])]
    await run.task
    assert run.terminal_status == "completed"
    return json.dumps(model.calls[0]["input"], ensure_ascii=False), run.id


async def test_revalidated_journal_check_in_joins_the_next_turn(clients):
    from app.ai.models import AiTurn

    app, [(client, uid), _] = clients
    job, _entry = await deliver_journal_check_in(app, uid)
    sent, run_id = await chat(app, client, job.conversation_id)
    assert "CHECKIN-CANARY" in sent
    async with app.state.database.sessions() as db:
        # The turn that saw journal-derived prose is itself evidence-only for later turns.
        assert (await db.get(AiTurn, run_id)).context_policy == "journal-turn-v1"


async def test_edited_entry_cuts_the_check_in_from_context(clients):
    from app.modules.journal.models import JournalEntry

    app, [(client, uid), _] = clients
    job, ok = await deliver_journal_check_in(app, uid)
    async with app.state.database.sessions.begin() as db:
        await db.execute(update(JournalEntry).where(JournalEntry.id == ok).values(version=2))
    sent, _run = await chat(app, client, job.conversation_id)
    assert "CHECKIN-CANARY" not in sent


async def test_deleted_entry_cuts_the_check_in_from_context(clients):
    from app.modules.journal.models import JournalEntry

    app, [(client, uid), _] = clients
    job, ok = await deliver_journal_check_in(app, uid)
    async with app.state.database.sessions.begin() as db:
        await db.execute(delete(JournalEntry).where(JournalEntry.id == ok))
    sent, _run = await chat(app, client, job.conversation_id)
    assert "CHECKIN-CANARY" not in sent


async def test_switching_journal_use_off_and_on_never_restores_old_check_ins(clients):
    app, [(client, uid), _] = clients
    job, _ok = await deliver_journal_check_in(app, uid)
    base = {"timezone": "Asia/Ho_Chi_Minh", "quietStart": "22:00", "quietEnd": "07:00",
            "badgesEnabled": True, "policyVersion": "proactive-v1"}
    view = (await client.get("/api/v1/ai/proactive")).json()["settings"]
    off = await client.put("/api/v1/ai/proactive/settings", json={**base, "journalContextEnabled": False,
                           "expectedVersion": view["version"]}, headers={"Idempotency-Key": str(uuid4())})
    assert off.status_code == 200
    on = await client.put("/api/v1/ai/proactive/settings", json={**base, "journalContextEnabled": True,
                          "expectedVersion": off.json()["version"]}, headers={"Idempotency-Key": str(uuid4())})
    assert on.status_code == 200
    sent, _run = await chat(app, client, job.conversation_id)
    assert "CHECKIN-CANARY" not in sent


async def test_plain_check_in_joins_context_like_any_reply(clients):
    app, [(client, uid), _] = clients
    ready(app, reply("MAY-CHECKIN-CANARY Tối nay thế nào rồi?"))
    await due_schedule(app, uid, slot="evening")
    await worker.proactive_tick(app.state.ai)
    job = await only_job(app, uid)
    sent, _run = await chat(app, client, job.conversation_id, text="Cũng ổn")
    assert "MAY-CHECKIN-CANARY" in sent


async def test_chat_runs_and_check_ins_never_share_a_running_conversation(clients):
    """HD-05: publish sets conversation_id and completed in one statement."""
    from app.infrastructure.database.models import AiRun

    app, [(client, uid), _] = clients
    ready(app, reply("Một lời chào nhỏ."))
    await due_schedule(app, uid)
    await worker.proactive_tick(app.state.ai)
    job = await only_job(app, uid)
    async with app.state.database.sessions() as db:
        running = (await db.scalars(select(AiRun).where(AiRun.status == "running"))).all()
    assert running == []
    _sent, _run = await chat(app, client, job.conversation_id)
