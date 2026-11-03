from datetime import timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.infrastructure.database.models import AiRun, AuthSession, now


async def seed(app, uid, *, deadline=None, status="pending", known=True):
    from app.ai.search.models import AiMapsSearch, AiSearchUsage
    async with app.state.database.sessions.begin() as db:
        session = await db.scalar(select(AuthSession).where(AuthSession.user_id == uid))
        rid = uuid4()
        db.add(AiRun(id=rid, user_id=uid, conversation_id=uuid4(), bot_id="hoatdong", status="completed"))
        await db.flush()
        fee = AiSearchUsage(user_id=uid, parent_run_id=rid, provider="apify", state="dispatched",
             reservation_nano_usd=50_000_000, pricing_version="test")
        db.add(fee)
        await db.flush()
        job = AiMapsSearch(user_id=uid, parent_run_id=rid, session_id=session.id, auth_version=session.auth_version,
            scope_id=uuid4(), data_version=1, operation_id=fee.id, status=status,
            deadline=deadline or now()+timedelta(seconds=90), expires_at=now()+timedelta(minutes=10),
            provider_ref={"run_id": "run123", "dataset_id": "data123", "storage_refs": {}} if known else None)
        db.add(job)
        await db.flush()
        return job.id


class FakeMaps:
    def __init__(self, *, abort_fails=False):
        self.starts = self.aborts = 0
        self.abort_fails = abort_fails

    async def start(self, **_):
        self.starts += 1
        raise AssertionError("worker must never replay start")

    async def status(self, ref):
        from decimal import Decimal

        from app.ai.search.apify import ProviderRunStatus
        return ProviderRunStatus("succeeded", Decimal("0.015"))

    async def results(self, ref):
        from app.ai.search.maps import PlaceResult
        return [PlaceResult(name="Cà phê", address="Quận 3", maps_url="https://www.google.com/maps/search/?api=1&query=cafe", fetched_at=now())]

    async def abort(self, ref):
        self.aborts += 1
        if self.abort_fails:
            raise OSError("fake abort failure")

    async def cleanup(self, ref):
        pass


@pytest.mark.postgres
@pytest.mark.parametrize("cancel_during_results", [False, True])
async def test_ready_during_read_revalidation_includes_places_before_polling_stops(clients, monkeypatch, cancel_during_results):
    from app.ai.search import maps_jobs
    from app.ai.search.models import AiMapsSearch
    from app.infrastructure.database.models import User
    from tests.test_chat_persistence import enable

    app, actors = clients
    client, uid = actors[0]
    await enable(client)
    identity = await seed(app, uid)
    async with app.state.database.sessions.begin() as db:
        job = await db.get(AiMapsSearch, identity)
        job.data_version = (await db.get(User, uid)).data_version
    maps_jobs._results.pop(identity, None)  # API and worker have separate process caches.
    original = maps_jobs.authorized
    checks = 0

    async def complete_between_snapshots(db, job, actor, **kwargs):
        nonlocal checks
        await original(db, job, actor, **kwargs)
        checks += 1
        if checks == 2:
            # The worker commits ready after the initial pending read, before
            # the API's post-I/O authorization snapshot is observed.
            job.status = "ready"
            job.version += 1

    monkeypatch.setattr(maps_jobs, "authorized", complete_between_snapshots)
    class CompletingMaps(FakeMaps):
        async def results(self, ref):
            if cancel_during_results:
                async with app.state.database.sessions.begin() as db:
                    job = await db.get(AiMapsSearch, identity)
                    job.cancel_requested = True
            return await super().results(ref)

    app.state.ai.maps_provider = CompletingMaps()
    response = await client.get(f"/api/v1/ai/maps-searches/{identity}")
    if cancel_during_results:
        assert response.status_code == 404
        assert "mapsUrl" not in response.text
        return
    assert response.status_code == 200
    view = response.json()
    assert view["status"] == "ready"
    assert len(view["places"]) == 1, "a terminal response must include results before the UI stops polling"
    assert view["places"][0]["mapsUrl"].startswith("https://www.google.com/maps/")
    assert app.state.ai.maps_provider.starts == 0


