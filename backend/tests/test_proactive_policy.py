"""Sessionless check-in authorization, E1 admission and quota separation (P1-11)."""

from datetime import date, time, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select, update

from tests.conftest import add_actor
from tests.fakes import make_test_model


def ready(app, **overrides):
    app.state.settings.proactive_enabled = True
    app.state.ai.model_override = make_test_model("ok")
    for name, value in overrides.items():
        setattr(app.state.settings, name, value)


async def seed(app, uid, *, bot="nhip", slot="morning", local_date=None, schedule=True, **job_fields):
    """Settings + schedule + one pending job for ``uid``; returns the job id."""
    from app.ai.proactive.models import AiProactiveJob, AiProactiveSchedule, AiProactiveSettings
    from app.infrastructure.database.models import now

    async with app.state.database.sessions.begin() as db:
        if await db.get(AiProactiveSettings, uid) is None:
            db.add(AiProactiveSettings(user_id=uid, timezone="Asia/Ho_Chi_Minh"))
        row = None
        if schedule:
            row = await db.scalar(select(AiProactiveSchedule).where(
                AiProactiveSchedule.user_id == uid, AiProactiveSchedule.bot_id == bot,
                AiProactiveSchedule.slot == slot))
            if row is None:
                row = AiProactiveSchedule(
                    user_id=uid, bot_id=bot, slot=slot, enabled=True,
                    local_time=time(7, 30) if slot == "morning" else time(20, 0),
                )
                db.add(row)
                await db.flush()
        at = now()
        job = AiProactiveJob(
            user_id=uid, schedule_id=row.id if row else None, bot_id=bot, slot=slot,
            local_date=local_date or date.today(), due_at=at, expires_at=at + timedelta(minutes=90),
            available_at=at, schedule_version=row.version if row else 1, settings_version=1,
            **job_fields,
        )
        db.add(job)
    return job.id


async def decide(app, job_id):
    from app.ai.proactive.models import AiProactiveJob
    from app.ai.proactive.policy import authorize_proactive

    async with app.state.database.sessions.begin() as db:
        job = await db.get(AiProactiveJob, job_id)
        return await authorize_proactive(db, app.state.settings, app.state.ai, job)


async def set_user(app, uid, **values):
    from app.infrastructure.database.models import User

    async with app.state.database.sessions.begin() as db:
        await db.execute(update(User).where(User.id == uid).values(**values))


async def test_eligible_user_is_authorized(clients):
    from app.ai.proactive.policy import Authorized

    app, [(_client, uid), _] = clients
    ready(app)
    await set_user(app, uid, last_seen_at=None)
    result = await decide(app, await seed(app, uid))
    # A freshly saved schedule counts as recent activity even without a session slide.
    assert isinstance(result, Authorized)
    assert result.user.id == uid and result.schedule.bot_id == "nhip"


@pytest.mark.parametrize(
    "values,outcome,reason",
    [
        ({"status": "deleted"}, "skip", "ineligible_account"),
        ({"deletion_pending": True}, "cancel", "deletion_pending"),
        ({"age_band": "under16"}, "skip", "ineligible_account"),
        ({"age_band": "unknown"}, "skip", "ineligible_account"),
    ],
)
async def test_account_matrix(clients, values, outcome, reason):
    app, [(_client, uid), _] = clients
    ready(app)
    job = await seed(app, uid)
    await set_user(app, uid, **values)
    result = await decide(app, job)
    assert (result.outcome, result.reason) == (outcome, reason)


async def test_suspended_account_is_skipped(clients):
    from app.infrastructure.database.models import now

    app, [(_client, uid), _] = clients
    ready(app)
    job = await seed(app, uid)
    await set_user(app, uid, suspended_until=now() + timedelta(days=1))
    assert (await decide(app, job)).reason == "ineligible_account"


async def test_guest_row_is_never_authorized(clients):
    from tests.guest_helpers import add_guest

    app, _ = clients
    ready(app)
    guest = await add_guest(app)
    job = await seed(app, guest.user_id)
    assert (await decide(app, job)).reason == "ineligible_account"


async def test_inactive_user_is_skipped(clients):
    from app.ai.proactive.models import AiProactiveSchedule
    from app.infrastructure.database.models import now

    app, [(_client, uid), _] = clients
    ready(app)
    job = await seed(app, uid)
    old = now() - timedelta(days=15)
    await set_user(app, uid, last_seen_at=old)
    async with app.state.database.sessions.begin() as db:
        await db.execute(update(AiProactiveSchedule).where(AiProactiveSchedule.user_id == uid)
                         .values(updated_at=old))
    assert (await decide(app, job)).reason == "inactive_user"


