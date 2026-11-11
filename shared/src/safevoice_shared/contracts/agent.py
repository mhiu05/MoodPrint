from dataclasses import dataclass
from typing import Literal, Protocol
from uuid import UUID

from pydantic import Field

from .auth import AuthContext
from .base import AgeBand, FrozenDTO
from .context import ContextBundle
from .evidence import EvidenceService
from .incidents import IncidentService
from .knowledge import KnowledgeRetriever, SourceCitation
from .memory import MemoryService
from .plans import ActionPlanService


class ToolBudget(Protocol):
    @property
    def total_calls(self) -> int: ...
    def consume(self, tool_name: str, max_calls_per_run: int) -> None: ...


@dataclass(frozen=True, slots=True)
class AgentServices:
    incidents: IncidentService
    evidence: EvidenceService
    plans: ActionPlanService
    memory: MemoryService
    knowledge: KnowledgeRetriever


@dataclass(slots=True)
class AgentToolContext:
    auth: AuthContext
    request_id: str
    conversation_id: UUID
    run_id: UUID
    age_band: AgeBand | None
    services: AgentServices
    context: ContextBundle
    budget: ToolBudget
    locale: str = "vi"


@dataclass(frozen=True, slots=True)
class ToolPolicy:
    name: str
    version: str
    access: Literal["read", "prepare", "write"]
    needs_approval: bool
    timeout_s: float
    max_calls_per_run: int


class Finding(FrozenDTO):
    text: str
    source_ids: list[str] = Field(default_factory=list[str])


class SafeOption(FrozenDTO):
    label: str
    description: str = ""


class CompanionTurn(FrozenDTO):
    reply: str
    observed_facts: list[Finding] = Field(default_factory=list[Finding])
    user_reported_facts: list[Finding] = Field(default_factory=list[Finding])
    possible_patterns: list[Finding] = Field(default_factory=list[Finding])
    uncertainties: list[str] = Field(default_factory=list[str])
    clarifying_question: str | None = None
    safe_options: list[SafeOption] = Field(default_factory=list[SafeOption])
    urgency: Literal["none", "elevated", "immediate"] = "none"
    citations: list[SourceCitation] = Field(default_factory=list[SourceCitation])
