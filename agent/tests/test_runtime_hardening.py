"""U-AG-170…195: every failure path ends cleanly; nothing is reported as a success it was not."""

import asyncio
import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from time import perf_counter
from types import SimpleNamespace
from typing import Any, cast
from uuid import UUID, uuid4

import httpx
import pytest
from agents import RunContextWrapper, SQLiteSession
from agents.exceptions import ModelRefusalError, ModelTimeoutError
from agents.testing import ModelStep, ScriptedModel, assistant_message, function_call
from agents.usage import Usage
from moodprint_agent.budget import RunToolBudget
from moodprint_agent.runtime import CompanionRuntime
from moodprint_agent.tools.context import CompanionToolContext, ToolDeps
from moodprint_agent.tools.proposals import ApplyOutcome, StoredProposal, payload_sha256
from moodprint_agent.tools.registry import ToolRegistry
from moodprint_agent.tools.saving import save_approved
from moodprint_shared.config import AppConfig
from moodprint_shared.contracts.agent import AgentServices, AgentToolContext, ToolPolicy
from moodprint_shared.contracts.auth import AuthContext
from moodprint_shared.contracts.context import ContextBundle
from openai import APIConnectionError

USAGE = Usage(requests=1, input_tokens=3, output_tokens=3, total_tokens=6)


def cfg_with(**agent: Any) -> AppConfig:
    base = AppConfig()
    return replace(base, agent=replace(base.agent, **agent))


def context() -> CompanionToolContext:
    return CompanionToolContext(
        auth=AuthContext(uuid4(), "s", "aal1", '{"private":"auth-canary"}'),
        request_id="hardening",
        conversation_id=uuid4(),
        run_id=uuid4(),
        age_band=None,
        services=cast(AgentServices, SimpleNamespace()),
        context=ContextBundle(),
        budget=RunToolBudget(),
    )


async def collect(runtime: CompanionRuntime, ctx: AgentToolContext, text="Xin chào", session=None):
    return [
        event
        async for event in runtime.stream_turn(
            ctx=ctx, user_input=text, session=session or SQLiteSession(str(ctx.conversation_id))
        )
    ]


def names(events) -> list[str]:
    return [e.event for e in events]


async def test_cancel_past_the_grace_period_stops_a_slow_tool_and_is_never_a_success() -> None:
    started = asyncio.Event()
    finished: list[str] = []

    async def slow_tool(ctx: RunContextWrapper[AgentToolContext]) -> str:
        """A tool that would take a long time."""
        started.set()
        try:
            await asyncio.sleep(30)
            finished.append("completed")
        except asyncio.CancelledError:
            finished.append("cancelled")
            raise
        return "done"

    registry = ToolRegistry()
    registry.register(slow_tool, ToolPolicy("slow_tool", "1", "read", False, 60, 1))
    model = ScriptedModel(
        [[function_call("slow_tool", {}, call_id="slow")], [assistant_message("Xong.")]]
    )
    runtime = CompanionRuntime(cfg_with(cancel_grace_s=0.2), registry, model=model)
    ctx = context()
    task = asyncio.create_task(collect(runtime, ctx))
    await started.wait()
    began = perf_counter()
    assert runtime.cancel(ctx.run_id)
    events = await asyncio.wait_for(task, timeout=5)
    assert perf_counter() - began < 3  # bounded by the grace period, not by the 30 s tool
    assert events[-1].event == "run.completed" and events[-1].data.status == "cancelled"
    assert "message.completed" not in names(events)  # a cancelled run is not an answer
    assert finished == ["cancelled"]
    assert runtime.cancel(ctx.run_id) is False  # nothing left behind


