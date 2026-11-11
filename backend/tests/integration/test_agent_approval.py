from uuid import uuid4

import pytest
from agents import RunContextWrapper
from agents.testing import ModelStep, ScriptedModel, assistant_message, function_call
from agents.usage import Usage
from app.agent_gateway.sse import RunStream, produce
from app.modules.conversations.approvals import ApprovalService
from app.modules.conversations.service import ConversationService
from safevoice_agent.runtime import CompanionRuntime
from safevoice_agent.tools.registry import ToolRegistry
from safevoice_shared.config import AppConfig
from safevoice_shared.contracts.agent import AgentToolContext, ToolPolicy
from safevoice_shared.contracts.errors import NotFound, VersionConflict
from safevoice_shared.testing.knowledge_fixture import FixtureKnowledgeRetriever

pytestmark = pytest.mark.integration


def registry(executed):
    async def save_test(ctx: RunContextWrapper[AgentToolContext], note: str) -> str:
        executed.append(note)
        return "saved"

    tools = ToolRegistry()
    tools.register(save_test, ToolPolicy("save_test", "1", "write", True, 15, 1))
    return tools


async def test_approval_persisted_owner_decision_restart_and_cumulative_usage(
    db_engine, identities
):
    auth, other = identities
    executed = []
    service = ConversationService(db_engine)
    conversation = await service.create(auth, uuid4())
    turn = await service.begin_turn(auth, conversation["id"], uuid4(), "Synthetic approval test")
    first = CompanionRuntime(
        AppConfig(),
        registry(executed),
        model=ScriptedModel(
            [
                ModelStep(
                    output=[function_call("save_test", {"note": "synthetic"}, call_id="save-1")],
                    usage=Usage(input_tokens=5, output_tokens=2, total_tokens=7, requests=1),
                )
            ]
        ),
    )
    stream = RunStream()
    await produce(
        knowledge=FixtureKnowledgeRetriever(),
        stream=stream,
        runtime=first,
        service=service,
        auth=auth,
        turn=turn,
        request_id="approval-test",
        content="Synthetic approval test",
    )
    checkpoint = first.pending_approvals(turn.run_id)[0]
    assert executed == []
    assert (await service.get_run(auth, turn.run_id))["status"] == "awaiting_approval"
    approvals = ApprovalService(db_engine)
    with pytest.raises(NotFound):
        await approvals.decide(other, turn.run_id, checkpoint.id, True)
    row, _ = await approvals.decide(auth, turn.run_id, checkpoint.id, True)
    with pytest.raises(VersionConflict):
        await approvals.decide(auth, turn.run_id, checkpoint.id, True)
    second = CompanionRuntime(
        AppConfig(),
        registry(executed),
        model=ScriptedModel(
            [
                ModelStep(
                    output=[assistant_message("Đã lưu nội dung tổng hợp.")],
                    usage=Usage(input_tokens=8, output_tokens=4, total_tokens=12, requests=1),
                )
            ]
        ),
    )
    await produce(
        knowledge=FixtureKnowledgeRetriever(),
        stream=RunStream(),
        runtime=second,
        service=service,
        auth=auth,
        turn=turn,
        request_id="approval-test-resumed",
        content="",
        resume={**row, "approved": True},
    )
    assert executed == ["synthetic"]
    run = await service.get_run(auth, turn.run_id)
    assert run["status"] == "completed"
    assert run["total_tokens"] == 19
    assert run["request_count"] == 2
    assert run["tool_call_count"] == 1
    await service.delete(auth, conversation["id"])
