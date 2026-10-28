"""Whole-branch review regressions for rollover admission and retained incident links."""

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import httpx
import pytest
from sqlalchemy import select

from tests.guest_helpers import (
    FakeGuestProvider,
    add_guest,
    db_now,
    enable_guest_entry,
    enable_paid_fixture,
    open_intent,
    post_guest,
    public_client,
)
from tests.test_guest_paid_dispatch import CountingTranscriber, wav

pytestmark = pytest.mark.postgres


async def test_old_window_rejection_never_refunds_new_window_admission(clients, monkeypatch):
    from app.modules.auth.provider import AnonymousSignupError
    from app.modules.guests import limits, service
    from app.modules.guests.models import GuestAbuseBucket, GuestProvisioningAttempt

    app, _ = clients
    enable_guest_entry(app)
    at = datetime(2026, 10, 28, 16, 59, 59, 999000, tzinfo=UTC)  # Bangkok day/hour boundary.

    async def clock(db):
        return at

    monkeypatch.setattr(limits, 'database_time', clock)
    entered, resume = asyncio.Event(), asyncio.Event()

    class RejectedFirst(FakeGuestProvider):
        first = True

        async def handle(self, request):
            if request.url.path.endswith('/signup') and self.first:
                self.first = False
                entered.set()
                await resume.wait()
                return httpx.Response(400, json={'error_code': 'captcha_failed'})
            return await super().handle(request)

    RejectedFirst(app)
    async with public_client(app) as old, public_client(app) as new:
        await open_intent(old)
        await open_intent(new)
        pending = asyncio.create_task(post_guest(old, str(uuid4())))
        try:
            await asyncio.wait_for(entered.wait(), 5)
            async with app.state.database.sessions() as db:
                attempt = await db.scalar(select(GuestProvisioningAttempt).where(GuestProvisioningAttempt.state == 'signup_started'))
                old_id, fence = attempt.id, attempt.lease_token
            at += timedelta(milliseconds=2)
            accepted = await post_guest(new, str(uuid4()))
            assert accepted.status_code == 201, accepted.text
        finally:
            resume.set()
        rejected = await asyncio.wait_for(pending, 5)
        assert rejected.status_code >= 400

    async def buckets():
        async with app.state.database.sessions() as db:
            return {(row.scope, row.window_start): row.count for row in
                (await db.scalars(select(GuestAbuseBucket).where(GuestAbuseBucket.scope.in_(['creation_hour', 'creation_day'])))).all()}

    rows = await buckets()
    for scope, window in [('creation_hour', limits.fixed_window(at, 3600)), ('creation_day', limits.bangkok_day(at))]:
        assert rows[(scope, window[0])] == 1, 'old rejection refunded a different accepted attempt'
        assert rows[(scope, window[0] - (timedelta(hours=1) if scope.endswith('hour') else timedelta(days=1))) ] == 0
    # A repeated/stolen rejection callback must not refund a reservation again.
    request = type('Request', (), {'app': app, 'client': type('Client', (), {'host': '127.0.0.1'})()})()
    await service._record_signup_failure(request, old_id, fence,
        AnonymousSignupError('rejected', 422, 'CAPTCHA_FAILED', 'Synthetic rejection'))
    assert await buckets() == rows


async def test_retention_skips_incident_link_but_expires_other_records(clients, monkeypatch):
    from app.modules.guests import jobs
    from app.modules.guests.models import (
        GuestAbuseBucket,
        GuestBudgetDay,
        GuestCleanupJob,
        GuestCostReservation,
        GuestOperationLink,
    )

    app, _ = clients
    enable_paid_fixture(app)
    guest = await add_guest(app, consents=True)
    app.state.transcriber = CountingTranscriber()
    response = await guest.client.post('/api/v1/voice/transcriptions', content=wav(),
        headers={'Content-Type': 'audio/wav', 'Idempotency-Key': str(uuid4())})
    assert response.status_code == 200, response.text
    at = await db_now(app) + timedelta(days=2)
    detached_id = uuid4()
    async with app.state.database.sessions.begin() as db:
        cleanup = await db.get(GuestCleanupJob, guest.user_id)
        cleanup.state = 'incident_required'
        linked = await db.scalar(select(GuestCostReservation))
        linked_id, day_id, charge = linked.id, linked.day, linked.charged_nano_usd
        db.add(GuestCostReservation(id=detached_id, day=day_id, kind='voice', state='cancelled',
            upper_nano_usd=0, lease_until=at - timedelta(hours=25)))
        db.add(GuestAbuseBucket(scope='intent', key_hash='a'*64, count=1,
            window_start=at-timedelta(days=2), expires_at=at-timedelta(days=1)))

    async def clock(db):
        return at

    monkeypatch.setattr(jobs, 'database_time', clock)
    assert await jobs.retention_tick(app) == {'buckets': 1, 'reservations': 1, 'days': 0}
    async with app.state.database.sessions() as db:
        assert await db.get(GuestCostReservation, detached_id) is None
        assert (await db.get(GuestCostReservation, linked_id)).charged_nano_usd == charge
        assert (await db.get(GuestBudgetDay, day_id)).spent_nano_usd == charge
        assert await db.scalar(select(GuestOperationLink.reservation_id)) == linked_id
        assert not (await db.scalars(select(GuestAbuseBucket))).all()
    assert await jobs.retention_tick(app) == {'buckets': 0, 'reservations': 0, 'days': 0}