async def test_cancel_inside_the_grace_period_lets_the_turn_finish_then_stops() -> None:
    entered, release = asyncio.Event(), asyncio.Event()

    async def delayed(call):
        entered.set()
        await release.wait()
        return [assistant_message("Xong lượt này.")]

    runtime = CompanionRuntime(
        cfg_with(cancel_grace_s=5), model=ScriptedModel([ModelStep.respond(delayed)])
    )
    ctx = context()
    task = asyncio.create_task(collect(runtime, ctx))
    await entered.wait()
    runtime.cancel(ctx.run_id)
    await asyncio.sleep(0.05)
    release.set()  # the turn completes within the grace window
    events = await asyncio.wait_for(task, timeout=5)
    assert events[-1].data.status == "cancelled" and "message.completed" not in names(events)


def proposal(owner: UUID, conversation: UUID, **changes: Any) -> StoredProposal:
    payload = {"description": "x"}
    base: dict[str, Any] = {
        "id": uuid4(),
        "owner_id": owner,
        "conversation_id": conversation,
        "run_id": uuid4(),
        "kind": "case_event",
        "target_case_id": uuid4(),
        "payload": payload,
        "payload_sha256": payload_sha256(payload),
        "preview": {},
        "base_version": 1,
        "request_key": "k",
        "status": "approved",
        "result": None,
        "created_at": datetime.now(UTC),
        "expires_at": datetime.now(UTC) + timedelta(minutes=5),
        "approval_binding": {"decision": "approve"},
    }
    base.update(changes)
    return StoredProposal(**base)


class Store:
    def __init__(self, stored: StoredProposal) -> None:
        self.stored = stored

    async def get(self, auth, proposal_id):
        return self.stored

    async def create(self, *args, **kwargs):  # pragma: no cover - unused here
        raise AssertionError


class Writer:
    def __init__(self) -> None:
        self.applied = 0

    async def apply(self, auth, *, proposal_id, run_id):
        self.applied += 1
        return ApplyOutcome("applied", result={"ok": True})


async def test_no_domain_write_starts_after_the_cancel_was_acknowledged() -> None:
    ctx = context()
    stored = proposal(ctx.auth.user_id, ctx.conversation_id)
    writer = Writer()
    ctx.deps = ToolDeps(proposals=cast(Any, Store(stored)))
    ctx.cancel_check = lambda: False
    ok = await save_approved(ctx, str(stored.id), "case_event", writer)
    assert ok["status"] == "applied" and writer.applied == 1  # control: normally it writes
    ctx.cancel_check = lambda: True  # the user's cancel is now acknowledged
    blocked = await save_approved(ctx, str(stored.id), "case_event", writer)
    assert blocked == {"error": {"code": "run_cancelled", "retryable": False}}
    assert writer.applied == 1  # the earlier, already-committed write stays; no new one began


@pytest.mark.parametrize(
    "error, code, retryable",
    [
        (ModelTimeoutError(30), "model_timeout", True),
        (ModelRefusalError("không thể"), "model_refusal", False),
        (
            APIConnectionError(
                request=httpx.Request("POST", "https://api.openai.com/v1/responses")
            ),
            "upstream_error",
            True,
        ),
        (RuntimeError("private-canary"), "internal_error", True),
    ],
)
async def test_each_failure_class_ends_as_a_failure_with_no_answer_and_no_leak(
    error: Exception, code: str, retryable: bool
) -> None:
    runtime = CompanionRuntime(AppConfig(), model=ScriptedModel([error]))
    events = await collect(runtime, context())
    assert events[-1].event == "run.failed"
    assert (events[-1].data.code, events[-1].data.retryable) == (code, retryable)
    assert "message.completed" not in names(events) and "run.completed" not in names(events)
    assert names(events)[-2] == "run.usage"
    assert "private-canary" not in "".join(e.model_dump_json() for e in events)
    assert [e.seq for e in events] == list(range(1, len(events) + 1))


async def test_a_second_run_with_the_same_id_is_refused_while_the_first_is_active() -> None:
    release, entered = asyncio.Event(), asyncio.Event()

    async def held(call):
        entered.set()
        await release.wait()
        return [assistant_message("ok")]

    runtime = CompanionRuntime(AppConfig(), model=ScriptedModel([ModelStep.respond(held)]))
    ctx = context()
    first = asyncio.create_task(collect(runtime, ctx))
    await entered.wait()
    with pytest.raises(ValueError, match="already active"):
        await collect(runtime, ctx)
    release.set()
    assert (await first)[-1].data.status == "completed"


