"""Check-in settings and schedule API (P1-10): validation, authorization, cancellation."""

from datetime import date, time, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select, update

from tests.conftest import add_actor

BASE = "/api/v1/ai/proactive"


def key():
    return {"Idempotency-Key": str(uuid4())}


def enable(app, **overrides):
    from tests.fakes import make_test_model

    app.state.settings.proactive_enabled = True
    app.state.ai.model_override = make_test_model("ok")
    for name, value in overrides.items():
        setattr(app.state.settings, name, value)


def schedule_body(**fields):
    body = {"enabled": True, "localTime": "07:30", "weekdays": [1, 2, 3, 4, 5, 6, 7],
            "pausedUntil": None, "expectedVersion": 0}
    body.update(fields)
    return body


async def put_schedule(client, bot="nhip", slot="morning", headers=None, **fields):
    return await client.put(f"{BASE}/schedules/{bot}/{slot}", json=schedule_body(**fields),
                            headers=headers or key())


def settings_body(**fields):
    body = {"timezone": "Asia/Ho_Chi_Minh", "quietStart": "22:00", "quietEnd": "07:00",
            "badgesEnabled": True, "journalContextEnabled": False, "expectedVersion": 0,
            "policyVersion": "proactive-v1"}
    body.update(fields)
    return body


async def db_rows(app, model, **where):
    async with app.state.database.sessions() as db:
        statement = select(model)
        for name, value in where.items():
            statement = statement.where(getattr(model, name) == value)
        return (await db.scalars(statement)).all()


def find(view, bot, slot):
    return next(s for s in view["schedules"] if s["botId"] == bot and s["slot"] == slot)


async def test_feature_flag_off_reads_unavailable_and_rejects_writes(clients):
    app, [(client, _uid), _] = clients
    response = await client.get(BASE)
    assert response.status_code == 200
    assert response.json()["available"] is False
    response = await put_schedule(client)
    assert response.status_code == 503 and response.json()["error"]["code"] == "PROACTIVE_UNAVAILABLE"


async def test_defaults_list_every_companion_and_slot(clients):
    app, [(client, _uid), _] = clients
    enable(app)
    view = (await client.get(BASE)).json()
    assert view["available"] is True
    assert len(view["schedules"]) == 10
    assert all(s["version"] == 0 and s["enabled"] is False for s in view["schedules"])
    assert find(view, "nhip", "morning")["localTime"] == "07:30"
    assert find(view, "may", "evening")["localTime"] == "20:00"
    assert view["settings"]["version"] == 0
    assert view["settings"]["timezone"] == "Asia/Bangkok"  # account timezone default
    assert view["settings"]["journalContextEnabled"] is False
    assert view["limits"] == {"dailyCap": 4, "enabledSlots": 0, "stepMinutes": 15,
                              "windows": {"morning": ["05:00", "11:30"], "evening": ["17:00", "22:30"]}}
    caunoi = find(view, "caunoi", "evening")
    assert caunoi["eligibility"] == {"allowed": False, "reason": "social_not_enabled"}
    assert find(view, "nhip", "evening")["eligibility"] == {"allowed": True, "reason": None}


async def test_create_schedule_computes_next_delivery_and_creates_settings(clients):
    from app.ai.proactive.models import AiProactiveSchedule, AiProactiveSettings
    from app.infrastructure.database.models import User

    app, [(client, uid), _] = clients
    enable(app)
    response = await put_schedule(client, weekdays=[1, 2, 3, 4, 5])
    assert response.status_code == 200, response.text
    view = response.json()
    assert view["enabled"] is True and view["version"] == 1
    assert view["weekdays"] == [1, 2, 3, 4, 5]
    assert view["nextDeliveryAt"] is not None
    [row] = await db_rows(app, AiProactiveSchedule, user_id=uid)
    assert row.weekdays == 31 and row.local_time == time(7, 30) and row.next_due_at is not None
    [prefs] = await db_rows(app, AiProactiveSettings, user_id=uid)
    assert prefs.timezone == "Asia/Bangkok" and prefs.version == 1
    [user] = await db_rows(app, User, id=uid)
    assert user.last_seen_at is not None
    assert (await client.get(BASE)).json()["limits"]["enabledSlots"] == 1


