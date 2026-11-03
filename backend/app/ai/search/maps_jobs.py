"""Async Maps coordination. Workers resume refs; no worker can dispatch a paid start."""

import asyncio
from dataclasses import asdict
from datetime import timedelta
from uuid import uuid4

import httpx
from sqlalchemy import or_, select, update

from app.ai.schemas import MapsSearchCard, PlacesCard
from app.ai.search.accounting import claim
from app.ai.search.apify import ApifyMapsProvider, ProviderRunRef
from app.ai.search.maps import MapsSearchView
from app.ai.search.models import AiMapsSearch, AiSearchUsage
from app.core.errors import DomainError
from app.core.security import Actor, assert_purpose, lock_actor
from app.infrastructure.database.models import AiRun, now

TERMINAL = {"ready", "empty", "failed", "timed_out", "cancelled", "expired"}
WORKER_IO_TIMEOUT_SECONDS = 20
# Per-process cache only, never a persisted temporary-chat result or cross-user cache.
_results: dict = {}


def cache(identity, places, expires):
    for key, (_, end) in list(_results.items()):
        if end <= now():
            _results.pop(key, None)
    if len(_results) >= 1000:
        _results.pop(next(iter(_results)))
    _results[identity] = (places, expires)


def provider_client(settings):
    client = httpx.AsyncClient(transport=httpx.AsyncHTTPTransport(retries=0,
        local_address="0.0.0.0" if getattr(settings, "provider_force_ipv4", False) else None), timeout=3, follow_redirects=False)
    return client, ApifyMapsProvider(client, settings.apify_api_token.get_secret_value(), build=settings.apify_maps_actor_build)


async def authorized(db, job, actor, *, scope_id=None):
    user = await lock_actor(db, actor)
    await assert_purpose(db, user, "AI")
    if (job.user_id != user.id or job.data_version != user.data_version or job.cancel_requested
            or job.expires_at <= now() or (scope_id is not None and job.scope_id != scope_id)
            or (job.conversation_id is None and job.session_id != actor.session_id)):
        raise DomainError(404, "MAPS_NOT_FOUND", "Không tìm thấy kết quả còn hiệu lực.")
    if job.conversation_id is not None:
        from app.ai.persistence import owned_conversation
        if await owned_conversation(db, job.conversation_id, user.id) is None:
            raise DomainError(404, "MAPS_NOT_FOUND", "Không tìm thấy kết quả còn hiệu lực.")
    return user


async def start_search(runtime, run, intent):
    await runtime.check(run)
    async with runtime.database.require()() as db, db.begin():
        user = await lock_actor(db, run.actor)
        await assert_purpose(db, user, "AI")
        if user.data_version != run.data_version:
            raise DomainError(409, "CONTEXT_CHANGED", "Quyền hoặc dữ liệu đã thay đổi.")
        fee = await claim(db, runtime.settings, user, run.id, "apify")
        job = AiMapsSearch(user_id=user.id, parent_run_id=run.id, operation_id=fee.id,
            scope_id=run.conversation_id, conversation_id=run.conversation_id if run.persistent else None,
            session_id=run.actor.session_id, auth_version=run.actor.auth_version, data_version=run.data_version,
            deadline=now()+timedelta(seconds=90), expires_at=now()+timedelta(minutes=10),
            lease_until=now()+timedelta(seconds=30), fence=uuid4())
        db.add(job)
        await db.flush()
        identity = job.id
        start_fence = job.fence
        fee.state = "dispatched"
    client = None
    ref = None
    try:
        await runtime.check(run)
        provider = getattr(runtime, "maps_provider", None)
        if provider is None:
            client, provider = provider_client(runtime.settings)
        query = (intent.query or "").lower()
        category = "cafe" if "phê" in query or "cafe" in query else "park" if "công viên" in query else "restaurant" if "nhà hàng" in query else "museum" if "bảo tàng" in query else "activity"
        async with asyncio.timeout(3):
            ref = await provider.start(category=category, area=intent.area)
    finally:
        async def save_ref():
            async with runtime.database.require()() as db, db.begin():
                row = await db.scalar(select(AiMapsSearch).where(AiMapsSearch.id == identity).with_for_update())
                fee = await db.get(AiSearchUsage, row.operation_id)
                row.provider_ref = asdict(ref) if ref else None
                if ref:
                    row.cleanup_done = False  # A late ref must reopen cleanup after no-ref recovery.
                    fee.active = fee.state != "settled"  # A recovered actor occupies a slot until confirmed stopped.
                if row.fence == start_fence:
                    row.status = "pending" if ref else "failed"
                    row.fence = None
                else:
                    # A late start result is retained only to abort/clean; never revive an old job.
                    row.cancel_requested = True
                row.lease_until = None
                row.next_poll_at = now()
                if not ref:
                    fee.state = "uncertain"
                    fee.active = False
                fee.call_count = 1
            if client:
                await client.aclose()
        task = asyncio.create_task(save_ref())
        while not task.done():
            try:
                await asyncio.shield(task)
            except asyncio.CancelledError:
                continue
        task.result()
    return identity


