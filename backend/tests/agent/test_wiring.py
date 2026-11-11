import json
from types import SimpleNamespace
from uuid import uuid4

import pytest
from safevoice_shared.config import AppConfig
from safevoice_shared.contracts.auth import AuthContext
from safevoice_shared.contracts.knowledge import KnowledgeQuery, KnowledgeResult, RetrievalScope


class EmptyMemory:
    async def search(self, auth, query):
        return []


class NoResultsRetriever:
    # A falsey injected adapter must not be replaced by the default fixture.
    def __bool__(self):
        return False

    async def search(self, query, *, scope, timeout_s):
        return KnowledgeResult(
            status="no_results", chunks=[], corpus_version="injected-empty-v1", latency_ms=0
        )


@pytest.mark.parametrize("injected", [False, True])
async def test_context_requires_an_explicit_retriever_and_never_substitutes_the_fixture(
    monkeypatch, injected
):
    from app.agent_gateway.wiring import build_context

    async def profile(self, auth):
        return SimpleNamespace(nickname="Synthetic", age_band=None, locale="vi")

    monkeypatch.setattr("app.agent_gateway.wiring.ProfileService.get", profile)
    monkeypatch.setattr("app.agent_gateway.wiring.MemoryService", lambda engine, cfg: EmptyMemory())

    async def no_roleplay(engine, cfg, auth, conversation_id, incidents):
        return None  # an ordinary chat; the roleplay/attachment lookups are covered in integration

    async def no_attachments(engine, cfg, auth, run_id, bundle):
        return bundle

    monkeypatch.setattr("app.agent_gateway.wiring._roleplay_context", no_roleplay)
    monkeypatch.setattr("app.agent_gateway.wiring._with_attachments", no_attachments)
    owner = uuid4()
    auth = AuthContext(
        user_id=owner,
        session_id=None,
        aal="aal1",
        claims_json=json.dumps({"sub": str(owner), "role": "authenticated"}),
    )
    kwargs = {"knowledge": NoResultsRetriever()} if injected else {}
    call = build_context(
        None,
        AppConfig(),
        auth,
        {"id": uuid4(), "linked_case_id": None, "summary": None},
        uuid4(),
        "wiring-test",
        "Synthetic context",
        **kwargs,
    )
    if not injected:
        # No retriever must be an error, never the synthetic fixture.
        with pytest.raises(ValueError, match="knowledge retriever"):
            await call
        return
    ctx = await call
    result = await ctx.services.knowledge.search(
        KnowledgeQuery(text="friends"),
        scope=RetrievalScope(request_id=ctx.request_id),
        timeout_s=1,
    )
    assert result.corpus_version == "injected-empty-v1"
    assert ctx.context.sections[0].kind == "identity"


def test_runtime_factory_registers_the_phase3_inventory_without_database_or_client():
    """Phase 0 exposed only get_server_time; Phase 3 pins the real inventory (CC-002 signature)."""
    from app.agent_gateway.wiring import build_runtime

    runtime = build_runtime(AppConfig(), None)
    names = sorted(tool.name for tool in runtime.agent.tools)
    assert "get_server_time" not in names
    assert names == sorted(runtime.registry.names())
    assert {"knowledge_search", "save_confirmed_event", "save_plan", "propose_memory"} <= set(names)
    assert runtime.prompt_version == "companion_v5"
    assert build_runtime(AppConfig(), None).tools_version == runtime.tools_version
