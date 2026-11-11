from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from safevoice_shared.contracts.auth import AuthContext
from safevoice_shared.contracts.paging import Page

from app.core.auth import bearer_token, get_auth
from app.modules.sharing.schemas import (
    ShareCreate,
    SharePatch,
    SharePreview,
    ShareRead,
    ShareSubmit,
)
from app.modules.sharing.service import SharingService

router = APIRouter(prefix="/v1/shares", tags=["sharing"])


def service(request: Request):
    return SharingService(
        request.app.state.engine, request.app.state.storage, request.app.state.cfg
    )


@router.get("", response_model=Page[ShareRead])
async def list_shares(
    limit: int = Query(50, ge=1, le=100),
    cursor: str | None = Query(None, max_length=2048),
    auth: AuthContext = Depends(get_auth),
    shares: SharingService = Depends(service),
):
    return await shares.list(auth, limit=limit, cursor=cursor)


@router.post("", response_model=ShareRead)
async def create_share(
    data: ShareCreate,
    auth: AuthContext = Depends(get_auth),
    shares: SharingService = Depends(service),
):
    return await shares.create(auth, data)


@router.get("/{id}", response_model=ShareRead)
async def get_share(
    id: UUID, auth: AuthContext = Depends(get_auth), shares: SharingService = Depends(service)
):
    return await shares.get(auth, id)


@router.patch("/{id}", response_model=ShareRead)
async def patch_share(
    id: UUID,
    data: SharePatch,
    auth: AuthContext = Depends(get_auth),
    shares: SharingService = Depends(service),
):
    return await shares.patch(auth, id, data)


@router.get("/{id}/preview", response_model=SharePreview)
async def preview(
    id: UUID, auth: AuthContext = Depends(get_auth), shares: SharingService = Depends(service)
):
    return await shares.preview(auth, id)


@router.post("/{id}/submit", response_model=ShareRead)
async def submit(
    id: UUID,
    data: ShareSubmit,
    request: Request,
    auth: AuthContext = Depends(get_auth),
    shares: SharingService = Depends(service),
):
    await request.app.state.auth_admin.require_live_user(auth, bearer_token(request))
    return await shares.submit(auth, id, data)


@router.post("/{id}/withdraw", response_model=ShareRead)
async def withdraw(
    id: UUID, auth: AuthContext = Depends(get_auth), shares: SharingService = Depends(service)
):
    return await shares.withdraw(auth, id)