async def read_view(database, provider, identity, actor, *, scope_id=None):
    # A worker can finish between the two authorization snapshots. Re-read that
    # ready transition so the terminal response contains its places before the
    # browser stops polling. Only one transition into ready is possible per job.
    for _ in range(2):
        async with database.require()() as db, db.begin():
            row = await db.get(AiMapsSearch, identity)
            if row is None:
                raise DomainError(404, "MAPS_NOT_FOUND", "Không tìm thấy kết quả còn hiệu lực.")
            await authorized(db, row, actor, scope_id=scope_id)
            status = row.status
            view = MapsSearchView(search_id=row.id, status=status, version=row.version, expires_at=row.expires_at)
            ref = ProviderRunRef(**row.provider_ref) if row.provider_ref else None
        places = _results.get(identity, ([], now()))[0]
        if status == "ready" and not places and ref and provider is not None:
            places = await provider.results(ref)
            cache(identity, places, view.expires_at)
        # Authorization is checked again after provider I/O (GET never starts an actor/model).
        async with database.require()() as db, db.begin():
            current = await db.get(AiMapsSearch, identity)
            await authorized(db, current, actor, scope_id=scope_id)
            became_ready = status != "ready" and current.status == "ready"
            if current.status != status:
                view.status, view.version = current.status, current.version
        if became_ready:
            continue
        if view.status == "ready":
            view.places = places
        return view
    raise DomainError(409, "MAPS_VIEW_CHANGED", "Kết quả vừa thay đổi. Hãy tải lại thẻ.")


async def maps_for_turn(runtime, run, intent):
    client = None
    try:
        if run.prompt_options.maps_search_id:
            provider = getattr(runtime, "maps_provider", None)
            if provider is None:
                client, provider = provider_client(runtime.settings)
            view = await read_view(runtime.database, provider, run.prompt_options.maps_search_id,
                                   run.actor, scope_id=run.conversation_id)
            if view.status == "ready" and view.places:
                run.public_cards.append(PlacesCard(kind="places", places=view.places))
            else:
                run.public_cards.append(MapsSearchCard(kind="maps_search", search_id=view.search_id))
            return view.model_dump(mode="json", by_alias=True)
        if not intent.area or intent.query is None:
            return {"status": "needs_area", "message": "Bạn muốn tìm ở khu vực nào? Không dùng GPS hoặc địa chỉ từ hồ sơ."}
        run.tool_calls += 1
        identity = await start_search(runtime, run, intent)
        run.public_cards.append(MapsSearchCard(kind="maps_search", search_id=identity))
        return {"status": "pending", "message": "Đang tìm địa điểm. Kết quả sẽ xuất hiện trong thẻ; lượt này chưa có địa điểm đã xác minh."}
    except DomainError as error:
        if error.code.startswith("SEARCH_"):
            return {"status": "unavailable", "reason": error.code}
        raise
    except (TimeoutError, httpx.HTTPError, ValueError):
        return {"status": "unavailable"}
    finally:
        if client:
            await client.aclose()