@pytest.mark.parametrize('outcome', ['reject', 'failed_grant'])
async def test_slow_creation_admission_keeps_fresh_provider_start_clock(clients, monkeypatch, outcome):
    from sqlalchemy import text, update

    from app.modules.guests import jobs, limits, service
    from app.modules.guests.models import GuestAbuseBucket, GuestProvisioningAttempt

    app, _ = clients
    enable_guest_entry(app)
    at = datetime(2026, 10, 28, 16, 59, 59, tzinfo=UTC)
    reserved_at = at
    original_bucket = limits.reserve_bucket

    async def clock(db):
        return at

    async def delayed_bucket(*args, **kwargs):
        nonlocal at
        result = await original_bucket(*args, **kwargs)
        if kwargs['scope'] == 'creation_hour':
            at += timedelta(seconds=61)  # Deterministic DB-wait elapsed time, no sleeping.
        return result

    monkeypatch.setattr(limits, 'database_time', clock)
    monkeypatch.setattr(service, 'database_time', clock)
    monkeypatch.setattr(limits, 'reserve_bucket', delayed_bucket)
    class Provider(FakeGuestProvider):
        async def handle(self, request):
            response = await super().handle(request)
            if request.url.path.endswith('/signup') and self.created:
                async with app.state.database.sessions.begin() as db:
                    await db.execute(text('update auth.users set created_at=:at where id=:uid'),
                        {'at': at, 'uid': self.created[-1]})
            return response

    async def failed_grant(*args, **kwargs):
        raise RuntimeError('synthetic failed local grant')

    provider = Provider(app, mode='captcha' if outcome == 'reject' else 'ok')
    if outcome == 'failed_grant':
        monkeypatch.setattr(service, 'grant_guest', failed_grant)
    async with public_client(app) as browser:
        await open_intent(browser)
        response = await post_guest(browser, str(uuid4()))
        assert response.status_code >= 400
    assert len(provider.signups) == 1
    async with app.state.database.sessions() as db:
        attempt = await db.scalar(select(GuestProvisioningAttempt))
        assert attempt.signup_started_at == at > reserved_at + timedelta(seconds=60)
        buckets = (await db.scalars(select(GuestAbuseBucket).where(
            GuestAbuseBucket.scope.in_(['creation_hour', 'creation_day'])))).all()
        assert len(buckets) == 2
        assert all(bucket.count == (0 if outcome == 'reject' else 1) for bucket in buckets)
        attempt_id = attempt.id
    if outcome == 'failed_grant':
        # The actual private orphan helper can still find/delete this identity.
        async with app.state.database.sessions.begin() as db:
            await db.execute(update(GuestProvisioningAttempt).where(GuestProvisioningAttempt.id == attempt_id)
                .values(next_attempt_at=await db_now(app) - timedelta(seconds=1)))
        assert await jobs.reconcile_guest_provisioning(app) == 1
        async with app.state.database.sessions() as db:
            assert (await db.get(GuestProvisioningAttempt, attempt_id)).state == 'resolved'
            assert await db.scalar(text('select count(*) from auth.users where id=:uid'),
                {'uid': provider.created[0]}) == 0


async def test_startup_cleanup_repair_retries_after_transient_failure(clients, monkeypatch):
    from sqlalchemy import delete

    from app.infrastructure.database.models import User
    from app.modules.guests import jobs
    from app.modules.guests.models import GuestCleanupJob

    app, _ = clients
    guest = await add_guest(app, started_ago=timedelta(seconds=7201))
    async with app.state.database.sessions.begin() as db:
        await db.execute(delete(GuestCleanupJob).where(GuestCleanupJob.user_id == guest.user_id))
    original_repair, original_cleanup = jobs.ensure_cleanup_jobs, jobs.process_guest_cleanup
    repairs = ticks = 0
    second_tick = asyncio.Event()

    async def repair(application):
        nonlocal repairs
        repairs += 1
        if repairs == 1:
            raise RuntimeError('synthetic transient DB failure')
        return await original_repair(application)

    async def cleanup(application):
        nonlocal ticks
        result = await original_cleanup(application)
        ticks += 1
        if ticks == 2:
            second_tick.set()
        return result

    monkeypatch.setattr(jobs, 'ensure_cleanup_jobs', repair)
    monkeypatch.setattr(jobs, 'process_guest_cleanup', cleanup)
    async with app.router.lifespan_context(app):
        await asyncio.wait_for(second_tick.wait(), 8)
        assert repairs == 2, 'failed startup repair was permanently suppressed'
        async with app.state.database.sessions() as db:
            assert await db.get(User, guest.user_id) is None
            assert await db.get(GuestCleanupJob, guest.user_id) is None
