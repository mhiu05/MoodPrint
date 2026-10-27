"""Durable cleanup and orphan reconciliation: crashes, leases, retries, markers, flags (GE-06.2)."""

import asyncio
import json
from datetime import timedelta
from uuid import uuid4

import pytest
from sqlalchemy import func, select, text, update

from tests.guest_helpers import (
    FakeGuestProvider,
    add_guest,
    db_now,
    enable_guest_entry,
    open_intent,
    post_guest,
    public_client,
)
from tests.test_guest_cleanup import claim, provider_rows, seed_owned, user_reference_counts

pytestmark = pytest.mark.postgres
LIFETIME = timedelta(seconds=7200)


async def job_of(app, user_id):
    from app.modules.guests.models import GuestCleanupJob

    async with app.state.database.sessions() as db:
        return await db.get(GuestCleanupJob, user_id)


async def make_due(app, user_id):
    from app.modules.guests.models import GuestCleanupJob

    async with app.state.database.sessions.begin() as db:
        await db.execute(
            update(GuestCleanupJob)
            .where(GuestCleanupJob.user_id == user_id)
            .values(next_attempt_at=func.clock_timestamp() - timedelta(seconds=1))
        )


async def test_worker_crash_rolls_back_then_retries(clients, monkeypatch):
    from app.modules.guests import jobs, lifecycle

    app, actors = clients
    guest = await add_guest(app, started_ago=LIFETIME + timedelta(seconds=5), consents=True)
    await seed_owned(app, guest.user_id, peer=actors[1][1], guest=True)
    before = await user_reference_counts(app, guest.user_id)

    async def crash_after_deleting(db, user_id, token):
        result = await lifecycle.purge_guest(db, user_id, token)
        assert result == "removed"
        raise RuntimeError("process died before commit")

    monkeypatch.setattr(jobs, "purge_guest", crash_after_deleting)
    assert await jobs.process_guest_cleanup(app) == 0
    assert await user_reference_counts(app, guest.user_id) == before, "whole transaction rolled back"
    job = await job_of(app, guest.user_id)
    assert job.state == "retry" and job.attempts == 1 and job.lease_token is None
    assert job.last_error == "purge_failed" and job.next_attempt_at > await db_now(app)
    assert (await guest.client.get("/api/v1/session")).status_code == 401

    # Not due yet: no work. Once due, the unpatched purge completes everything.
    assert await jobs.process_guest_cleanup(app) == 0
    monkeypatch.undo()
    await make_due(app, guest.user_id)
    assert await jobs.process_guest_cleanup(app) == 1
    assert sum((await user_reference_counts(app, guest.user_id)).values()) == 0
    assert await provider_rows(app, guest.user_id) == (0, 0)


async def test_lost_lease_cannot_finish_cleanup(clients):
    from app.modules.guests import jobs
    from app.modules.guests.models import GuestCleanupJob

    app, _ = clients
    guest = await add_guest(app, started_ago=LIFETIME + timedelta(seconds=5))
    stale = await claim(app, guest)
    async with app.state.database.sessions.begin() as db:  # the lease expires; another worker takes over
        await db.execute(
            update(GuestCleanupJob)
            .where(GuestCleanupJob.user_id == guest.user_id)
            .values(lease_until=func.clock_timestamp() - timedelta(seconds=1))
        )
    claimed = await jobs._claim_cleanup(app)
    assert claimed is not None and claimed[0] == guest.user_id and claimed[1] != stale
    from app.modules.guests.lifecycle import purge_guest

    async with app.state.database.sessions.begin() as db:
        assert await purge_guest(db, guest.user_id, stale) == "fenced"
    assert (await user_reference_counts(app, guest.user_id))["auth_sessions.user_id"] == 1
    async with app.state.database.sessions.begin() as db:
        assert await purge_guest(db, guest.user_id, claimed[1]) == "removed"