def registry_with_write(executed: list[str]) -> ToolRegistry:
    async def save_test(ctx: RunContextWrapper[AgentToolContext], note: str) -> str:
        executed.append(note)
        return "saved"

    registry = ToolRegistry()
    registry.register(save_test, ToolPolicy("save_test", "1", "write", True, 15, 1))
    return registry


async def test_a_version_1_checkpoint_still_resumes() -> None:
    executed: list[str] = []
    ctx, session = context(), SQLiteSession("v1-checkpoint")
    first = CompanionRuntime(
        AppConfig(),
        registry_with_write(executed),
        model=ScriptedModel([[function_call("save_test", {"note": "ghi"}, call_id="w1")]]),
    )
    await collect(first, ctx, session=session)
    checkpoint = json.loads(first.pending_approvals(ctx.run_id)[0].serialized_state)
    assert checkpoint["version"] == 2
    legacy = {
        k: v
        for k, v in checkpoint.items()
        if k not in ("scratch", "urgency_level", "urgency_signals")
    }
    legacy["version"] = 1
    model = ScriptedModel([[assistant_message("Đã lưu.")]])
    second = CompanionRuntime(AppConfig(), registry_with_write(executed), model=model)
    resumed = [
        e
        async for e in second.resume_after_approval(
            ctx=ctx, serialized_state=json.dumps(legacy), approved=True, session=session
        )
    ]
    assert executed == ["ghi"] and resumed[-1].data.status == "completed"
    # A checkpoint from another tool inventory or prompt version is refused, not guessed at.
    bad = {**checkpoint, "tools_version": "something-else"}
    with pytest.raises(Exception, match="incompatible"):
        _ = [
            e
            async for e in CompanionRuntime(
                AppConfig(), registry_with_write([]), model=ScriptedModel([])
            ).resume_after_approval(
                ctx=context(), serialized_state=json.dumps(bad), approved=True, session=session
            )
        ]


async def test_twenty_concurrent_runs_stay_isolated_and_leave_nothing_active() -> None:
    def scripted(n: int) -> ScriptedModel:
        return ScriptedModel(
            [ModelStep(output=[assistant_message(f"trả lời số {n}")], usage=USAGE)]
        )

    contexts = [context() for _ in range(20)]
    runtimes = [CompanionRuntime(AppConfig(), model=scripted(n)) for n in range(20)]
    shared = CompanionRuntime(AppConfig(), model=ScriptedModel([]))  # one runtime, many runs below
    batches = await asyncio.gather(
        *(collect(runtimes[n], contexts[n], f"câu hỏi {n}") for n in range(20))
    )
    for n, events in enumerate(batches):
        done = next(e for e in events if e.event == "message.completed").data
        assert done.content == f"trả lời số {n}"
        assert {e.run_id for e in events} == {contexts[n].run_id}
        assert events[-1].data.status == "completed"
    assert all(not runtime._active for runtime in runtimes) and not shared._active  # type: ignore[attr-defined]


async def test_one_runtime_serves_many_runs_without_mixing_them() -> None:
    steps = [
        ModelStep(output=[assistant_message(f"một câu trả lời {n}")], usage=USAGE) for n in range(8)
    ]
    model = ScriptedModel(steps)
    runtime = CompanionRuntime(AppConfig(), model=model)
    contexts = [context() for _ in range(8)]
    batches = await asyncio.gather(*(collect(runtime, c, "xin chào") for c in contexts))
    answers = [next(e for e in ev if e.event == "message.completed").data.content for ev in batches]
    assert sorted(answers) == sorted(f"một câu trả lời {n}" for n in range(8))  # each consumed once
    for ctx, events in zip(contexts, batches, strict=True):
        assert {e.run_id for e in events} == {ctx.run_id}
    assert not runtime._active  # type: ignore[attr-defined]
