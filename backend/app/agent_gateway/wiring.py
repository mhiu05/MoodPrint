import os
from dataclasses import replace
from uuid import UUID

from openai import AsyncOpenAI
from safevoice_agent.budget import RunToolBudget
from safevoice_agent.memory.context_builder import DomainSummary, MemoryContextBuilder
from safevoice_agent.runtime import CompanionRuntime
from safevoice_agent.tools.context import CompanionToolContext, ToolDeps
from safevoice_agent.tools.factory import build_registry
from safevoice_agent.tools.risk_assessor import OpenAIRiskAssessor
from safevoice_shared.config import AppConfig
from safevoice_shared.contracts.agent import AgentServices
from safevoice_shared.contracts.context import ContextBundle, ContextRequest
from safevoice_shared.contracts.errors import NotFound
from safevoice_shared.contracts.knowledge import KnowledgeRetriever
from safevoice_shared.contracts.paging import Page

from app.agent_gateway.proposals import SqlConfirmedEventWriter, SqlPlanWriter, SqlProposalStore
from app.modules.evidence.service import EvidenceService
from app.modules.incidents.service import IncidentService
from app.modules.memory.service import MemoryService
from app.modules.plans.service import ActionPlanService
from app.modules.profiles.service import ProfileService
from app.modules.roleplay.service import RoleplayService


def _require_retriever(knowledge: KnowledgeRetriever | None) -> KnowledgeRetriever:
    """A turn without a configured retriever fails; it never answers from synthetic fixtures.

    ``is None`` on purpose: an injected adapter may be falsey and is still the adapter.
    """
    if knowledge is None:
        raise ValueError(
            "No knowledge retriever is configured for this turn; refusing to use the fixture"
        )
    return knowledge


class CaseHeadlines:
    """Headline-only view of the linked case for the context (never events or evidence)."""

    def __init__(self, incidents: IncidentService) -> None:
        self._incidents = incidents

    async def summary(self, auth, case_id: UUID) -> DomainSummary | None:
        try:
            case = await self._incidents.get_case(auth, case_id)
        except Exception:  # not found / not the caller's: no context, never an error
            return None
        return DomainSummary(
            title=case.title,
            status=case.status,
            event_count=len(case.events),
            updated_at=case.updated_at,
        )


class DeferredDomainServices:
    """Phase 0 has no domain tools; unavailable domain lookups are explicit."""

    async def list_cases(self, auth, query):
        return Page(items=[], next_cursor=None)

    async def get_case(self, auth, case_id):
        raise NotFound()

    async def add_event(self, auth, case_id, data):
        raise NotFound()

    async def list_for_case(self, auth, case_id):
        return []

    async def get(self, auth, evidence_id):
        raise NotFound()

    async def open_read_url(self, auth, evidence_id, purpose):
        raise NotFound()

    async def add_derivative(self, auth, evidence_id, data):
        raise NotFound()

    async def get_for_case(self, auth, case_id):
        return None

    async def upsert(self, auth, case_id, data, *, expected_version):
        raise NotFound()

    async def set_item_status(self, auth, plan_id, item_id, status):
        raise NotFound()


def build_runtime(cfg: AppConfig, model_client: AsyncOpenAI | None) -> CompanionRuntime:
    """Frozen signature (CC-002). The registry is a pure function of the config."""
    # Model-assisted urgency is opt-in (it sends the student's words to the external model once more).
    # Default off: the deterministic layer alone runs. See agent/evals/spikes/S-06.md.
    assessor = (
        OpenAIRiskAssessor(model_client, cfg)
        if model_client is not None and os.environ.get("SAFEVOICE_MODEL_ASSISTED_SAFETY") == "1"
        else None
    )
    return CompanionRuntime(
        cfg, build_registry(cfg), openai_client=model_client, risk_assessor=assessor
    )