async def test_service_and_flag_conditions(clients):
    app, [(_client, uid), (_other, other_uid)] = clients
    ready(app)
    job = await seed(app, uid)
    app.state.settings.proactive_enabled = False
    assert (await decide(app, job)).reason == "disabled"
    ready(app, proactive_rollout_user_ids=[other_uid])
    assert (await decide(app, job)).reason == "disabled"
    ready(app, proactive_rollout_user_ids=[])
    app.state.ai.model_override = None
    assert (await decide(app, job)).reason == "ai_unavailable"
    ready(app, chat_history_enabled=False)
    assert (await decide(app, job)).reason == "no_history_capability"


async def test_schedule_state_conditions(clients):
    from app.ai.proactive.models import AiProactiveSchedule
    from app.infrastructure.database.models import now

    app, [(_client, uid), _] = clients
    ready(app)
    job = await seed(app, uid)

    async def schedule(**values):
        async with app.state.database.sessions.begin() as db:
            await db.execute(update(AiProactiveSchedule).where(AiProactiveSchedule.user_id == uid)
                             .values(**values))

    await schedule(paused_until=date.today())
    assert (await decide(app, job)).reason == "paused"
    await schedule(paused_until=None, auto_paused_at=now())
    assert (await decide(app, job)).reason == "auto_paused"
    await schedule(auto_paused_at=None, enabled=False)
    assert (await decide(app, job)).reason == "disabled"
    await schedule(enabled=True, version=2)
    result = await decide(app, job)
    assert (result.outcome, result.reason) == ("cancel", "version_changed")


async def test_orphaned_job_without_schedule_is_skipped(clients):
    app, [(_client, uid), _] = clients
    ready(app)
    job = await seed(app, uid, schedule=False)
    assert (await decide(app, job)).reason == "disabled"


async def test_caunoi_social_eligibility_is_rechecked(clients):
    from app.ai.proactive.policy import Authorized
    from app.infrastructure.database.models import Consent

    app, [(_client, uid), _] = clients
    ready(app)
    job = await seed(app, uid, bot="caunoi")
    assert (await decide(app, job)).reason == "ineligible_social"
    async with app.state.database.sessions.begin() as db:
        await db.execute(update(Consent).where(Consent.user_id == uid, Consent.purpose == "MATCH")
                         .values(enabled=True))
    assert isinstance(await decide(app, job), Authorized)
    # Global 18+: losing adult eligibility ends every check-in, social or not.
    await set_user(app, uid, age_band="teen")
    assert (await decide(app, job)).reason == "ineligible_account"


# --- quota separation ---------------------------------------------------------------------


async def add_run(app, uid, *, origin="proactive", status="running", bot="nhip", conversation_id=None):
    from app.infrastructure.database.models import AiRun

    async with app.state.database.sessions.begin() as db:
        run = AiRun(id=uuid4(), user_id=uid, bot_id=bot, status=status, origin=origin,
                    proactive_slot="morning" if origin == "proactive" else None,
                    conversation_id=conversation_id if origin == "proactive" else (conversation_id or uuid4()))
        db.add(run)
    return run.id


async def test_daily_turns_and_rate_count_only_user_runs(clients):
    from app.ai.persistence import admission, daily_turns
    from app.infrastructure.database.models import User, now

    app, [(_client, uid), _] = clients
    for _ in range(3):
        await add_run(app, uid, status="completed")
    await add_run(app, uid)  # running proactive run
    async with app.state.database.sessions.begin() as db:
        assert await daily_turns(db, uid, now()) == 0
        settings = app.state.settings.model_copy(update={
            "ai_user_concurrency": 1, "ai_requests_per_minute": 1, "ai_daily_turns_per_user": 1,
        })
        user = await db.get(User, uid)
        await admission(db, user, settings)  # proactive runs never block the user's own chat
    await add_run(app, uid, origin="user", status="completed")
    async with app.state.database.sessions.begin() as db:
        assert await daily_turns(db, uid, now()) == 1


async def test_global_concurrency_counts_proactive_runs(clients):
    from app.ai.persistence import admission
    from app.core.errors import DomainError
    from app.infrastructure.database.models import User

    app, [(_client, uid), (_other, other_uid)] = clients
    await add_run(app, other_uid)
    async with app.state.database.sessions.begin() as db:
        settings = app.state.settings.model_copy(update={"ai_global_concurrency": 1})
        with pytest.raises(DomainError) as error:
            await admission(db, await db.get(User, uid), settings)
    assert error.value.code == "RUN_LIMIT"


async def test_session_quota_ignores_proactive_runs(clients):
    app, [(client, uid), _] = clients
    app.state.ai.model_override = make_test_model("ok")
    before = (await client.get("/api/v1/session")).json()["features"]["aiQuotaRemaining"]
    await add_run(app, uid, status="completed")
    after = (await client.get("/api/v1/session")).json()["features"]["aiQuotaRemaining"]
    assert before == after


# --- E1 admission ----------------------------------------------------------------------