async def test_failure_never_reactivates_guest(clients, monkeypatch):
    from app.infrastructure.database.models import User
    from app.modules.guests import jobs

    app, _ = clients
    for flag in ("guest_auth_enabled", "guest_paid_enabled", "feedback_enabled"):
        assert getattr(app.state.settings, flag) is False
    guest = await add_guest(app, started_ago=LIFETIME + timedelta(seconds=5), consents=True)
    async with app.state.database.sessions() as db:
        original = await db.get(User, guest.user_id)
        original = (original.account_kind, original.guest_started_at, original.guest_expires_at)

    async def always_fails(db, user_id, token):
        raise RuntimeError("helper unavailable")

    monkeypatch.setattr(jobs, "purge_guest", always_fails)
    for attempt in range(1, 8):
        await make_due(app, guest.user_id)
        await jobs.process_guest_cleanup(app)
        job = await job_of(app, guest.user_id)
        assert job.state == "retry" and job.attempts == attempt
        response = await guest.client.get("/api/v1/session")
        assert response.status_code == 401 and response.json()["error"]["code"] == "GUEST_EXPIRED"
    assert job.alerted_at is not None, "exhausted automatic retries raise an alert"
    assert job.next_attempt_at - await db_now(app) > timedelta(minutes=30), "then hourly, never abandoned"
    async with app.state.database.sessions() as db:
        user = await db.get(User, guest.user_id)
    assert (user.account_kind, user.guest_started_at, user.guest_expires_at) == original
    assert user.account_kind == "guest"
    assert jobs.retry_delay(1) == 5 and jobs.retry_delay(5) == 900 and jobs.retry_delay(6) == 3600


async def test_incident_jobs_are_never_reclaimed(clients):
    from app.modules.guests import jobs
    from app.modules.guests.models import GuestCleanupJob

    app, _ = clients
    guest = await add_guest(app, started_ago=LIFETIME + timedelta(seconds=5))
    async with app.state.database.sessions.begin() as db:
        await db.execute(
            update(GuestCleanupJob)
            .where(GuestCleanupJob.user_id == guest.user_id)
            .values(state="incident_required", alerted_at=func.clock_timestamp())
        )
    assert await jobs._claim_cleanup(app) is None
    assert (await guest.client.get("/api/v1/session")).status_code == 401


async def orphan_attempt(app, mode="timeout"):
    """A real attempt whose provider signup created an identity the application never mapped."""
    enable_guest_entry(app)
    provider = FakeGuestProvider(app, mode)
    browser = public_client(app)
    await open_intent(browser)
    response = await post_guest(browser, str(uuid4()))
    assert response.status_code == 409
    from app.modules.guests.models import GuestProvisioningAttempt

    async with app.state.database.sessions() as db:
        attempt = (await db.scalars(select(GuestProvisioningAttempt))).one()
    return provider, attempt


async def test_marker_recovers_crash_before_subject_persist(clients):
    from app.modules.guests import jobs
    from app.modules.guests.models import GuestProvisioningAttempt

    app, _ = clients
    canary = uuid4()
    async with app.state.database.sessions.begin() as db:
        await db.execute(text("insert into auth.users(id,is_anonymous) values (:id,false)"), {"id": canary})
    provider, attempt = await orphan_attempt(app)
    assert attempt.state == "ambiguous" and attempt.provider_subject is None
    orphan = provider.created[0]
    # Simulate a process crash mid-signup instead: still `signup_started`, lease long gone.
    async with app.state.database.sessions.begin() as db:
        await db.execute(
            update(GuestProvisioningAttempt)
            .where(GuestProvisioningAttempt.id == attempt.id)
            .values(
                state="signup_started",
                lease_token=uuid4(),
                lease_until=func.clock_timestamp() - timedelta(seconds=1),
                next_attempt_at=func.clock_timestamp() - timedelta(seconds=1),
            )
        )
    assert await jobs.reconcile_guest_provisioning(app) == 1
    async with app.state.database.sessions() as db:
        row = await db.get(GuestProvisioningAttempt, attempt.id)
        gone = await db.scalar(text("select count(*) from auth.users where id=:id"), {"id": orphan})
        kept = await db.scalar(text("select count(*) from auth.users where id=:id"), {"id": canary})
    assert row.state == "resolved" and gone == 0 and kept == 1, "only the marked orphan is removed"
    assert len(provider.signups) == 1, "reconciliation never repeats an upstream signup"


