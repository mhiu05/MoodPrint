from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response
from moodprint_shared.contracts.auth import AuthContext
from moodprint_shared.contracts.evidence import EvidenceMeta, SignedRead
from moodprint_shared.contracts.paging import Page

from app.core.auth import get_auth
from app.modules.evidence.schemas import EvidencePatch, NoteCreate, UploadCreate, UploadReply
from app.modules.evidence.service import EvidenceService

router = APIRouter(prefix="/v1", tags=["evidence"])


def service(request: Request):
    return EvidenceService(
        request.app.state.engine, request.app.state.storage, request.app.state.cfg
    )


@router.post("/evidence/uploads", response_model=UploadReply)
async def init_upload(
    data: UploadCreate,
    auth: AuthContext = Depends(get_auth),
    evidence: EvidenceService = Depends(service),
):
    return await evidence.init_upload(auth, data)


@router.post("/evidence/notes", response_model=EvidenceMeta)
async def create_note(
    data: NoteCreate,
    auth: AuthContext = Depends(get_auth),
    evidence: EvidenceService = Depends(service),
):
    return await evidence.create_note(auth, data)


@router.get("/evidence", response_model=Page[EvidenceMeta])
async def list_evidence(
    caseId: UUID | None = None,
    unlinked: bool = False,
    limit: int = Query(50, ge=1, le=100),
    cursor: str | None = Query(None, max_length=2048),
    auth: AuthContext = Depends(get_auth),
    evidence: EvidenceService = Depends(service),
):
    return await evidence.list(auth, case_id=caseId, unlinked=unlinked, limit=limit, cursor=cursor)


@router.get("/evidence/{id}", response_model=EvidenceMeta)
async def get_evidence(
    id: UUID, auth: AuthContext = Depends(get_auth), evidence: EvidenceService = Depends(service)
):
    return await evidence.get(auth, id)


@router.post("/evidence/{id}/upload-token", response_model=UploadReply)
async def upload_token(
    id: UUID, auth: AuthContext = Depends(get_auth), evidence: EvidenceService = Depends(service)
):
    return await evidence.upload_token(auth, id)


@router.post("/evidence/{id}/complete", response_model=EvidenceMeta)
async def complete(
    id: UUID, auth: AuthContext = Depends(get_auth), evidence: EvidenceService = Depends(service)
):
    return await evidence.complete(auth, id)


@router.patch("/evidence/{id}", response_model=EvidenceMeta)
async def patch_evidence(
    id: UUID,
    data: EvidencePatch,
    auth: AuthContext = Depends(get_auth),
    evidence: EvidenceService = Depends(service),
):
    return await evidence.patch(auth, id, data)


@router.get("/evidence/{id}/download-url", response_model=SignedRead)
async def download(
    id: UUID, auth: AuthContext = Depends(get_auth), evidence: EvidenceService = Depends(service)
):
    return await evidence.open_read_url(auth, id, "user_download")


@router.post("/cases/{id}/evidence/{evidenceId}/link", response_model=EvidenceMeta)
async def link(
    id: UUID,
    evidenceId: UUID,
    auth: AuthContext = Depends(get_auth),
    evidence: EvidenceService = Depends(service),
):
    return await evidence.link(auth, id, evidenceId)


@router.delete("/cases/{id}/evidence/{evidenceId}/link", status_code=204)
async def unlink(
    id: UUID,
    evidenceId: UUID,
    auth: AuthContext = Depends(get_auth),
    evidence: EvidenceService = Depends(service),
):
    await evidence.unlink(auth, id, evidenceId)
    return Response(status_code=204)


@router.delete("/evidence/{id}", status_code=204)
async def delete_evidence(
    id: UUID, auth: AuthContext = Depends(get_auth), evidence: EvidenceService = Depends(service)
):
    await evidence.delete(auth, id)
    return Response(status_code=204)