async def advance_one(database, provider) -> bool:
    """Claim one fenced job, release DB, poll/abort, then compare fence before settlement."""
    async with database.require()() as db, db.begin():
        job = await db.scalar(select(AiMapsSearch).where(
            AiMapsSearch.cleanup_done.is_(False), AiMapsSearch.next_poll_at <= now(),
            or_(AiMapsSearch.lease_until.is_(None), AiMapsSearch.lease_until <= now()),
        ).order_by(AiMapsSearch.next_poll_at).limit(1).with_for_update(skip_locked=True))
        if job is None:
            return False
        fence = uuid4()
        job.fence, job.lease_until, job.attempts = fence, now()+timedelta(seconds=25), job.attempts+1
        identity = job.id
    # Release the claim before the owner gate: cancel/delete take owner -> job.
    cancelled = False
    async with database.require()() as db, db.begin():
        if job.user_id is not None:
            try:
                await authorized(db, job, Actor(job.user_id, job.session_id, job.auth_version))
                parent = await db.get(AiRun, job.parent_run_id) if job.parent_run_id else None
                cancelled = cancelled or parent is None or parent.status in ("cancelled", "failed", "interrupted")
            except DomainError:
                cancelled = True
        job = await db.scalar(select(AiMapsSearch).where(AiMapsSearch.id == identity,
            AiMapsSearch.fence == fence, AiMapsSearch.lease_until > now()).with_for_update())
        if job is None:
            return True
        ref = ProviderRunRef(**job.provider_ref) if job.provider_ref else None
        expired, cancelled = now() >= job.deadline, cancelled or job.cancel_requested
        cleanup_due = now() >= job.expires_at or job.user_id is None
        old_status = job.status
    status, charged, places, cleaned, vendor_terminal = old_status, None, [], False, False
    try:
        async with asyncio.timeout(WORKER_IO_TIMEOUT_SECONDS):
            if not ref:
                status = "failed"
            elif cleanup_due:
                # UI terminal states do not prove that a failed abort stopped the actor.
                if old_status not in TERMINAL:
                    await provider.abort(ref)
                settled = await provider.status(ref)
                if settled.state == "pending" and old_status in TERMINAL:
                    await provider.abort(ref)
                    settled = await provider.status(ref)
                vendor_terminal = settled.state != "pending"
                charged = settled.charged_usd if vendor_terminal else None
                if vendor_terminal:
                    # Preserve final billing evidence before deleting provider metadata.
                    if charged is not None:
                        async with database.require()() as db, db.begin():
                            current = await db.scalar(select(AiMapsSearch).where(AiMapsSearch.id == identity,
                                AiMapsSearch.fence == fence, AiMapsSearch.lease_until > now()).with_for_update())
                            if current is None:
                                return True
                            fee = await db.get(AiSearchUsage, current.operation_id)
                            fee.state, fee.actual_nano_usd = "settled", int(charged * 1_000_000_000)
                    await provider.cleanup(ref)
                    cleaned = True
                status = "expired"
            elif old_status in TERMINAL:
                # Terminal jobs only reconcile billing until cleanup; never revive them.
                settled = await provider.status(ref)
                vendor_terminal = settled.state != "pending"
                if not vendor_terminal:
                    await provider.abort(ref)
                else:
                    charged = settled.charged_usd
            elif cancelled or expired:
                status = "cancelled" if cancelled else "timed_out"
                await provider.abort(ref)
                settled = await provider.status(ref)
                vendor_terminal = settled.state != "pending"
                if vendor_terminal:
                    charged = settled.charged_usd
            else:
                settled = await provider.status(ref)
                vendor_terminal = settled.state != "pending"
                if vendor_terminal:
                    charged = settled.charged_usd
                if settled.state == "succeeded":
                    places = await provider.results(ref)
                    status = "ready" if places else "empty"
                elif vendor_terminal:
                    status = "failed"
    except (TimeoutError, httpx.HTTPError, OSError, ValueError, KeyError):
        pass  # No replay, no refund. Retry polling/cleanup with bounded backoff.
    async with database.require()() as db, db.begin():
        job = await db.scalar(select(AiMapsSearch).where(AiMapsSearch.id == identity,
            AiMapsSearch.fence == fence, AiMapsSearch.lease_until > now()).with_for_update())
        if job is None:
            return True
        if job.cancel_requested:
            status, places = "cancelled", []
        job.status, job.version = status, job.version + int(status != job.status)
        fee = await db.get(AiSearchUsage, job.operation_id)
        if charged is not None:
            fee.state, fee.actual_nano_usd = "settled", int(charged * 1_000_000_000)
            fee.item_count = len(places) if places else fee.item_count
        elif status in TERMINAL and fee.state != "settled":
            fee.state = "uncertain"
        if ref is None or vendor_terminal:
            fee.active = False
        # Otherwise preserve the execution evidence: an API/storage outage cannot
        # reactivate an actor already confirmed stopped on an earlier tick.
        job.cleanup_done = cleaned or ref is None
        if cleaned:
            job.provider_ref = None
            job.session_id = job.scope_id = job.conversation_id = None
        job.fence = job.lease_until = None
        job.next_poll_at = (job.expires_at if status in TERMINAL and fee.state == "settled"
                            else now()+timedelta(seconds=min(30, 2 ** min(job.attempts, 4))))
        expires = job.expires_at
    if places and status == "ready":
        cache(identity, places, expires)
    if status in ("cancelled", "expired", "timed_out", "failed"):
        _results.pop(identity, None)
    return True


async def detach_searches(db, user_id):
    # Tombstoned accounts do not trigger user FK cascades. Preserve money, remove identity.
    await db.execute(update(AiMapsSearch).where(AiMapsSearch.user_id == user_id).values(
        user_id=None, parent_run_id=None, scope_id=None, conversation_id=None, session_id=None,
        cancel_requested=True, next_poll_at=now()))
    await db.execute(update(AiSearchUsage).where(AiSearchUsage.user_id == user_id).values(user_id=None, parent_run_id=None))
