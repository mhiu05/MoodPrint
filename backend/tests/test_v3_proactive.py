"""V3-04: check-ins for the three agents; legacy schedules preserved, paused and moved only explicitly."""

from datetime import date, time, timedelta

import pytest
from sqlalchemy import select

from tests.test_proactive_api import BASE, enable, find, key, put_schedule, settings_body
from tests.test_proactive_executor import (
    due_schedule,
    only_job,
    proactive_messages,
    ready,
    reply,
    tick,
)

pytestmark = pytest.mark.postgres


async def schedules(app, uid):
    from app.ai.proactive.models import AiProactiveSchedule

    async with app.state.database.sessions() as db:
        rows = (await db.scalars(select(AiProactiveSchedule).where(AiProactiveSchedule.user_id == uid))).all()
    return {(row.bot_id, row.slot): row for row in rows}


async def test_view_lists_the_three_agents_and_keeps_legacy_schedules_paused_and_movable(clients):
    app, [(client, uid), _] = clients
    enable(app)
    assert (await put_schedule(client, "nhip", "morning", localTime="07:30")).status_code == 200
    assert (await put_schedule(client, "caunoi", "evening", localTime="20:00", enabled=False)).status_code == 200
    app.state.settings.ai_three_agent_experience_enabled = True
    view = (await client.get(BASE)).json()
    pairs = [(s["botId"], s["slot"]) for s in view["schedules"]]
    assert pairs[:6] == [(bot, slot) for bot in ("nhatky", "hoatdong", "dieuphoi") for slot in ("morning", "evening")]
    # Only kept legacy rows follow; no default legacy entries are offered.
    assert pairs[6:] == [("nhip", "morning"), ("caunoi", "evening")]
    nhip = find(view, "nhip", "morning")
    assert nhip["legacy"] is True and nhip["migrateTo"] == "nhatky" and nhip["enabled"] is True
    assert nhip["eligibility"] == {"allowed": False, "reason": "legacy_companion"}
    assert nhip["nextDeliveryAt"] is None  # paused while V3 is on, never deleted
    assert find(view, "caunoi", "evening")["migrateTo"] is None
    # A kept legacy schedule does not use a slot of the daily cap.
    assert view["limits"]["enabledSlots"] == 0
    # It cannot be switched on again, but switching it off is always allowed.
    again = await put_schedule(client, "nhip", "morning", localTime="08:00", expectedVersion=1)
    assert again.status_code == 403
    off = await put_schedule(client, "caunoi", "evening", localTime="20:00", enabled=False, expectedVersion=1)
    assert off.status_code == 200
    # A V3 agent's schedule is created normally.
    created = await put_schedule(client, "hoatdong", "evening", localTime="20:00")
    assert created.status_code == 200 and created.json()["eligibility"]["allowed"] is True


async def test_explicit_migration_moves_time_and_state_and_switches_the_legacy_row_off(clients):
    app, [(client, uid), _] = clients
    enable(app)
    await put_schedule(client, "nhip", "morning", localTime="07:45", weekdays=[1, 3, 5])
    app.state.settings.ai_three_agent_experience_enabled = True
    moved = await client.post(f"{BASE}/schedules/nhip/morning/migrate", json={"expectedVersion": 1}, headers=key())
    assert moved.status_code == 200, moved.text
    body = moved.json()
    assert (body["botId"], body["localTime"], body["weekdays"], body["enabled"]) == ("nhatky", "07:45", [1, 3, 5], True)
    rows = await schedules(app, uid)
    assert rows[("nhip", "morning")].enabled is False and rows[("nhip", "morning")].next_due_at is None
    assert rows[("nhatky", "morning")].next_due_at is not None
    # Stale or repeated attempts never create a second schedule.
    again = await client.post(f"{BASE}/schedules/nhip/morning/migrate", json={"expectedVersion": 1}, headers=key())
    assert again.status_code == 409
    assert len(await schedules(app, uid)) == 2
    # Cầu Nối has no successor; it can only be switched off.
    await client.put(f"{BASE}/settings", json=settings_body(expectedVersion=1), headers=key())
    app.state.settings.ai_three_agent_experience_enabled = False
    from app.infrastructure.database.models import Consent

    async with app.state.database.sessions.begin() as db:
        consent = await db.scalar(select(Consent).where(Consent.user_id == uid, Consent.purpose == "MATCH"))
        consent.enabled = True
    assert (await put_schedule(client, "caunoi", "evening", localTime="20:00")).status_code == 200
    app.state.settings.ai_three_agent_experience_enabled = True
    refused = await client.post(f"{BASE}/schedules/caunoi/evening/migrate", json={"expectedVersion": 1},
                                headers=key())
    assert refused.status_code == 409 and refused.json()["error"]["code"] == "NO_SUCCESSOR"
    # The flag off: migration is unavailable (nothing moves silently).
    app.state.settings.ai_three_agent_experience_enabled = False
    assert (await client.post(f"{BASE}/schedules/rure/morning/migrate", json={"expectedVersion": 1},
                              headers=key())).status_code == 503