async def test_stale_version_and_idempotent_replay(clients):
    app, [(client, _uid), _] = clients
    enable(app)
    headers = key()
    first = await put_schedule(client, headers=headers)
    replay = await put_schedule(client, headers=headers)
    assert replay.status_code == 200 and replay.json()["version"] == first.json()["version"] == 1
    stale = await put_schedule(client, expectedVersion=0, localTime="08:00")
    assert stale.status_code == 409 and stale.json()["error"]["code"] == "STALE_VERSION"
    moved = await put_schedule(client, expectedVersion=1, localTime="08:00")
    assert moved.status_code == 200 and moved.json()["version"] == 2
    assert moved.json()["localTime"] == "08:00"


@pytest.mark.parametrize("value", ["04:45", "11:45", "07:10", "25:00", "7:30"])
async def test_schedule_window_and_step(clients, value):
    app, [(client, _uid), _] = clients
    enable(app)
    response = await put_schedule(client, localTime=value)
    assert response.status_code == 422
    if value in ("04:45", "11:45", "07:10"):
        assert response.json()["error"]["code"] == "SCHEDULE_WINDOW"


async def test_under_18_account_cannot_use_proactive_schedules(clients):
    app, _ = clients
    enable(app)
    client, _uid = await add_actor(app, 7, age_band="teen")
    # Global 18+: the whole surface is refused before any schedule rule is evaluated.
    assert (await client.get(BASE)).status_code == 403
    denied = await put_schedule(client, bot="may", slot="evening", localTime="20:00")
    assert denied.status_code == 403 and denied.json()["error"]["code"] == "ELIGIBILITY_REQUIRED"


async def test_schedule_inside_quiet_hours_is_rejected(clients):
    app, [(client, _uid), _] = clients
    enable(app)
    response = await put_schedule(client, bot="may", slot="evening", localTime="22:15")
    assert response.status_code == 422 and response.json()["error"]["code"] == "SCHEDULE_IN_QUIET_HOURS"
    # Disabled schedules may keep any in-window time; only enabled ones must avoid quiet hours.
    response = await put_schedule(client, bot="may", slot="evening", localTime="22:15", enabled=False)
    assert response.status_code == 200


async def test_daily_cap_blocks_the_fifth_enabled_slot(clients):
    app, [(client, _uid), _] = clients
    enable(app)
    for bot, slot in (("nhip", "morning"), ("nhip", "evening"), ("may", "morning"), ("may", "evening")):
        time_value = "07:30" if slot == "morning" else "20:00"
        assert (await put_schedule(client, bot=bot, slot=slot, localTime=time_value)).status_code == 200
    blocked = await put_schedule(client, bot="rure")
    assert blocked.status_code == 409 and blocked.json()["error"]["code"] == "PROACTIVE_DAILY_CAP"
    # A disabled schedule can still be saved, and updating an enabled one is not a fifth slot.
    assert (await put_schedule(client, bot="rure", enabled=False)).status_code == 200
    assert (await put_schedule(client, expectedVersion=1, localTime="08:00")).status_code == 200


async def test_caunoi_requires_adult_match(clients):
    from app.infrastructure.database.models import Consent, User, now

    app, [(client, uid), _] = clients
    enable(app)
    denied = await put_schedule(client, bot="caunoi")
    assert denied.status_code == 403 and denied.json()["error"]["code"] == "PROACTIVE_INELIGIBLE"
    async with app.state.database.sessions.begin() as db:
        await db.execute(update(Consent).where(Consent.user_id == uid, Consent.purpose == "MATCH")
                         .values(enabled=True))
    assert (await put_schedule(client, bot="caunoi")).status_code == 200
    async with app.state.database.sessions.begin() as db:
        await db.execute(update(User).where(User.id == uid)
                         .values(social_restricted_until=now() + timedelta(days=1)))
    view = (await client.get(BASE)).json()
    assert find(view, "caunoi", "morning")["eligibility"]["reason"] == "social_restricted"


async def test_history_capability_required(clients):
    app, [(client, _uid), _] = clients
    enable(app, chat_history_enabled=False)
    view = (await client.get(BASE)).json()
    assert find(view, "nhip", "morning")["eligibility"]["reason"] == "history_unavailable"
    response = await put_schedule(client)
    assert response.status_code == 403 and response.json()["error"]["code"] == "PROACTIVE_INELIGIBLE"