@pytest.mark.postgres
async def test_worker_claim_releases_job_before_waiting_for_owner_cancel(clients, monkeypatch):
    import asyncio

    from sqlalchemy import text

    from app.ai.search import maps_jobs
    from app.ai.search.models import AiMapsSearch
    from app.infrastructure.database.models import User

    app, actors = clients
    uid = actors[0][1]
    identity = await seed(app, uid)
    checking = asyncio.Event()
    original = maps_jobs.authorized

    async def authorize(db, job, actor, **kwargs):
        checking.set()
        return await original(db, job, actor, **kwargs)

    monkeypatch.setattr(maps_jobs, "authorized", authorize)
    worker = None
    try:
        # Same owner -> job order as cancel/delete. The worker must not hold the
        # job while it waits for this account lock, or the two operations deadlock.
        async with app.state.database.sessions.begin() as db:
            await db.scalar(select(User).where(User.id == uid).with_for_update())
            worker = asyncio.create_task(maps_jobs.advance_one(app.state.database, FakeMaps()))
            await asyncio.wait_for(checking.wait(), 3)
            await db.execute(text("SET LOCAL lock_timeout = '300ms'"))
            job = await db.scalar(select(AiMapsSearch).where(AiMapsSearch.id == identity).with_for_update())
            job.cancel_requested = True
    finally:
        if worker is not None:
            await asyncio.wait_for(worker, 5)
    job, _ = await fetch(app, identity)
    assert job.status == "cancelled"


@pytest.mark.postgres
async def test_worker_restart_resumes_known_ref_without_start_and_settles(clients):
    from app.ai.search.maps_jobs import advance_one
    from app.ai.search.models import AiMapsSearch, AiSearchUsage
    app, actors = clients
    identity = await seed(app, actors[0][1])
    provider = FakeMaps()
    assert await advance_one(app.state.database, provider)
    async with app.state.database.sessions() as db:
        job = await db.get(AiMapsSearch, identity)
        fee = await db.get(AiSearchUsage, job.operation_id)
        assert job.status == "ready" and job.version == 2
        assert fee.actual_nano_usd == 15_000_000 and not fee.active
    assert provider.starts == 0


@pytest.mark.postgres
async def test_unknown_dispatch_never_replays_or_refunds(clients):
    from app.ai.search.maps_jobs import advance_one
    from app.ai.search.models import AiMapsSearch, AiSearchUsage
    app, actors = clients
    identity = await seed(app, actors[0][1], deadline=now()-timedelta(seconds=1), status="starting", known=False)
    provider = FakeMaps()
    await advance_one(app.state.database, provider)
    async with app.state.database.sessions() as db:
        job = await db.get(AiMapsSearch, identity)
        fee = await db.get(AiSearchUsage, job.operation_id)
        assert job.status == "failed" and fee.state == "uncertain"
        assert fee.actual_nano_usd is None and fee.reservation_nano_usd == 50_000_000
    assert provider.starts == 0


@pytest.mark.postgres
async def test_cancel_racing_ready_wins_and_no_result_is_published(clients):
    from app.ai.search.maps_jobs import advance_one
    from app.ai.search.models import AiMapsSearch
    app, actors = clients
    identity = await seed(app, actors[0][1])
    class Racing(FakeMaps):
        async def status(self, ref):
            async with app.state.database.sessions.begin() as db:
                job = await db.get(AiMapsSearch, identity)
                job.cancel_requested = True
            return await super().status(ref)
    provider = Racing()
    await advance_one(app.state.database, provider)
    async with app.state.database.sessions() as db:
        job = await db.get(AiMapsSearch, identity)
        assert job.status == "cancelled"


@pytest.mark.postgres
async def test_deadline_abort_failure_keeps_liability(clients):
    from app.ai.search.maps_jobs import advance_one
    from app.ai.search.models import AiMapsSearch, AiSearchUsage
    app, actors = clients
    identity = await seed(app, actors[0][1], deadline=now()-timedelta(seconds=1))
    provider = FakeMaps(abort_fails=True)
    await advance_one(app.state.database, provider)
    async with app.state.database.sessions() as db:
        job = await db.get(AiMapsSearch, identity)
        fee = await db.get(AiSearchUsage, job.operation_id)
        assert job.status == "timed_out" and fee.state == "uncertain"
        assert fee.actual_nano_usd is None
        assert fee.active, "an unconfirmed abort must still occupy a concurrency slot"
    from app.ai.search.accounting import claim
    from app.core.errors import DomainError
    from app.infrastructure.database.models import User
    settings = maps_settings(app)
    settings.ai_search_user_concurrency = 1
    async with app.state.database.sessions.begin() as db:
        with pytest.raises(DomainError) as blocked:
            await claim(db, settings, await db.get(User, actors[0][1]), uuid4(), "apify")
        assert blocked.value.code == "SEARCH_QUOTA"


