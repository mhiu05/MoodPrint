import json
from types import SimpleNamespace
from uuid import uuid4

import pytest
from moodprint_shared.config import AppConfig
from moodprint_shared.contracts.auth import AuthContext
from moodprint_shared.contracts.knowledge import KnowledgeQuery, KnowledgeResult, RetrievalScope


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
async def test_context_retriever_can_be_injected_without_changing_default(monkeypatch, injected):
    from app.agent_gateway.wiring import build_context

    async def profile(self, auth):
        return SimpleNamespace(nickname="Synthetic", age_band=None, locale="vi")

    monkeypatch.setattr("app.agent_gateway.wiring.ProfileService.get", profile)
    monkeypatch.setattr("app.agent_gateway.wiring.MemoryService", lambda engine, cfg: EmptyMemory())
    owner = uuid4()
    auth = AuthContext(
        user_id=owner,
        session_id=None,
        aal="aal1",
        claims_json=json.dumps({"sub": str(owner), "role": "authenticated"}),
    )
    kwargs = {"knowledge": NoResultsRetriever()} if injected else {}
    ctx = await build_context(
        None,
        AppConfig(),
        auth,
        {"id": uuid4(), "linked_case_id": None, "summary": None},
        uuid4(),
        "wiring-test",
        "Synthetic context",
        **kwargs,
    )
    result = await ctx.services.knowledge.search(
        KnowledgeQuery(text="friends"),
        scope=RetrievalScope(request_id=ctx.request_id),
        timeout_s=1,
    )
    assert result.corpus_version == ("injected-empty-v1" if injected else "synthetic-fixture-v1")
    assert ctx.context.sections[0].kind == "identity"


def test_runtime_factory_retains_only_diagnostic_tool():
    from app.agent_gateway.wiring import build_runtime

    runtime = build_runtime(AppConfig(), None)
    assert [tool.name for tool in runtime.agent.tools] == ["get_server_time"]
