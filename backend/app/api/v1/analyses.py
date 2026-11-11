"""Evidence analysis: a consent-gated, idempotent read of one uploaded image."""

from uuid import UUID

from fastapi import APIRouter, Depends, Request
from safevoice_shared.contracts.auth import AuthContext

from app.core.auth import get_auth
from app.modules.analysis.schemas import AnalysisCreate, AnalysisRead
from app.modules.analysis.service import AnalysisService
from app.modules.evidence.service import EvidenceService

router = APIRouter(prefix="/v1/analyses", tags=["analyses"])


def analysis_service(request: Request) -> AnalysisService:
    state = request.app.state
    runtime = getattr(state, "runtime", None)
    return AnalysisService(
        state.engine,
        state.cfg,
        EvidenceService(state.engine, state.storage, state.cfg),
        getattr(runtime, "openai_client", None),
        storage_base_url=state.settings.supabase_url,
        production=state.settings.app_env == "production",
        tasks=state.run_tasks,
    )


@router.post("", response_model=AnalysisRead)
async def create_analysis(
    body: AnalysisCreate, request: Request, auth: AuthContext = Depends(get_auth)
) -> AnalysisRead:
    return await analysis_service(request).create(auth, body)


@router.get("/{analysis_id}", response_model=AnalysisRead)
async def get_analysis(
    analysis_id: UUID, request: Request, auth: AuthContext = Depends(get_auth)
) -> AnalysisRead:
    return await analysis_service(request).get(auth, analysis_id)