async def test_empty_orphan_lookup_never_reissues_signup(clients):
    from app.modules.guests import jobs
    from app.modules.guests.models import GuestProvisioningAttempt

    app, _ = clients
    provider, attempt = await orphan_attempt(app)
    async with app.state.database.sessions.begin() as db:  # the identity is not (yet) findable
        await db.execute(text("update auth.users set raw_user_meta_data='{}'::jsonb where id=:id"), {"id": provider.created[0]})
    steps = []
    for expected in (5, 30, 300, 3600):
        await make_attempt_due(app, attempt.id)
        assert await jobs.reconcile_guest_provisioning(app) == 1
        async with app.state.database.sessions() as db:
            row = await db.get(GuestProvisioningAttempt, attempt.id)
        assert row.state == "ambiguous", "one empty lookup is not permission to retry upstream"
        steps.append(round((row.next_attempt_at - await db_now(app)).total_seconds()))
        assert abs(steps[-1] - expected) <= 3, steps
    assert len(provider.signups) == 1
    # After the 24h window the unresolved attempt escalates; it is still never granted or resent.
    async with app.state.database.sessions.begin() as db:
        await db.execute(
            update(GuestProvisioningAttempt)
            .where(GuestProvisioningAttempt.id == attempt.id)
            .values(
                signup_started_at=func.clock_timestamp() - timedelta(hours=25),
                reconcile_until=func.clock_timestamp() - timedelta(hours=1),
                next_attempt_at=func.clock_timestamp() - timedelta(seconds=1),
            )
        )
    assert await jobs.reconcile_guest_provisioning(app) == 1
    async with app.state.database.sessions() as db:
        row = await db.get(GuestProvisioningAttempt, attempt.id)
    assert row.state == "incident_required" and row.user_id is None
    assert len(provider.signups) == 1


async def make_attempt_due(app, attempt_id):
    from app.modules.guests.models import GuestProvisioningAttempt

    async with app.state.database.sessions.begin() as db:
        await db.execute(
            update(GuestProvisioningAttempt)
            .where(GuestProvisioningAttempt.id == attempt_id)
            .values(next_attempt_at=func.clock_timestamp() - timedelta(seconds=1))
        )


async def test_duplicate_or_mismatched_markers_trigger_no_delete(clients):
    from app.modules.guests import jobs
    from app.modules.guests.models import GuestProvisioningAttempt

    app, _ = clients
    provider, attempt = await orphan_attempt(app)
    original = provider.created[0]
    marker = json.dumps({"moodprint_guest_attempt": attempt.provider_correlation})
    duplicate = uuid4()
    async with app.state.database.sessions.begin() as db:
        await db.execute(
            text("insert into auth.users(id,is_anonymous,raw_user_meta_data) values (:id,true,cast(:m as jsonb))"),
            {"id": duplicate, "m": marker},
        )
    await make_attempt_due(app, attempt.id)
    assert await jobs.reconcile_guest_provisioning(app) == 1
    async with app.state.database.sessions() as db:
        row = await db.get(GuestProvisioningAttempt, attempt.id)
        survivors = await db.scalar(
            text("select count(*) from auth.users where id = any(:ids)"),
            {"ids": [original, duplicate]},
        )
    assert row.state == "incident_required" and survivors == 2, "a multiple match deletes nothing"


async def test_marker_requires_anonymous_unmapped_in_window_identity(clients):
    from app.modules.guests import jobs
    from app.modules.guests.models import GuestProvisioningAttempt

    app, _ = clients
    provider, attempt = await orphan_attempt(app)
    orphan = provider.created[0]
    async with app.state.database.sessions.begin() as db:
        await db.execute(text("update auth.users set is_anonymous=false where id=:id"), {"id": orphan})
    await make_attempt_due(app, attempt.id)
    await jobs.reconcile_guest_provisioning(app)
    async with app.state.database.sessions() as db:
        assert await db.scalar(text("select count(*) from auth.users where id=:id"), {"id": orphan}) == 1
    async with app.state.database.sessions.begin() as db:  # anonymous again but far outside the window
        await db.execute(
            text("update auth.users set is_anonymous=true, created_at=created_at - interval '1 hour' where id=:id"),
            {"id": orphan},
        )
    await make_attempt_due(app, attempt.id)
    await jobs.reconcile_guest_provisioning(app)
    async with app.state.database.sessions() as db:
        assert await db.scalar(text("select count(*) from auth.users where id=:id"), {"id": orphan}) == 1
        row = await db.get(GuestProvisioningAttempt, attempt.id)
    assert row.state == "ambiguous"


