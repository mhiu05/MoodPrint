"""Roleplay practice: sessions are conversations in a no-tools partner mode (see conversations)."""

from uuid import UUID

from fastapi import APIRouter, Depends, Request
from moodprint_shared.contracts.auth import AuthContext
from moodprint_shared.contracts.paging import Page

from app.core.auth import get_auth
from app.modules.incidents.service import IncidentService
from app.modules.profiles.service import ProfileService
from app.modules.roleplay.schemas import RoleplayCreate, RoleplayRead, ScenarioRead
from app.modules.roleplay.service import RoleplayService, scenarios

router = APIRouter(prefix="/v1/roleplay", tags=["roleplay"])


def roleplay_service(request: Request) -> RoleplayService:
    state = request.app.state
    runtime = getattr(state, "runtime", None)
    return RoleplayService(state.engine, state.cfg, getattr(runtime, "openai_client", None))


@router.get("/scenarios", response_model=Page[ScenarioRead])
async def list_scenarios(auth: AuthContext = Depends(get_auth)) -> Page[ScenarioRead]:
    return Page(items=scenarios(), next_cursor=None)


@router.post("/sessions", response_model=RoleplayRead)
async def create_session(
    body: RoleplayCreate, request: Request, auth: AuthContext = Depends(get_auth)
) -> RoleplayRead:
    state = request.app.state
    case_exists = False
    if body.linked_case_id is not None:
        # Ownership is verified by the domain service (404 for someone else's case).
        await IncidentService(state.engine).get_case(auth, body.linked_case_id)
        case_exists = True
    profile = await ProfileService(state.engine).get(auth)
    return await roleplay_service(request).create(
        auth, body, age_band=profile.age_band, case_exists=case_exists
    )


@router.get("/sessions", response_model=Page[RoleplayRead])
async def list_sessions(
    request: Request, auth: AuthContext = Depends(get_auth)
) -> Page[RoleplayRead]:
    return Page(items=await roleplay_service(request).list(auth), next_cursor=None)


@router.get("/sessions/{session_id}", response_model=RoleplayRead)
async def get_session(
    session_id: UUID, request: Request, auth: AuthContext = Depends(get_auth)
) -> RoleplayRead:
    return await roleplay_service(request).get(auth, session_id)


@router.post("/sessions/{session_id}/complete", response_model=RoleplayRead)
async def complete_session(
    session_id: UUID, request: Request, auth: AuthContext = Depends(get_auth)
) -> RoleplayRead:
    return await roleplay_service(request).complete(auth, session_id)


@router.post("/sessions/{session_id}/abandon", response_model=RoleplayRead)
async def abandon_session(
    session_id: UUID, request: Request, auth: AuthContext = Depends(get_auth)
) -> RoleplayRead:
    return await roleplay_service(request).abandon(auth, session_id)
