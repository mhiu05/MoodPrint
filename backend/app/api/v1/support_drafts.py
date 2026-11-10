from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response
from moodprint_shared.contracts.auth import AuthContext
from moodprint_shared.contracts.paging import Page

from app.core.auth import get_auth
from app.modules.support.schemas import DraftCreate, DraftPatch, DraftRead
from app.modules.support.service import SupportService

router = APIRouter(prefix="/v1/support-drafts", tags=["support drafts"])


def service(request: Request):
    return SupportService(request.app.state.engine)


@router.get("", response_model=Page[DraftRead])
async def list_drafts(
    limit: int = Query(50, ge=1, le=100),
    cursor: str | None = Query(None, max_length=2048),
    auth: AuthContext = Depends(get_auth),
    drafts: SupportService = Depends(service),
):
    return await drafts.list(auth, limit=limit, cursor=cursor)


@router.post("", response_model=DraftRead)
async def create_draft(
    data: DraftCreate,
    auth: AuthContext = Depends(get_auth),
    drafts: SupportService = Depends(service),
):
    return await drafts.create(auth, data)


@router.get("/{id}", response_model=DraftRead)
async def get_draft(
    id: UUID, auth: AuthContext = Depends(get_auth), drafts: SupportService = Depends(service)
):
    return await drafts.get(auth, id)


@router.patch("/{id}", response_model=DraftRead)
async def patch_draft(
    id: UUID,
    data: DraftPatch,
    auth: AuthContext = Depends(get_auth),
    drafts: SupportService = Depends(service),
):
    return await drafts.patch(auth, id, data)


@router.delete("/{id}", status_code=204)
async def delete_draft(
    id: UUID, auth: AuthContext = Depends(get_auth), drafts: SupportService = Depends(service)
):
    await drafts.delete(auth, id)
    return Response(status_code=204)
