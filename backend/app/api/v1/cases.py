import logging
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response
from moodprint_shared.contracts.auth import AuthContext
from moodprint_shared.contracts.incidents import (
    CaseDetail,
    CaseQuery,
    CaseStatus,
    CaseSummary,
    TimelineEvent,
)
from moodprint_shared.contracts.paging import Page

from app.core.auth import get_auth
from app.core.errors import ApiError
from app.jobs.evidence import purge_once
from app.modules.incidents.schemas import CaseCreate, CasePatch, EventWrite
from app.modules.incidents.service import IncidentService

router = APIRouter(prefix="/v1/cases", tags=["cases"])


def service(request: Request) -> IncidentService:
    return IncidentService(request.app.state.engine)


@router.get("", response_model=Page[CaseSummary])
async def list_cases(
    status: CaseStatus | None = None,
    q: str | None = Query(default=None, max_length=200),
    sort: str = Query(default="updated", pattern="^(updated|title)$"),
    limit: int = Query(default=50, ge=1, le=100),
    cursor: str | None = Query(default=None, max_length=2048),
    auth: AuthContext = Depends(get_auth),
    cases: IncidentService = Depends(service),
):
    return await cases.list_cases(
        auth,
        CaseQuery.model_validate(dict(status=status, q=q, sort=sort, limit=limit, cursor=cursor)),
    )


@router.post("", response_model=CaseDetail)
async def create_case(
    data: CaseCreate,
    auth: AuthContext = Depends(get_auth),
    cases: IncidentService = Depends(service),
):
    return await cases.create(auth, data)


@router.get("/{id}", response_model=CaseDetail)
async def get_case(
    id: UUID, auth: AuthContext = Depends(get_auth), cases: IncidentService = Depends(service)
):
    return await cases.get_case(auth, id)


@router.patch("/{id}", response_model=CaseDetail)
async def update_case(
    id: UUID,
    data: CasePatch,
    auth: AuthContext = Depends(get_auth),
    cases: IncidentService = Depends(service),
):
    return await cases.update(auth, id, data)


@router.delete("/{id}", status_code=204)
async def delete_case(
    id: UUID,
    request: Request,
    auth: AuthContext = Depends(get_auth),
    cases: IncidentService = Depends(service),
):
    await cases.delete(auth, id)
    try:
        await purge_once(request.app.state.engine, request.app.state.storage)
    except Exception:
        logging.getLogger(__name__).warning("case.evidence_purge_deferred")
    return Response(status_code=204)


@router.get("/{id}/related", response_model=Page[CaseSummary])
async def related_cases(
    id: UUID, auth: AuthContext = Depends(get_auth), cases: IncidentService = Depends(service)
):
    return Page[CaseSummary](items=await cases.related(auth, id), next_cursor=None)


@router.post("/{id}/events", response_model=TimelineEvent)
async def add_event(
    id: UUID,
    data: EventWrite,
    auth: AuthContext = Depends(get_auth),
    cases: IncidentService = Depends(service),
):
    return await cases.add_event(auth, id, data)


@router.patch("/{id}/events/{event_id}", response_model=TimelineEvent)
async def update_event(
    id: UUID,
    event_id: UUID,
    data: EventWrite,
    auth: AuthContext = Depends(get_auth),
    cases: IncidentService = Depends(service),
):
    if event_id != data.id:
        raise ApiError("validation_failed", "Định danh mốc không khớp.", 422)
    return await cases.update_event(auth, id, data)


@router.delete("/{id}/events/{event_id}", status_code=204)
async def remove_event(
    id: UUID,
    event_id: UUID,
    auth: AuthContext = Depends(get_auth),
    cases: IncidentService = Depends(service),
):
    await cases.remove_event(auth, id, event_id)
    return Response(status_code=204)