async def test_migration_after_todays_legacy_delivery_starts_tomorrow(clients):
    from app.ai.proactive.models import AiProactiveJob
    from app.ai.proactive.schedule import local_date
    from app.infrastructure.database.models import AiRun, now

    app, [(client, uid), _] = clients
    enable(app)
    assert (await put_schedule(client, "rure", "evening", localTime="21:00")).status_code == 200
    rows = await schedules(app, uid)
    today = local_date(now(), "Asia/Ho_Chi_Minh")
    async with app.state.database.sessions.begin() as db:
        run = AiRun(user_id=uid, conversation_id=None, bot_id="rure", status="completed", origin="proactive",
                    proactive_slot="evening")
        db.add(run)
        await db.flush()
        db.add(AiProactiveJob(user_id=uid, schedule_id=rows[("rure", "evening")].id, bot_id="rure", slot="evening",
                              local_date=today, due_at=now(), expires_at=now() + timedelta(hours=1),
                              available_at=now(), status="delivered", run_id=run.id, schedule_version=1,
                              settings_version=1))
    app.state.settings.ai_three_agent_experience_enabled = True
    moved = await client.post(f"{BASE}/schedules/rure/evening/migrate", json={"expectedVersion": 1}, headers=key())
    assert moved.status_code == 200, moved.text
    from zoneinfo import ZoneInfo

    due = (await schedules(app, uid))[("hoatdong", "evening")].next_due_at
    assert due.astimezone(ZoneInfo("Asia/Ho_Chi_Minh")).date() > today


async def test_worker_skips_a_kept_legacy_schedule_and_delivers_for_the_journal_agent(clients):
    app, [(_client, uid), _] = clients
    model = reply("Chào buổi sáng, hôm nay thử uống một ngụm nước ấm nhé.")
    ready(app, model, ai_three_agent_experience_enabled=True)
    await due_schedule(app, uid, bot="nhip")
    assert (await tick(app))["claimed"] == 1
    job = await only_job(app, uid)
    assert (job.status, job.skip_reason) == ("skipped", "legacy_companion")
    assert model.calls == []
    assert await proactive_messages(app, uid) == []


async def test_journal_agent_morning_reads_yesterday_only_under_the_same_setting(clients):
    from app.ai.proactive.models import AiProactiveJob
    from tests.collaboration_helpers import entry

    app, [(_client, uid), _] = clients
    entry_id = await entry(app, uid, days_ago=1, text="Hôm qua đi dạo công viên thấy nhẹ đầu")
    model = reply("Hôm qua bạn có ghi đi dạo công viên. Sáng nay thử ra ban công hít thở 5 phút nhé.",
                  source_entry_ids=[str(entry_id)])
    ready(app, model, ai_three_agent_experience_enabled=True)
    await due_schedule(app, uid, bot="nhatky", journal=True, local_time=time(7, 30))
    assert (await tick(app))["claimed"] == 1
    async with app.state.database.sessions() as db:
        job = (await db.scalars(select(AiProactiveJob).where(AiProactiveJob.user_id == uid))).one()
    assert job.status == "delivered", job.last_error
    sent = model.calls[0]["input"][0]["content"]
    assert "đi dạo công viên" in sent and '"companion": "nhatky"' in sent
    rows = await proactive_messages(app, uid)
    assert rows and rows[0][1].bot_id == "nhatky"


async def test_v3_agent_check_ins_never_run_with_the_experience_off(clients):
    app, [(_client, uid), _] = clients
    model = reply("Chào bạn!")
    ready(app, model)
    await due_schedule(app, uid, bot="dieuphoi")
    await tick(app)
    job = await only_job(app, uid)
    assert (job.status, job.skip_reason) == ("skipped", "agent_unavailable")
    assert model.calls == [] and isinstance(date.today(), date)
