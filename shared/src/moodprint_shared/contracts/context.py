from datetime import datetime
from typing import Literal, Protocol
from uuid import UUID

from pydantic import Field

from .auth import AuthContext
from .base import AgeBand, FrozenDTO

ContextKind = Literal["identity", "conversation_summary", "memory", "domain", "knowledge"]


class Provenance(FrozenDTO):
    source_kind: str
    source_id: str
    retrieved_at: datetime
    stale: bool = False


class DroppedSection(FrozenDTO):
    kind: ContextKind
    reason: str
    source_ids: list[str] = Field(default_factory=list[str])


class ContextRequest(FrozenDTO):
    auth: AuthContext = Field(exclude=True, repr=False)
    conversation_id: UUID
    user_input: str
    linked_case_id: UUID | None = None
    token_budget: int = Field(ge=0)
    nickname: str | None = None
    age_band: AgeBand | None = None
    locale: str = "vi"
    conversation_summary: str | None = None


class ContextSection(FrozenDTO):
    kind: ContextKind
    text: str
    provenance: list[Provenance]
    tokens: int = Field(ge=0)
    priority: int


class ContextBundle(FrozenDTO):
    sections: list[ContextSection] = Field(default_factory=list[ContextSection])
    dropped: list[DroppedSection] = Field(default_factory=list[DroppedSection])
    total_tokens: int = Field(default=0, ge=0)


class ContextBuilder(Protocol):
    async def build(self, request: ContextRequest) -> ContextBundle: ...
