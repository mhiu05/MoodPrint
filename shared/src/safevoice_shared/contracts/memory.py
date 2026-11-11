from __future__ import annotations

from datetime import datetime
from typing import Literal, Protocol
from uuid import UUID

from pydantic import Field

from .auth import AuthContext
from .base import FrozenDTO

MemoryCategory = Literal["preference", "communication", "support_person", "goal", "context"]
MemoryStatus = Literal["active", "superseded"]


class MemoryCreate(FrozenDTO):
    category: MemoryCategory
    content: str = Field(min_length=1, max_length=500)
    source_conversation_id: UUID | None = None
    expires_at: datetime | None = None


class Memory(MemoryCreate):
    id: UUID
    owner_id: UUID
    content_hash: str
    status: MemoryStatus = "active"
    supersedes_id: UUID | None = None
    source_kind: Literal["user_created", "approved_candidate"] = "user_created"
    source_candidate_id: UUID | None = None
    last_retrieved_at: datetime | None = None
    version: int = Field(default=1, ge=1)
    created_at: datetime
    updated_at: datetime


class MemoryCandidateCreate(FrozenDTO):
    category: MemoryCategory
    content: str = Field(min_length=1, max_length=500)
    source_kind: Literal["user_explicit", "agent_proposed"] = "agent_proposed"
    source_conversation_id: UUID | None = None
    source_message_id: UUID | None = None
    supersedes_memory_id: UUID | None = None


class MemoryCandidate(MemoryCandidateCreate):
    id: UUID
    owner_id: UUID
    status: Literal["pending", "approved", "rejected", "expired"] = "pending"
    expires_at: datetime
    decided_at: datetime | None = None
    created_at: datetime


class CandidateDecision(FrozenDTO):
    decision: Literal["approve", "reject"]
    edited_content: str | None = Field(default=None, min_length=1, max_length=500)


class MemoryQuery(FrozenDTO):
    text: str = Field(max_length=4000)
    categories: list[MemoryCategory] = Field(default_factory=list[MemoryCategory])
    limit: int = Field(default=5, ge=1, le=20)


class MemoryHit(FrozenDTO):
    memory: Memory
    score: float = Field(ge=0)


class MemoryService(Protocol):
    async def list(self, auth: AuthContext, *, status: MemoryStatus = "active") -> list[Memory]: ...
    async def create(self, auth: AuthContext, data: MemoryCreate) -> Memory: ...
    async def update(self, auth: AuthContext, memory_id: UUID, content: str) -> Memory: ...
    async def delete(self, auth: AuthContext, memory_id: UUID) -> None: ...
    async def propose(self, auth: AuthContext, data: MemoryCandidateCreate) -> MemoryCandidate: ...
    async def decide(
        self, auth: AuthContext, candidate_id: UUID, decision: CandidateDecision
    ) -> Memory | None: ...
    async def search(self, auth: AuthContext, query: MemoryQuery) -> list[MemoryHit]: ...
