"""The E2E runtime is the real Phase 3 wiring with a rule-driven provider (offline proof)."""

from types import SimpleNamespace
from typing import cast
from uuid import uuid4

from agents import SQLiteSession
from moodprint_agent.budget import RunToolBudget
from moodprint_agent.testing.scripted_scenarios import build_e2e_runtime
from moodprint_agent.tools.context import CompanionToolContext
from moodprint_shared.config import AppConfig
from moodprint_shared.contracts.agent import AgentServices
from moodprint_shared.contracts.auth import AuthContext
from moodprint_shared.contracts.context import ContextBundle
from moodprint_shared.testing.knowledge_fixture import FixtureKnowledgeRetriever


def ctx() -> CompanionToolContext:
    return CompanionToolContext(
        auth=AuthContext(uuid4(), "s", "aal1", "{}"),
        request_id="e2e",
        conversation_id=uuid4(),
        run_id=uuid4(),
        age_band=None,
        services=cast(AgentServices, SimpleNamespace(knowledge=FixtureKnowledgeRetriever())),
        context=ContextBundle(),
        budget=RunToolBudget(),
    )


async def test_the_factory_keeps_the_full_phase3_inventory_and_only_swaps_the_provider() -> None:
    runtime = build_e2e_runtime(AppConfig())
    assert {"knowledge_search", "save_confirmed_event", "save_plan", "analyze_evidence"} <= set(
        runtime.registry.names()
    )
    assert "get_server_time" not in runtime.registry.names()  # not the diagnostic default


async def test_a_cited_answer_uses_the_real_knowledge_tool_and_ledger() -> None:
    runtime, context = build_e2e_runtime(AppConfig()), ctx()
    events = [
        e
        async for e in runtime.stream_turn(
            ctx=context,
            user_input="Cho mình nguồn về nhờ người lớn",
            session=SQLiteSession("e2e-1"),
        )
    ]
    assert [e.data.tool for e in events if e.event == "tool.started"] == ["knowledge_search"]
    done = next(e for e in events if e.event == "message.completed").data
    assert len(done.citations) == 1 and done.citations[0].title == "Tìm người hỗ trợ"


async def test_plain_and_urgent_messages_get_text_answers() -> None:
    runtime = build_e2e_runtime(AppConfig())
    for text in ("Xin chào", "Mình muốn chết"):
        events = [
            e
            async for e in runtime.stream_turn(
                ctx=ctx(), user_input=text, session=SQLiteSession(f"e2e-{text}")
            )
        ]
        assert events[-1].data.status == "completed"
    last = next(e for e in events if e.event == "message.completed").data
    assert last.structured is not None and last.structured.urgency == "immediate"
    assert "111" in last.content  # the static block comes from the deterministic layer
