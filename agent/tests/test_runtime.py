import asyncio
import json
from dataclasses import replace
from types import SimpleNamespace
from typing import cast
from uuid import uuid4

from agents import RunContextWrapper, SQLiteSession
from agents.testing import ModelStep, ScriptedModel, assistant_message, function_call
from agents.usage import Usage
from safevoice_agent.budget import RunToolBudget
from safevoice_agent.companion import PROMPT_VERSION
from safevoice_agent.runtime import CompanionRuntime
from safevoice_agent.tools.registry import ToolRegistry
from safevoice_shared.config import AppConfig
from safevoice_shared.contracts.agent import AgentServices, AgentToolContext, ToolPolicy
from safevoice_shared.contracts.auth import AuthContext
from safevoice_shared.contracts.context import ContextBundle
from safevoice_shared.contracts.streaming import STREAM_EVENT_ADAPTER


def context():
    return AgentToolContext(
        auth=AuthContext(uuid4(), "synthetic-session", "aal1", '{"private":"auth-canary"}'),
        request_id="test",
        conversation_id=uuid4(),
        run_id=uuid4(),
        age_band=None,
        services=cast(AgentServices, SimpleNamespace()),
        context=ContextBundle(),
        budget=RunToolBudget(),
    )


async def collect(runtime, ctx, model_input="Xin chào", session=None):
    return [
        event
        async for event in runtime.stream_turn(
            ctx=ctx,
            user_input=model_input,
            session=session or SQLiteSession(str(ctx.conversation_id)),
        )
    ]


