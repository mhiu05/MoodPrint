"""Per-turn tool context. Narrow Protocols only: no engine, secret or JWT ever reaches a tool."""

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Protocol, cast
from uuid import UUID

from moodprint_shared.contracts.agent import AgentToolContext
from moodprint_shared.contracts.auth import AuthContext
from moodprint_shared.contracts.knowledge import SourceCitation

from moodprint_agent.roleplay.models import RoleplayContext
from moodprint_agent.tools.proposals import (
    ApplyOutcome,
    ProposalKind,
    StoredProposal,
)


class ProposalStore(Protocol):
    """Server-owned, immutable proposals. Every call is scoped to the authenticated owner."""

    async def create(
        self,
        auth: AuthContext,
        *,
        conversation_id: UUID,
        run_id: UUID,
        kind: ProposalKind,
        target_case_id: UUID,
        payload: dict[str, Any],
        preview: dict[str, Any],
        base_version: int | None,
        request_key: str,
    ) -> StoredProposal: ...

    async def get(self, auth: AuthContext, proposal_id: UUID) -> StoredProposal | None: ...


class ConfirmedEventWriter(Protocol):
    """Applies an *approved* case-event proposal through the Incident domain service."""

    async def apply(
        self, auth: AuthContext, *, proposal_id: UUID, run_id: UUID
    ) -> ApplyOutcome: ...


class PlanWriter(Protocol):
    """Applies an *approved* action-plan proposal through the ActionPlan domain service."""

    async def apply(
        self, auth: AuthContext, *, proposal_id: UUID, run_id: UUID
    ) -> ApplyOutcome: ...


class AnalysisRunner(Protocol):
    """Consent- and approval-gated image reading; returns text only, never image bytes."""

    async def analyze(
        self, auth: AuthContext, *, evidence_id: UUID, run_id: UUID
    ) -> dict[str, Any]: ...


class SupportDirectory(Protocol):
    def lookup(self, kind: str) -> list[dict[str, Any]]: ...


class EvidenceImageFetcher(Protocol):
    async def fetch(self, auth: AuthContext, evidence_id: UUID) -> bytes: ...


class VisionRunner(Protocol):
    async def read(self, image: bytes, mime: str) -> dict[str, Any]: ...


@dataclass(frozen=True, slots=True)
class ToolDeps:
    proposals: ProposalStore | None = None
    events: ConfirmedEventWriter | None = None
    plans: PlanWriter | None = None
    analysis: AnalysisRunner | None = None
    support: SupportDirectory | None = None


@dataclass(slots=True)
class RunScratch:
    """State that lives exactly as long as one run and travels in its approval checkpoint."""

    citations: dict[str, SourceCitation] = field(default_factory=dict[str, SourceCitation])
    proposals: dict[str, str] = field(default_factory=dict[str, str])
    memory_candidates: int = 0
    assessment: dict[str, Any] | None = None

    def register_citation(self, citation: SourceCitation) -> str:
        """Return the stable ``S<n>`` ref for a retrieved citation, creating it on first use."""
        for ref, existing in self.citations.items():
            if existing == citation:
                return ref
        ref = f"S{len(self.citations) + 1}"
        self.citations[ref] = citation
        return ref

    def snapshot(self) -> dict[str, Any]:
        return {
            "citations": {ref: c.model_dump(mode="json") for ref, c in self.citations.items()},
            "proposals": dict(self.proposals),
            "memory_candidates": self.memory_candidates,
            "assessment": self.assessment,
        }

    @classmethod
    def from_snapshot(cls, data: dict[str, Any]) -> "RunScratch":
        scratch = cls()
        for ref, raw in dict(data.get("citations", {})).items():
            scratch.citations[str(ref)] = SourceCitation.model_validate(raw)
        scratch.proposals = {str(k): str(v) for k, v in dict(data.get("proposals", {})).items()}
        scratch.memory_candidates = int(data.get("memory_candidates", 0))
        assessment = data.get("assessment")
        scratch.assessment = (
            cast(dict[str, Any], assessment) if isinstance(assessment, dict) else None
        )
        return scratch


@dataclass(slots=True)
class CompanionToolContext(AgentToolContext):
    """Shared context plus Phase 3 collaborators (keyword-only; shared contract unchanged)."""

    deps: ToolDeps = field(kw_only=True, default_factory=ToolDeps)
    scratch: RunScratch = field(kw_only=True, default_factory=RunScratch)
    mode: str = field(kw_only=True, default="companion")
    tool_call_id: str | None = field(kw_only=True, default=None)
    knowledge_timeout_s: float = field(kw_only=True, default=7.0)
    safety_hint: str | None = field(kw_only=True, default=None)
    memory_candidates_max: int = field(kw_only=True, default=1)
    roleplay: RoleplayContext | None = field(kw_only=True, default=None)
    # Set by the runtime: True once the user's cancel was acknowledged (linearisation point).
    cancel_check: Callable[[], bool] | None = field(kw_only=True, default=None)

    def cancelled(self) -> bool:
        return self.cancel_check is not None and self.cancel_check()