@pytest.mark.postgres
async def test_worker_total_io_deadline_releases_lease_but_keeps_vendor_liability(clients, monkeypatch):
    import asyncio

    from app.ai.search import maps_jobs

    app, actors = clients
    identity = await seed(app, actors[0][1])
    class Stalled(FakeMaps):
        async def status(self, ref):
            await asyncio.Event().wait()

    monkeypatch.setattr(maps_jobs, "WORKER_IO_TIMEOUT_SECONDS", 0.03)
    assert await asyncio.wait_for(maps_jobs.advance_one(app.state.database, Stalled()), 3)
    job, fee = await fetch(app, identity)
    assert job.lease_until is None and job.fence is None and not job.cleanup_done
    assert fee.active and fee.actual_nano_usd is None


@pytest.mark.postgres
async def test_expired_terminal_job_still_aborts_a_pending_vendor_run(clients):
    from app.ai.search.apify import ProviderRunStatus
    from app.ai.search.maps_jobs import advance_one

    app, actors = clients
    identity = await seed(app, actors[0][1], status="timed_out")
    await make_due(app, identity, expires_at=now() - timedelta(seconds=1))

    class Pending(FakeMaps):
        async def status(self, ref):
            return ProviderRunStatus("pending")

        async def cleanup(self, ref):
            raise AssertionError("never delete run evidence while the actor is still running")

    provider = Pending()
    await advance_one(app.state.database, provider)
    job, fee = await fetch(app, identity)
    assert provider.aborts == 1, "TTL must not stop retrying a failed vendor abort"
    assert fee.active and not job.cleanup_done and job.provider_ref is not None


@pytest.mark.postgres
@pytest.mark.parametrize("cancelled", [False, True])
async def test_expired_jobs_cleanup_vendor_storage_even_when_access_revoked(clients, cancelled):
    from app.ai.search.maps_jobs import advance_one
    from app.ai.search.models import AiMapsSearch
    app, actors = clients
    identity = await seed(app, actors[0][1], status="ready")
    async with app.state.database.sessions.begin() as db:
        job = await db.get(AiMapsSearch, identity)
        job.expires_at = now()-timedelta(seconds=1)
        job.cancel_requested = cancelled
    class Cleaning(FakeMaps):
        cleaned = 0
        async def cleanup(self, ref):
            self.cleaned += 1
    provider = Cleaning()
    await advance_one(app.state.database, provider)
    assert provider.cleaned == 1
    async with app.state.database.sessions() as db:
        job = await db.get(AiMapsSearch, identity)
        assert job.cleanup_done and job.provider_ref is None


def maps_settings(app):
    from pydantic import SecretStr
    s = app.state.settings
    s.ai_three_agent_experience_enabled = s.ai_multi_message_enabled = s.ai_accounting_enabled = True
    s.ai_maps_search_enabled = s.maps_search_worker_enabled = s.apify_maps_charge_bound_verified = True
    s.apify_maps_actor_build, s.apify_maps_pricing_version = "pinned-test", "fake-bound-v1"
    s.apify_api_token = SecretStr("synthetic-test-token")
    s.openai_model, s.ai_daily_budget_usd = "gpt-6-luna", 20
    return s


async def fetch(app, identity):
    from app.ai.search.models import AiMapsSearch, AiSearchUsage
    async with app.state.database.sessions() as db:
        job = await db.get(AiMapsSearch, identity)
        return job, await db.get(AiSearchUsage, job.operation_id)


async def make_due(app, identity, **values):
    from app.ai.search.models import AiMapsSearch
    async with app.state.database.sessions.begin() as db:
        job = await db.get(AiMapsSearch, identity)
        job.next_poll_at = now() - timedelta(seconds=1)
        for name, value in values.items():
            setattr(job, name, value)


