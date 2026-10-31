"""Privacy around check-ins (P1-18): deletion mid-flight, content-free metadata tables."""

import asyncio

from sqlalchemy import text, update

from app.jobs import proactive as worker
from tests.test_proactive_executor import due_schedule, only_job, proactive_messages, ready, reply
from tests.test_proactive_journal import CANARY, entry, scripted


async def test_account_deletion_requested_during_generation_publishes_nothing(clients):
    from app.infrastructure.database.models import User

    app, [(_client, uid), _] = clients
    model = reply("Một lời chào nhỏ.")
    model.hold = True
    ready(app, model)
    await due_schedule(app, uid)
    task = asyncio.create_task(worker.proactive_tick(app.state.ai))
    await asyncio.wait_for(model.started.wait(), 10)
    async with app.state.database.sessions.begin() as db:
        await db.execute(update(User).where(User.id == uid).values(deletion_pending=True))
    model.release.set()
    await task
    job = await only_job(app, uid)
    assert (job.status, job.last_error) == ("cancelled", "deletion_pending")
    assert await proactive_messages(app, uid) == []


async def test_journal_text_never_lands_in_metadata_tables(clients):
    app, [(_client, uid), _] = clients
    ok = await entry(app, uid, text=f"điều riêng tư {CANARY}")
    ready(app, scripted(["Hôm qua bạn có ghi lại một điều nhỏ."], [ok]), ai_accounting_enabled=True)
    await due_schedule(app, uid, bot="nhip", journal=True)
    await worker.proactive_tick(app.state.ai)
    assert (await only_job(app, uid)).status == "delivered"
    async with app.state.database.sessions() as db:
        for table in ("ai_proactive_jobs", "ai_message_sources", "ai_usage", "ai_turns", "ai_runs",
                      "ai_proactive_settings", "ai_proactive_schedules", "ai_conversation_reads"):
            dump = await db.scalar(text(f"select coalesce(string_agg(t::text, ' '), '') from moodprint.{table} t"))
            assert CANARY not in dump, table