async def build_context(
    engine,
    cfg: AppConfig,
    auth,
    conversation,
    run_id: UUID,
    request_id: str,
    content: str,
    knowledge: KnowledgeRetriever | None = None,
    storage=None,
    analysis=None,
):
    """Fresh context for every turn and every resume; nothing global, no engine in tools."""
    memory = MemoryService(engine, cfg)
    profile = await ProfileService(engine).get(auth)
    incidents, plans = IncidentService(engine), ActionPlanService(engine)
    roleplay = await _roleplay_context(engine, cfg, auth, conversation["id"], incidents)
    request = ContextRequest(
        auth=auth,
        conversation_id=conversation["id"],
        user_input=content,
        linked_case_id=conversation["linked_case_id"],
        token_budget=4096,
        nickname=profile.nickname,
        age_band=profile.age_band,
        locale=profile.locale,
        conversation_summary=conversation["summary"],
    )
    # A practice partner sees neither memory nor the case file unless the user opted in.
    bundle = (
        ContextBundle()
        if roleplay is not None
        else await MemoryContextBuilder(memory, cfg, domain=CaseHeadlines(incidents)).build(request)
    )
    if roleplay is None:
        bundle = await _with_attachments(engine, cfg, auth, run_id, bundle)
    store = SqlProposalStore(engine, cfg)
    return CompanionToolContext(
        auth=auth,
        request_id=request_id,
        conversation_id=conversation["id"],
        run_id=run_id,
        age_band=profile.age_band,
        services=AgentServices(
            incidents=incidents,
            evidence=EvidenceService(engine, storage, cfg),
            plans=plans,
            memory=memory,
            knowledge=_require_retriever(knowledge),
        ),
        context=bundle,
        budget=RunToolBudget(cfg.agent.max_tool_calls_per_run),
        locale=profile.locale,
        deps=ToolDeps(
            proposals=store,
            events=SqlConfirmedEventWriter(store, incidents),
            plans=SqlPlanWriter(store, plans),
            analysis=analysis,
        ),
        knowledge_timeout_s=max(1.0, cfg.agent.knowledge_tool_timeout_s - 1),
        memory_candidates_max=cfg.memory.extraction_max_candidates_per_run,
        mode="roleplay" if roleplay is not None else "companion",
        roleplay=roleplay,
    )


async def _roleplay_context(engine, cfg: AppConfig, auth, conversation_id: UUID, incidents):
    service = RoleplayService(engine, cfg)
    context = await service.context_for(auth, conversation_id)
    if context is None:
        return None
    case_id = await service.linked_case(auth, conversation_id)
    if case_id is None:
        return context
    try:
        case = await incidents.get_case(auth, case_id)
    except Exception:  # the case may have been deleted since: practise without it
        return context
    summary = f"{case.title} ({case.status}); {len(case.events)} mốc; {case.summary[:300]}"
    return replace(context, case_summary=summary)


async def _with_attachments(engine, cfg: AppConfig, auth, run_id: UUID, bundle: ContextBundle):
    """Tell the model *that* images are attached (id, name, kind), never what is in them."""
    from datetime import UTC, datetime

    from safevoice_shared.contracts.context import ContextSection, Provenance

    from app.modules.conversations.service import ConversationService

    rows = await ConversationService(engine, cfg).attachments_for_run(auth, run_id)
    if not rows:
        return bundle
    listing = "; ".join(
        f"{row['id']} ({row['original_filename'] or 'ảnh'}, {row['kind']})" for row in rows[:3]
    )
    text = (
        "Bằng chứng đính kèm tin nhắn này (chỉ là danh sách, chưa được đọc; muốn đọc phải "
        f"dùng analyze_evidence và chờ người dùng đồng ý): {listing}"
    )
    section = ContextSection(
        kind="domain",
        text=text,
        provenance=[
            Provenance(
                source_kind="attachment",
                source_id=str(rows[0]["id"]),
                retrieved_at=datetime.now(UTC),
            )
        ],
        tokens=max(1, len(text) // 3),
        priority=5,
    )
    return bundle.model_copy(
        update={
            "sections": [*bundle.sections, section],
            "total_tokens": bundle.total_tokens + section.tokens,
        }
    )