@pytest.mark.postgres
async def test_late_start_ref_after_lease_takeover_is_aborted_and_cleaned_without_replay(clients):
    import asyncio
    from decimal import Decimal
    from types import SimpleNamespace

    from app.ai.search.apify import ProviderRunRef, ProviderRunStatus
    from app.ai.search.maps_jobs import advance_one, start_search
    from app.ai.search.models import AiMapsSearch
    from app.ai.search.policy import SearchIntent
    from app.core.security import Actor
    from app.infrastructure.database.models import User
    from tests.test_chat_persistence import enable

    app, actors = clients
    client, uid = actors[0]
    await enable(client)
    settings = maps_settings(app)
    rid = uuid4()
    async with app.state.database.sessions.begin() as db:
        session = await db.scalar(select(AuthSession).where(AuthSession.user_id == uid))
        user = await db.get(User, uid)
        db.add(AiRun(id=rid, user_id=uid, conversation_id=uuid4(), bot_id="hoatdong", status="running"))
        actor, data_version = Actor(uid, session.id, session.auth_version), user.data_version
    release, started = asyncio.Event(), asyncio.Event()

    class Stalled(FakeMaps):
        def __init__(self):
            super().__init__()
            self.calls = []

        async def start(self, **_):
            self.starts += 1
            started.set()
            await release.wait()  # The paid start outlives the starter's 30s lease.
            return ProviderRunRef("late123", "latedata", {"key-value-stores": "latekv"})

        async def status(self, ref):
            self.calls.append(("status", ref.run_id))
            return ProviderRunStatus("aborted", Decimal("0.004"))

        async def cleanup(self, ref):
            self.calls.append(("cleanup", ref.run_id))

    provider = Stalled()
    runtime = SimpleNamespace(database=app.state.database, settings=settings, maps_provider=provider,
                              check=lambda run: asyncio.sleep(0))
    run = SimpleNamespace(id=rid, actor=actor, data_version=data_version, conversation_id=uuid4(), persistent=False)
    intent = SearchIntent("quán cà phê", maps=True, area="Quận 3")
    starter = asyncio.create_task(start_search(runtime, run, intent))
    await asyncio.wait_for(started.wait(), 3)
    async with app.state.database.sessions.begin() as db:
        identity = await db.scalar(select(AiMapsSearch.id).where(AiMapsSearch.parent_run_id == rid))
    await make_due(app, identity, lease_until=now() - timedelta(seconds=1))
    # Recovery of a no-ref row: unknown money, no start replay, nothing to clean yet.
    assert await advance_one(app.state.database, provider)
    job, fee = await fetch(app, identity)
    assert job.status == "failed" and job.cleanup_done and fee.state == "uncertain" and not fee.active
    release.set()
    assert await starter == identity
    job, fee = await fetch(app, identity)
    # The late ref reopens cleanup but never revives the job.
    assert job.provider_ref["run_id"] == "late123" and job.cancel_requested and not job.cleanup_done
    assert fee.active, "a recovered run ref must reacquire its vendor execution slot"
    await make_due(app, identity)
    assert await advance_one(app.state.database, provider)
    job, fee = await fetch(app, identity)
    assert job.status == "cancelled" and fee.state == "settled" and fee.actual_nano_usd == 4_000_000
    await make_due(app, identity, expires_at=now() - timedelta(seconds=1))
    assert await advance_one(app.state.database, provider)
    job, fee = await fetch(app, identity)
    # Cleaned, and the visible state stays the explicit cancellation (never expired/revived).
    assert job.cleanup_done and job.provider_ref is None and job.status == "cancelled"
    assert ("cleanup", "late123") in provider.calls and provider.starts == 1