async def test_flags_off_keep_expiry_cleanup_and_reconciliation(clients):
    from app.modules.guests import jobs

    app, actors = clients
    provider, attempt = await orphan_attempt(app)
    settings = app.state.settings
    for flag in (
        "guest_auth_enabled", "guest_paid_enabled", "guest_semantic_enabled",
        "feedback_enabled", "feedback_admin_enabled", "product_tour_enabled",
    ):
        setattr(settings, flag, False)
    guest = await add_guest(app, started_ago=LIFETIME + timedelta(seconds=5))
    # New entry is closed, yet expiry still denies, cleanup still purges, reconciliation still resolves.
    assert (await guest.client.get("/api/v1/session")).status_code == 401
    await make_attempt_due(app, attempt.id)
    assert await jobs.reconcile_guest_provisioning(app) == 1
    assert await jobs.process_guest_cleanup(app) == 1
    assert sum((await user_reference_counts(app, guest.user_id)).values()) == 0
    async with app.state.database.sessions() as db:
        assert await db.scalar(text("select count(*) from auth.users where id=:id"), {"id": provider.created[0]}) == 0


async def test_startup_scan_inserts_a_missing_job_without_touching_access(clients):
    from app.infrastructure.database.models import User
    from app.modules.guests import jobs

    app, _ = clients
    guest = await add_guest(app)
    async with app.state.database.sessions.begin() as db:
        await db.execute(text("delete from moodprint.guest_cleanup_jobs where user_id=:u"), {"u": guest.user_id})
    assert await jobs.ensure_cleanup_jobs(app) == 1
    assert await jobs.ensure_cleanup_jobs(app) == 0
    job = await job_of(app, guest.user_id)
    async with app.state.database.sessions() as db:
        user = await db.get(User, guest.user_id)
    assert job.due_at == user.guest_expires_at == guest.expires_at and job.state == "pending"
    assert (await guest.client.get("/api/v1/session")).status_code == 200, "the scan never changes access"


async def test_recovery_and_cleanup_do_not_deadlock(clients):
    from app.infrastructure.database.models import User
    from app.modules.guests import jobs, service
    from app.modules.guests.models import GuestProvisioningAttempt

    app, _ = clients
    enable_guest_entry(app)
    FakeGuestProvider(app)
    browser = public_client(app)
    await open_intent(browser)
    key = str(uuid4())
    assert (await post_guest(browser, key)).status_code == 201
    async with app.state.database.sessions() as db:
        attempt = (await db.scalars(select(GuestProvisioningAttempt))).one()
    async with app.state.database.sessions.begin() as db:  # the trial ended: purge is allowed now
        await db.execute(update(User).where(User.id == attempt.user_id).values(status="deleting"))
        await db.execute(text("update moodprint.guest_cleanup_jobs set due_at=clock_timestamp()"))
    from fastapi import Response

    request = type("Req", (), {"app": app, "client": None, "cookies": {}, "headers": {}})()

    async def recover():
        try:
            await service.recover_guest_credentials(request, attempt.id, Response())
        except Exception as error:  # a 409 terminal answer is fine; a deadlock is not
            assert "deadlock" not in str(error).lower()
            return type(error).__name__

    results = await asyncio.wait_for(
        asyncio.gather(recover(), jobs.process_guest_cleanup(app)), timeout=15
    )
    assert results[1] == 1
    assert sum((await user_reference_counts(app, attempt.user_id)).values()) == 0


async def test_guest_metrics_are_content_free(clients):
    from app.modules.guests import jobs

    app, _ = clients
    guest = await add_guest(app, started_ago=LIFETIME + timedelta(seconds=30))
    metrics = await jobs.guest_metrics(app)
    assert set(metrics) == {
        "guest_cleanup_lag_seconds", "guest_cleanup_retry_count",
        "guest_orphan_count", "guest_incident_count",
    }
    assert metrics["guest_cleanup_lag_seconds"] >= 25
    assert str(guest.user_id) not in json.dumps(metrics)
