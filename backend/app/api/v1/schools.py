from fastapi import APIRouter, Depends, Query
from moodprint_shared.contracts.auth import AuthContext
from moodprint_shared.contracts.paging import Page

from app.api.v1.shares import service
from app.core.auth import get_auth
from app.modules.sharing.schemas import SchoolRead
from app.modules.sharing.service import SharingService

router = APIRouter(prefix="/v1/schools", tags=["schools"])


@router.get("", response_model=Page[SchoolRead])
async def schools(
    limit: int = Query(50, ge=1, le=100),
    cursor: str | None = Query(None, max_length=2048),
    auth: AuthContext = Depends(get_auth),
    shares: SharingService = Depends(service),
):
    return await shares.schools(auth, limit=limit, cursor=cursor)