async def test_guest_and_underage_are_denied(clients):
    from tests.guest_helpers import add_guest

    app, _ = clients
    enable(app)
    guest = await add_guest(app)
    response = await guest.client.get(BASE)
    assert response.status_code == 403 and response.json()["error"]["code"] == "REGISTERED_REQUIRED"
    child, _uid = await add_actor(app, 8, age_band="under16")
    response = await child.get(BASE)
    assert response.status_code == 403 and response.json()["error"]["code"] == "ELIGIBILITY_REQUIRED"


async def test_rollout_cohort_limits_availability(clients):
    app, [(client, _uid), (other, other_uid)] = clients
    enable(app, proactive_rollout_user_ids=[other_uid])
    assert (await client.get(BASE)).json()["available"] is False
    assert (await put_schedule(client)).status_code == 503
    assert (await other.get(BASE)).json()["available"] is True


async def seed_pending_job(app, uid, bot="nhip", slot="morning"):
    from app.ai.proactive.models import AiProactiveJob, AiProactiveSchedule
    from app.infrastructure.database.models import now

    async with app.state.database.sessions.begin() as db:
        schedule = await db.scalar(select(AiProactiveSchedule).where(
            AiProactiveSchedule.user_id == uid, AiProactiveSchedule.bot_id == bot,
            AiProactiveSchedule.slot == slot))
        at = now()
        job = AiProactiveJob(user_id=uid, schedule_id=schedule.id if schedule else None, bot_id=bot,
                             slot=slot, local_date=date.today(), due_at=at,
                             expires_at=at + timedelta(minutes=90), available_at=at,
                             schedule_version=schedule.version if schedule else 1, settings_version=1)
        db.add(job)
    return job.id


async def job_status(app, job_id):
    from app.ai.proactive.models import AiProactiveJob

    [job] = await db_rows(app, AiProactiveJob, id=job_id)
    return job.status


async def test_editing_or_deleting_a_schedule_cancels_unstarted_jobs(clients):
    from app.ai.proactive.models import AiProactiveSchedule

    app, [(client, uid), _] = clients
    enable(app)
    await put_schedule(client)
    job = await seed_pending_job(app, uid)
    assert (await put_schedule(client, expectedVersion=1, localTime="09:00")).status_code == 200
    assert await job_status(app, job) == "cancelled"
    response = await client.request("DELETE", f"{BASE}/schedules/nhip/morning",
                                    json={"expectedVersion": 1}, headers=key())
    assert response.status_code == 409  # stale: the edit made it version 2
    response = await client.request("DELETE", f"{BASE}/schedules/nhip/morning",
                                    json={"expectedVersion": 2}, headers=key())
    assert response.status_code == 200 and response.json()["resourceVersion"] == 2
    assert await db_rows(app, AiProactiveSchedule, user_id=uid) == []
    missing = await client.request("DELETE", f"{BASE}/schedules/nhip/morning",
                                   json={"expectedVersion": 2}, headers=key())
    assert missing.status_code == 404


async def test_pause_until_and_resume_from_auto_pause(clients):
    from app.ai.proactive.models import AiProactiveSchedule
    from app.infrastructure.database.models import now

    app, [(client, uid), _] = clients
    enable(app)
    await put_schedule(client)
    paused = await put_schedule(client, expectedVersion=1,
                                pausedUntil=(date.today() + timedelta(days=3)).isoformat())
    assert paused.status_code == 200 and paused.json()["pausedUntil"] is not None
    too_far = await put_schedule(client, expectedVersion=2,
                                 pausedUntil=(date.today() + timedelta(days=45)).isoformat())
    assert too_far.status_code == 422
    async with app.state.database.sessions.begin() as db:
        await db.execute(update(AiProactiveSchedule).where(AiProactiveSchedule.user_id == uid)
                         .values(auto_paused_at=now()))
    view = find((await client.get(BASE)).json(), "nhip", "morning")
    assert view["autoPaused"] is True and view["nextDeliveryAt"] is None
    resumed = await put_schedule(client, expectedVersion=2, pausedUntil=None)
    assert resumed.json()["autoPaused"] is False and resumed.json()["nextDeliveryAt"] is not None