async def test_event_order_seq_usage_and_privacy_without_api_key(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    model = ScriptedModel(
        [
            ModelStep(
                output=[function_call("get_server_time", {}, call_id="clock")],
                usage=Usage(requests=1, input_tokens=5, output_tokens=2, total_tokens=7),
            ),
            ModelStep(
                output=[assistant_message("Mình đang nghe.")],
                usage=Usage(requests=1, input_tokens=8, output_tokens=4, total_tokens=12),
            ),
        ]
    )
    runtime, ctx = CompanionRuntime(AppConfig(), model=model), context()
    events = await collect(runtime, ctx)
    assert events[0].event == "run.started"
    assert [e.event for e in events][-2:] == ["run.usage", "run.completed"]
    assert [e.seq for e in events] == list(range(1, len(events) + 1))
    assert all(
        STREAM_EVENT_ADAPTER.validate_json(e.model_dump_json(by_alias=True)) == e for e in events
    )
    assert next(e.data for e in events if e.event == "run.usage").total_tokens == 19
    assert next(e.data for e in events if e.event == "run.usage").tool_calls == 1
    assert (
        next(e.data for e in events if e.event == "message.completed").content == "Mình đang nghe."
    )
    assert next(e.data for e in events if e.event == "tool.started").model_dump().keys() == {
        "call_id",
        "tool",
        "label",
    }
    assert "arguments" not in "".join(e.model_dump_json() for e in events)
    assert "auth-canary" not in "".join(e.model_dump_json() for e in events)
    assert all(
        call.model_settings.store is False and call.tracing.is_disabled() is not False
        for call in model.calls
    )
    assert runtime.prompt_version == PROMPT_VERSION
    model.assert_complete()


async def test_model_error_maps_without_raw_text() -> None:
    events = await collect(
        CompanionRuntime(AppConfig(), model=ScriptedModel([RuntimeError("private-canary")])),
        context(),
    )
    assert events[-1].event == "run.failed"
    assert events[-1].data.code == "internal_error"
    assert "private-canary" not in "".join(e.model_dump_json() for e in events)


async def test_explicit_openai_client_keeps_offline_model_independent() -> None:
    from openai import AsyncOpenAI

    client = AsyncOpenAI(api_key="synthetic-not-a-real-key", base_url="http://127.0.0.1:9")
    try:
        runtime = CompanionRuntime(
            AppConfig(),
            model=ScriptedModel([[assistant_message("Chào An.")]]),
            openai_client=client,
        )
        events = await collect(runtime, context())
        assert events[-1].data.status == "completed"
        provider_model = runtime.run_config().model_provider.get_model(AppConfig().openai_model)
        assert provider_model._client is client
    finally:
        await client.close()


async def test_run_timeout_cancels_and_heartbeat_emitted() -> None:
    cleanup = asyncio.Event()

    async def slow(call):
        try:
            await asyncio.Event().wait()
            return [assistant_message("never")]
        finally:
            await asyncio.sleep(0.02)
            cleanup.set()

    cfg = replace(
        AppConfig(), agent=replace(AppConfig().agent, run_timeout_s=1, heartbeat_interval_s=0.01)
    )
    events = await collect(
        CompanionRuntime(cfg, model=ScriptedModel([ModelStep.respond(slow)])), context()
    )
    assert any(e.event == "heartbeat" for e in events)
    assert events[-1].event == "run.failed"
    assert events[-1].data.code == "run_timeout"
    assert cleanup.is_set(), "runtime returned while the SDK model task was still alive"


async def test_max_turns_failed() -> None:
    cfg = replace(AppConfig(), agent=replace(AppConfig().agent, max_turns=1))
    model = ScriptedModel([[function_call("get_server_time", {}, call_id="a")]])
    events = await collect(CompanionRuntime(cfg, model=model), context())
    assert events[-1].data.code == "max_turns"


async def test_total_tool_budget_failed() -> None:
    model = ScriptedModel(
        [
            [function_call("get_server_time", {}, call_id="a")],
            [function_call("get_server_time", {}, call_id="b")],
        ]
    )
    ctx = context()
    ctx.budget = RunToolBudget(max_calls=1)
    events = await collect(CompanionRuntime(AppConfig(), model=model), ctx)
    assert events[-1].data.code == "tool_budget_exceeded"


async def test_runtime_caps_budget_to_configured_total_limit() -> None:
    model = ScriptedModel(
        [
            [function_call("get_server_time", {}, call_id="a")],
            [function_call("get_server_time", {}, call_id="b")],
        ]
    )
    cfg = replace(AppConfig(), agent=replace(AppConfig().agent, max_tool_calls_per_run=1))
    events = await collect(CompanionRuntime(cfg, model=model), context())
    assert events[-1].data.code == "tool_budget_exceeded"


async def test_approved_memory_is_in_instructions_and_never_in_replay_history() -> None:
    from datetime import UTC, datetime

    from safevoice_shared.contracts.context import ContextSection, Provenance

    ctx, session = context(), SQLiteSession("private-memory")
    ctx.context = ContextBundle(
        sections=[
            ContextSection(
                kind="memory",
                text="approved-memory-canary",
                tokens=8,
                priority=500,
                provenance=[
                    Provenance(
                        source_kind="approved_memory",
                        source_id="memory-1",
                        retrieved_at=datetime.now(UTC),
                    )
                ],
            )
        ],
        total_tokens=8,
    )
    model = ScriptedModel([[assistant_message("Mình đang nghe.")]])
    await collect(CompanionRuntime(AppConfig(), model=model), ctx, session=session)
    assert "approved-memory-canary" in model.calls[0].system_instructions
    assert "approved-memory-canary" not in json.dumps(await session.get_items())


async def test_reasoning_is_never_forwarded() -> None:
    from openai.types.responses import ResponseReasoningItem

    model = ScriptedModel(
        [
            [
                ResponseReasoningItem(
                    id="private-reasoning",
                    type="reasoning",
                    summary=[{"type": "summary_text", "text": "reasoning-canary"}],
                ),
                assistant_message("Mình hiểu."),
            ]
        ]
    )
    events = await collect(CompanionRuntime(AppConfig(), model=model), context())
    assert events[-1].data.status == "completed"
    assert "reasoning-canary" not in "".join(e.model_dump_json() for e in events)


async def test_cancel_after_turn_finishes_session() -> None:
    release = asyncio.Event()
    entered = asyncio.Event()

    async def delayed(call):
        entered.set()
        await release.wait()
        return [assistant_message("Đã dừng.")]

    runtime = CompanionRuntime(AppConfig(), model=ScriptedModel([ModelStep.respond(delayed)]))
    ctx, session = context(), SQLiteSession("cancel")
    task = asyncio.create_task(collect(runtime, ctx, session=session))
    await entered.wait()
    assert runtime.cancel(ctx.run_id)
    release.set()
    events = await task
    assert events[-1].data.status == "cancelled"
    assert await session.get_items()
    assert not runtime.cancel(ctx.run_id)


def write_registry(executions):
    async def save_test(ctx: RunContextWrapper[AgentToolContext], note: str) -> str:
        executions.append(note)
        return "saved"

    registry = ToolRegistry()
    registry.register(save_test, ToolPolicy("save_test", "1", "write", True, 15, 1))
    return registry


async def test_write_pauses_serialized_state_has_no_auth_and_resumes_after_recreated_runtime() -> (
    None
):
    executed = []
    model = ScriptedModel([[function_call("save_test", {"note": "synthetic"}, call_id="write-1")]])
    ctx, session = context(), SQLiteSession("approval")
    runtime = CompanionRuntime(AppConfig(), write_registry(executed), model=model)
    events = await collect(runtime, ctx, session=session)
    assert events[-1].data.status == "awaiting_approval"
    assert executed == []
    checkpoint = runtime.pending_approvals(ctx.run_id)[0]
    assert checkpoint.preview == {}
    assert "auth-canary" not in checkpoint.serialized_state
    assert "claims_json" not in checkpoint.serialized_state
    model2 = ScriptedModel([[assistant_message("Đã lưu.")]])
    runtime2 = CompanionRuntime(AppConfig(), write_registry(executed), model=model2)
    resumed = [
        e
        async for e in runtime2.resume_after_approval(
            ctx=ctx,
            serialized_state=checkpoint.serialized_state,
            approved=True,
            session=session,
        )
    ]
    assert executed == ["synthetic"]
    assert resumed[-1].data.status == "completed"
    assert resumed[0].seq > events[-1].seq
    model2.assert_complete()


async def test_reject_returns_message_to_model_without_executing_write() -> None:
    executed, ctx, session = [], context(), SQLiteSession("rejection")
    runtime = CompanionRuntime(
        AppConfig(),
        write_registry(executed),
        model=ScriptedModel(
            [
                [function_call("save_test", {"note": "synthetic"}, call_id="write-1")],
            ]
        ),
    )
    await collect(runtime, ctx, session=session)
    checkpoint = runtime.pending_approvals(ctx.run_id)[0]
    model = ScriptedModel([[assistant_message("Mình chưa lưu.")]])
    fresh = CompanionRuntime(AppConfig(), write_registry(executed), model=model)
    events = [
        e
        async for e in fresh.resume_after_approval(
            ctx=ctx,
            serialized_state=checkpoint.serialized_state,
            approved=False,
            session=session,
        )
    ]
    assert executed == []
    assert "Người dùng" in json.dumps(model.calls[0].input, ensure_ascii=False)
    assert events[-1].data.status == "completed"
