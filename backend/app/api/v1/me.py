from fastapi import APIRouter, Depends, Request
from moodprint_shared.contracts.auth import AuthContext

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