async def test_settings_validation_and_quiet_conflict(clients):
    app, [(client, _uid), _] = clients
    enable(app)
    bad_zone = await client.put(f"{BASE}/settings", json=settings_body(timezone="Mars/Base"), headers=key())
    assert bad_zone.status_code == 422 and bad_zone.json()["error"]["code"] == "INVALID_TIMEZONE"
    short = await client.put(f"{BASE}/settings", json=settings_body(quietStart="22:00", quietEnd="01:00"),
                             headers=key())
    assert short.status_code == 422 and short.json()["error"]["code"] == "QUIET_HOURS_INVALID"
    await put_schedule(client, bot="may", slot="evening", localTime="21:00")
    conflict = await client.put(f"{BASE}/settings", json=settings_body(quietStart="20:30", quietEnd="07:00", expectedVersion=1),
                                headers=key())
    assert conflict.status_code == 409 and conflict.json()["error"]["code"] == "SCHEDULE_IN_QUIET_HOURS"
    saved = await client.put(f"{BASE}/settings", json=settings_body(expectedVersion=1), headers=key())
    assert saved.status_code == 200 and saved.json()["version"] == 2
    stale = await client.put(f"{BASE}/settings", json=settings_body(expectedVersion=1), headers=key())
    assert stale.status_code == 409 and stale.json()["error"]["code"] == "STALE_VERSION"


async def test_timezone_change_recomputes_schedules_and_cancels_jobs(clients):
    from app.ai.proactive.models import AiProactiveSchedule

    app, [(client, uid), _] = clients
    enable(app)
    await put_schedule(client)
    [before] = await db_rows(app, AiProactiveSchedule, user_id=uid)
    job = await seed_pending_job(app, uid)
    response = await client.put(f"{BASE}/settings", json=settings_body(timezone="Asia/Tokyo", expectedVersion=1),
                                headers=key())
    assert response.status_code == 200
    [after] = await db_rows(app, AiProactiveSchedule, user_id=uid)
    assert after.next_due_at != before.next_due_at
    assert (after.next_due_at - before.next_due_at) % timedelta(hours=1) == timedelta(0)
    assert await job_status(app, job) == "cancelled"


async def test_journal_consent_requires_policy_and_revocation_bumps_versions(clients):
    from app.ai.proactive.models import AiProactiveSettings
    from app.infrastructure.database.models import User

    app, [(client, uid), _] = clients
    enable(app)
    on = await client.put(f"{BASE}/settings", json=settings_body(journalContextEnabled=True), headers=key())
    assert on.status_code == 200 and on.json()["journalContextEnabled"] is True
    await put_schedule(client)
    job = await seed_pending_job(app, uid)
    other_job = await seed_pending_job(app, uid, bot="may", slot="evening")
    [user_before] = await db_rows(app, User, id=uid)
    off = await client.put(f"{BASE}/settings", json=settings_body(expectedVersion=1), headers=key())
    assert off.status_code == 200 and off.json()["journalContextEnabled"] is False
    [prefs] = await db_rows(app, AiProactiveSettings, user_id=uid)
    [user_after] = await db_rows(app, User, id=uid)
    assert prefs.journal_context_version == 1
    assert user_after.data_version == user_before.data_version + 1
    assert await job_status(app, job) == "cancelled"
    # Turning journal use off cancels only Nhịp; other companions keep today's check-in.
    assert await job_status(app, other_job) == "pending"


async def test_session_exposes_proactive_feature(clients):
    from tests.fakes import make_test_model

    app, [(client, _uid), _] = clients
    assert (await client.get("/api/v1/session")).json()["features"]["proactive"] is False
    enable(app)
    app.state.ai.model_override = make_test_model("ok")
    assert (await client.get("/api/v1/session")).json()["features"]["proactive"] is True
    app.state.settings.chat_history_enabled = False
    assert (await client.get("/api/v1/session")).json()["features"]["proactive"] is False


def test_worker_flag_requires_accounting_and_budget_in_production():
    from pydantic import ValidationError

    from app.core.config import Settings

    base = dict(
        _env_file=None, app_env="production", frontend_origin="https://moodprint.example",
        supabase_url="https://project.supabase.co", supabase_publishable_key="sb_publishable_x",
        database_url="postgresql://u:p@db.example:5432/postgres", ai_enabled=True,
        openai_api_key="sk-test", openai_model="gpt-6-luna",
    )
    with pytest.raises(ValidationError):
        Settings(**base, proactive_worker_enabled=True, proactive_enabled=True)
    Settings(**base, proactive_worker_enabled=True, proactive_enabled=True,
             ai_accounting_enabled=True, ai_daily_budget_usd=5)
