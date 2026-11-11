from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response
from pydantic import Field
from safevoice_shared.contracts.auth import AuthContext
from safevoice_shared.contracts.base import FrozenDTO
from safevoice_shared.contracts.memory import (
    CandidateDecision,
    Memory,
    MemoryCandidate,
    MemoryCreate,
)
from safevoice_shared.contracts.paging import Page

from app.core.auth import get_auth
from app.modules.conversations.paging import FoundationPages
from app.modules.memory.service import MemoryService

router = APIRouter(prefix="/v1", tags=["memory"])


def service(request: Request) -> MemoryService:
    return MemoryService(request.app.state.engine, request.app.state.cfg)


@router.get("/memories", response_model=Page[Memory])
async def list_memories(
    limit: int = Query(default=50, ge=1, le=100),
    cursor: str | None = Query(default=None, max_length=2048),
    auth: AuthContext = Depends(get_auth),
    memory: MemoryService = Depends(service),
):
    return await FoundationPages(memory.engine).memories(auth, limit=limit, cursor=cursor)


@router.post("/memories", response_model=Memory)
async def create_memory(
    data: MemoryCreate,
    auth: AuthContext = Depends(get_auth),
    memory: MemoryService = Depends(service),
):
    return (await memory.create(auth, data)).model_dump(mode="json", by_alias=True)


class MemoryEdit(FrozenDTO):
    content: str = Field(min_length=1, max_length=500)


@router.patch("/memories/{id}", response_model=Memory)
async def edit_memory(
    id: UUID,
    data: MemoryEdit,
    auth: AuthContext = Depends(get_auth),
    memory: MemoryService = Depends(service),
):
    return (await memory.update(auth, id, data.content)).model_dump(mode="json", by_alias=True)


@router.delete("/memories/{id}", status_code=204)
async def delete_memory(
    id: UUID, auth: AuthContext = Depends(get_auth), memory: MemoryService = Depends(service)
):
    await memory.delete(auth, id)
    return Response(status_code=204)


@router.get("/memory-candidates", response_model=Page[MemoryCandidate])
async def candidates(
    limit: int = Query(default=50, ge=1, le=100),
    cursor: str | None = Query(default=None, max_length=2048),
    auth: AuthContext = Depends(get_auth),
    memory: MemoryService = Depends(service),
):
    return await FoundationPages(memory.engine).candidates(auth, limit=limit, cursor=cursor)


@router.post("/memory-candidates/{id}/decision", response_model=Memory | None)
async def decide(
    id: UUID,
    data: CandidateDecision,
    auth: AuthContext = Depends(get_auth),
    memory: MemoryService = Depends(service),
):
    result = await memory.decide(auth, id, data)
    return result.model_dump(mode="json", by_alias=True) if result else None
