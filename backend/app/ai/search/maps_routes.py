from uuid import UUID

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select

from app.ai.search.maps import MapsSearchView
from app.ai.search.maps_jobs import authorized, provider_client, read_view
from app.ai.search.models import AiMapsSearch
from app.contracts import VersionInput
from app.core.errors import DomainError
from app.core.security import Actor, idempotency_key, require_registered_actor, transaction
from app.infrastructure.database.models import now

router = APIRouter()


@router.get("/ai/maps-searches/{search_id}", response_model=MapsSearchView)
async def get_maps(search_id: UUID, request: Request, actor: Actor = Depends(require_registered_actor)):
    runtime = request.app.state.ai
    client, provider = None, getattr(runtime, "maps_provider", None)
    # A cached job remains readable when new admission is switched off.
    if provider is None and request.app.state.settings.apify_maps_actor_build:
        client, provider = provider_client(request.app.state.settings)
    try:
        view = await read_view(runtime.database, provider, search_id, actor)
        from fastapi.responses import JSONResponse
        return JSONResponse(view.model_dump(mode="json", by_alias=True), headers={"Cache-Control": "no-store"})
    finally:
        if client:
            await client.aclose()


@router.post("/ai/maps-searches/{search_id}/cancel", response_model=MapsSearchView)
async def cancel_maps(search_id: UUID, body: VersionInput, request: Request,
                      actor: Actor = Depends(require_registered_actor)):
    idempotency_key(request)
    async with transaction(request, actor) as (db, user):
        job = await db.scalar(select(AiMapsSearch).where(AiMapsSearch.id == search_id).with_for_update())
        if job is None or job.user_id != user.id:
            raise DomainError(404, "MAPS_NOT_FOUND", "Không tìm thấy kết quả còn hiệu lực.")
        if job.cancel_requested:
            return MapsSearchView(search_id=job.id, status="cancelled", version=job.version, expires_at=job.expires_at)
        await authorized(db, job, actor)
        if job.version != body.expected_version:
            raise DomainError(409, "STALE_VERSION", "Kết quả vừa thay đổi. Hãy tải lại thẻ.")
        job.cancel_requested = True
        job.version += 1
        job.next_poll_at = now()
        return MapsSearchView(search_id=job.id, status="cancelled", version=job.version, expires_at=job.expires_at)
