from uuid import UUID

from fastapi import APIRouter, Depends, Query
from moodprint_shared.contracts.auth import AuthContext
from moodprint_shared.contracts.evidence import SignedRead
from moodprint_shared.contracts.paging import Page

from app.api.v1.shares import service
from app.core.auth import get_auth
from app.modules.sharing.schemas import SchoolShareRead
from app.modules.sharing.service import SharingService

router = APIRouter(prefix="/v1/school", tags=["school access"])


@router.get("/{schoolId}/shares", response_model=Page[SchoolShareRead])
async def school_shares(
    schoolId: UUID,
    limit: int = Query(50, ge=1, le=100),
    cursor: str | None = Query(None, max_length=2048),
    auth: AuthContext = Depends(get_auth),
    shares: SharingService = Depends(service),
):
    return await shares.school_list(auth, schoolId, limit=limit, cursor=cursor)


@router.get("/{schoolId}/shares/{id}", response_model=SchoolShareRead)
async def school_share(
    schoolId: UUID,
    id: UUID,
    auth: AuthContext = Depends(get_auth),
    shares: SharingService = Depends(service),
):
    return await shares.school_get(auth, schoolId, id)


@router.get("/{schoolId}/shares/{id}/evidence/{evidenceId}/download-url", response_model=SignedRead)
async def school_evidence(
    schoolId: UUID,
    id: UUID,
    evidenceId: UUID,
    auth: AuthContext = Depends(get_auth),
    shares: SharingService = Depends(service),
):
    return await shares.school_download(auth, schoolId, id, evidenceId)