@pytest.mark.postgres
async def test_cleanup_crash_after_run_metadata_delete_resumes_and_keeps_settlement(clients):
    from decimal import Decimal

    from app.ai.search.apify import ProviderRunStatus
    from app.ai.search.maps_jobs import advance_one
    app, actors = clients
    identity = await seed(app, actors[0][1], status="ready")
    await make_due(app, identity, expires_at=now() - timedelta(seconds=1))

    class Crashing(FakeMaps):
        deleted = False
        cleaned = 0

        async def status(self, ref):
            # After the first attempt deleted the run, Apify answers 404 -> "missing".
            return ProviderRunStatus("missing") if self.deleted else ProviderRunStatus("succeeded", Decimal("0.015"))

        async def cleanup(self, ref):
            if not self.deleted:
                self.deleted = True
                raise OSError("crash after deleting the run metadata")
            self.cleaned += 1

    provider = Crashing()
    await advance_one(app.state.database, provider)
    job, fee = await fetch(app, identity)
    # Final billing was persisted before any vendor deletion; cleanup stays open.
    assert fee.state == "settled" and fee.actual_nano_usd == 15_000_000
    assert not job.cleanup_done and job.provider_ref is not None
    await advance_one(app.state.database, provider)
    job, fee = await fetch(app, identity)
    assert job.cleanup_done and job.status == "expired" and provider.cleaned == 1
    assert fee.state == "settled" and fee.actual_nano_usd == 15_000_000 and provider.starts == 0


@pytest.mark.postgres
async def test_cleanup_error_never_reopens_a_confirmed_terminal_execution_slot(clients):
    from app.ai.search.maps_jobs import advance_one
    from app.ai.search.models import AiMapsSearch, AiSearchUsage

    app, actors = clients
    identity = await seed(app, actors[0][1], status="ready")
    async with app.state.database.sessions.begin() as db:
        job = await db.get(AiMapsSearch, identity)
        job.expires_at = now() - timedelta(seconds=1)
        fee = await db.get(AiSearchUsage, job.operation_id)
        fee.state, fee.actual_nano_usd, fee.active = "settled", 15_000_000, False

    class Unavailable(FakeMaps):
        async def status(self, ref):
            raise OSError("synthetic provider outage during storage cleanup")

    await advance_one(app.state.database, Unavailable())
    job, fee = await fetch(app, identity)
    assert not fee.active, "a cleanup outage must not reserve execution quota for a stopped actor"
    assert not job.cleanup_done and job.provider_ref is not None


@pytest.mark.postgres
async def test_timed_out_job_is_never_revived_and_retries_abort_until_billed(clients):
    from decimal import Decimal

    from app.ai.search.apify import ProviderRunStatus
    from app.ai.search.maps_jobs import advance_one
    app, actors = clients
    identity = await seed(app, actors[0][1], deadline=now() - timedelta(seconds=1))

    class Late(FakeMaps):
        state = "pending"
        results_read = 0

        async def status(self, ref):
            return ProviderRunStatus(self.state, Decimal("0.02") if self.state != "pending" else None)

        async def results(self, ref):
            self.results_read += 1
            return await super().results(ref)

    provider = Late(abort_fails=True)
    await advance_one(app.state.database, provider)
    job, fee = await fetch(app, identity)
    assert job.status == "timed_out" and fee.state == "uncertain" and provider.aborts == 1
    provider.abort_fails = False
    await make_due(app, identity)
    await advance_one(app.state.database, provider)  # Still running at the vendor: abort again.
    assert provider.aborts == 2
    provider.state = "succeeded"
    await make_due(app, identity)
    await advance_one(app.state.database, provider)
    job, fee = await fetch(app, identity)
    assert job.status == "timed_out" and provider.results_read == 0
    assert fee.state == "settled" and fee.actual_nano_usd == 20_000_000 and not fee.active
    assert job.next_poll_at == job.expires_at  # A billed terminal job waits only for cleanup.


@pytest.mark.postgres
async def test_account_detach_cleans_pending_job_now_and_keeps_liability(clients):
    from app.ai.search.maps_jobs import advance_one, detach_searches
    app, actors = clients
    uid = actors[0][1]
    identity = await seed(app, uid)
    async with app.state.database.sessions.begin() as db:
        await detach_searches(db, uid)

    class Cleaning(FakeMaps):
        cleaned = 0

        async def cleanup(self, ref):
            self.cleaned += 1

    provider = Cleaning()
    await advance_one(app.state.database, provider)
    job, fee = await fetch(app, identity)
    assert job.user_id is None and fee.user_id is None and job.session_id is None
    assert provider.aborts == 1 and provider.cleaned == 1 and job.cleanup_done
    assert fee.state == "settled" and fee.actual_nano_usd == 15_000_000
