from typing import Literal

from fastapi import APIRouter, Depends, Request, Response
from safevoice_shared.contracts.auth import AuthContext
from safevoice_shared.contracts.base import FrozenDTO

from app.core.auth import bearer_token, get_auth
from app.core.deps import profile_service
from app.modules.profiles.schemas import Profile, ProfilePatch
from app.modules.profiles.service import ProfileService

router = APIRouter(prefix="/v1/me", tags=["profiles"])


@router.get("", response_model=Profile)
async def get_me(
    request: Request,
    auth: AuthContext = Depends(get_auth),
    profiles: ProfileService = Depends(profile_service),
):
    return await profiles.get_or_seed(auth, bearer_token(request))


@router.patch("", response_model=Profile)
async def patch_me(data: ProfilePatch, request: Request, auth: AuthContext = Depends(get_auth)):
    return await ProfileService(request.app.state.engine).patch(auth, data)


class AccountDelete(FrozenDTO):
    confirm: Literal["DELETE"]


@router.delete("", status_code=204)
async def delete_me(data: AccountDelete, request: Request, auth: AuthContext = Depends(get_auth)):
    await ProfileService(request.app.state.engine, request.app.state.auth_admin).delete_account(
        auth, bearer_token(request), request.app.state.storage, request.app.state.cfg
    )
    return Response(status_code=204)