async def admit(app, job_id):
    from app.ai.proactive.models import AiProactiveJob
    from app.ai.proactive.policy import admit_proactive, authorize_proactive

    async with app.state.database.sessions.begin() as db:
        job = await db.get(AiProactiveJob, job_id)
        authorized = await authorize_proactive(db, app.state.settings, app.state.ai, job)
        return await admit_proactive(db, app.state.settings, authorized, job)


async def test_budget_share_skips_proactive_before_user_chat_budget(clients):
    from app.infrastructure.database.models import AiUsage

    app, [(_client, uid), _] = clients
    ready(app, ai_accounting_enabled=True, ai_daily_budget_usd=1.0, proactive_budget_share=0.5)
    run = await add_run(app, uid, origin="user", status="completed")
    async with app.state.database.sessions.begin() as db:
        from app.infrastructure.database.models import now

        db.add(AiUsage(run_id=run, user_id=uid, worker_id=uuid4(), model="m", prompt_version="p",
                       pricing_version="v", estimated_nano_usd=600_000_000, state="settled",
                       lease_until=now()))
    result = await admit(app, await seed(app, uid))
    assert (result.outcome, result.reason) == ("skip", "budget")


async def test_daily_delivery_cap(clients):
    app, [(_client, uid), _] = clients
    ready(app, proactive_daily_cap_per_user=2)
    for bot in ("may", "guong"):
        run = await add_run(app, uid, status="completed", bot=bot)
        await seed(app, uid, bot=bot, status="delivered", run_id=run)
    result = await admit(app, await seed(app, uid))
    assert (result.outcome, result.reason) == ("skip", "daily_cap")


async def test_active_chat_with_the_same_companion_defers(clients):
    app, [(_client, uid), _] = clients
    ready(app)
    await add_run(app, uid, origin="user", bot="nhip")
    result = await admit(app, await seed(app, uid))
    assert (result.outcome, result.reason) == ("defer", "active_chat")


async def test_capacity_defers_instead_of_skipping(clients):
    app, [(_client, uid), (_other, other_uid)] = clients
    ready(app, ai_global_concurrency=1)
    await add_run(app, other_uid, origin="user", bot="may")
    result = await admit(app, await seed(app, uid))
    assert (result.outcome, result.reason) == ("defer", "capacity")


async def deliver(app, uid, *, bot, local_date, read):
    """A delivered check-in whose single bubble the user has or has not opened."""
    from app.ai.models import AiConversation, AiMessageRecord
    from app.ai.proactive.models import AiConversationRead
    from app.infrastructure.database.models import now

    async with app.state.database.sessions.begin() as db:
        conversation = AiConversation(user_id=uid, bot_id=bot, expires_at=now() + timedelta(days=20),
                                      version=1)
        db.add(conversation)
        await db.flush()
    run = await add_run(app, uid, status="completed", bot=bot, conversation_id=conversation.id)
    async with app.state.database.sessions.begin() as db:
        db.add(AiMessageRecord(conversation_id=conversation.id, sequence=1, actor="bot", text="x",
                               cards=[], run_id=run))
        if read:
            db.add(AiConversationRead(conversation_id=conversation.id, user_id=uid, last_read_sequence=1))
    await seed(app, uid, bot=bot, local_date=local_date, status="delivered", run_id=run,
               conversation_id=conversation.id)


async def test_three_unopened_check_ins_auto_pause_the_companion(clients):
    from app.ai.proactive.models import AiProactiveSchedule

    app, [(_client, uid), _] = clients
    ready(app, proactive_daily_cap_per_user=6)
    for days in (3, 2, 1):
        await deliver(app, uid, bot="rure", local_date=date.today() - timedelta(days=days), read=False)
    result = await admit(app, await seed(app, uid, bot="rure"))
    assert (result.outcome, result.reason) == ("skip", "auto_paused")
    async with app.state.database.sessions() as db:
        row = await db.scalar(select(AiProactiveSchedule).where(
            AiProactiveSchedule.user_id == uid, AiProactiveSchedule.bot_id == "rure"))
    assert row.auto_paused_at is not None


async def test_one_opened_check_in_keeps_the_companion_active(clients):
    from app.ai.proactive.policy import Authorized

    app, [(_client, uid), _] = clients
    ready(app, proactive_daily_cap_per_user=6)
    for days, read in ((3, False), (2, True), (1, False)):
        await deliver(app, uid, bot="rure", local_date=date.today() - timedelta(days=days), read=read)
    job = await seed(app, uid, bot="rure")
    assert await admit(app, job) is None
    assert isinstance(await decide(app, job), Authorized)


async def test_under_18_accounts_get_no_check_ins_from_any_companion(clients):
    app, _ = clients
    ready(app)
    _client, uid = await add_actor(app, 9, age_band="teen")
    for bot in ("may", "nhip", "caunoi"):
        decision = await decide(app, await seed(app, uid, bot=bot))
        assert decision.outcome == "skip" and decision.reason == "ineligible_account"
