from uuid import UUID

from moodprint_agent.budget import RunToolBudget
from moodprint_agent.memory.context_builder import MemoryContextBuilder
from moodprint_agent.runtime import CompanionRuntime
from moodprint_agent.tools.context import CompanionToolContext, ToolDeps
from moodprint_agent.tools.factory import build_registry
from moodprint_shared.config import AppConfig
from moodprint_shared.contracts.agent import AgentServices
from moodprint_shared.contracts.context import ContextRequest
from moodprint_shared.contracts.errors import NotFound
from moodprint_shared.contracts.knowledge import KnowledgeRetriever
from moodprint_shared.contracts.paging import Page
from moodprint_shared.testing.knowledge_fixture import FixtureKnowledgeRetriever
from openai import AsyncOpenAI

from app.agent_gateway.proposals import SqlConfirmedEventWriter, SqlPlanWriter, SqlProposalStore
from app.modules.evidence.service import EvidenceService
from app.modules.incidents.service import IncidentService
from app.modules.memory.service import MemoryService
from app.modules.plans.service import ActionPlanService
from app.modules.profiles.service import ProfileService


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
    return CompanionRuntime(cfg, build_registry(cfg), openai_client=model_client)


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
):
    """Fresh context for every turn and every resume; nothing global, no engine in tools."""
    memory = MemoryService(engine, cfg)
    profile = await ProfileService(engine).get(auth)
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
    bundle = await MemoryContextBuilder(memory, cfg).build(request)
    incidents, plans = IncidentService(engine), ActionPlanService(engine)
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
            knowledge=knowledge if knowledge is not None else FixtureKnowledgeRetriever(),
        ),
        context=bundle,
        budget=RunToolBudget(cfg.agent.max_tool_calls_per_run),
        locale=profile.locale,
        deps=ToolDeps(
            proposals=store,
            events=SqlConfirmedEventWriter(store, incidents),
            plans=SqlPlanWriter(store, plans),
        ),
        knowledge_timeout_s=max(1.0, cfg.agent.knowledge_tool_timeout_s - 1),
        memory_candidates_max=cfg.memory.extraction_max_candidates_per_run,
    )
