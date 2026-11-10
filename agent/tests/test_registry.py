import json
from dataclasses import replace
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest
from agents import Agent, RunConfig, RunContextWrapper, Runner
from agents.testing import ScriptedModel, assistant_message, function_call
from agents.tool_context import ToolContext
from moodprint_agent.budget import RunToolBudget
from moodprint_agent.tools.diagnostics import get_server_time
from moodprint_agent.tools.registry import ToolRegistry
from moodprint_shared.config import OPENAI_MODEL
from moodprint_shared.contracts.agent import ToolPolicy


def policy(**changes):
    return replace(ToolPolicy("get_server_time", "1", "read", False, 15, 2), **changes)


def test_registry_rejects_write_without_approval() -> None:
    with pytest.raises(ValueError, match="approval"):
        ToolRegistry().register(get_server_time, policy(access="write"))


def test_tool_signature_has_no_user_id() -> None:
    async def unsafe(user_id: str) -> str:
        return user_id

    with pytest.raises(ValueError, match="identity"):
        ToolRegistry().register(unsafe, policy())


def test_tools_version_changes_with_policy() -> None:
    left, right = ToolRegistry(), ToolRegistry()
    left.register(get_server_time, policy())
    right.register(get_server_time, policy(max_calls_per_run=1))
    assert left.version() != right.version()


async def test_get_server_time_runs_without_api_key() -> None:
    registry = ToolRegistry()
    registry.register(get_server_time, policy())
    model = ScriptedModel(
        [
            [function_call("get_server_time", {}, call_id="clock-1")],
            [assistant_message("Đã xem giờ máy chủ.")],
        ]
    )
    ctx = SimpleNamespace(budget=RunToolBudget())
    result = await Runner.run(
        Agent(name="test", model=OPENAI_MODEL, tools=registry.sdk_tools()),
        "Giờ máy chủ?",
        context=ctx,
        run_config=RunConfig(
            model=model, tracing_disabled=True, trace_include_sensitive_data=False
        ),
    )
    assert result.final_output == "Đã xem giờ máy chủ."
    assert ctx.budget.total_calls == 1
    tool_output = next(x.output for x in result.new_items if x.type == "tool_call_output_item")
    timestamp = datetime.fromisoformat(json.loads(str(tool_output))["server_time"])
    assert timestamp.utcoffset() == timedelta(0)
    model.assert_complete()


async def test_per_tool_limit_is_structured_result() -> None:
    registry = ToolRegistry()
    registry.register(get_server_time, policy(max_calls_per_run=1))
    tool = registry.sdk_tools()[0]
    wrapper = ToolContext.from_agent_context(
        RunContextWrapper(SimpleNamespace(budget=RunToolBudget())),
        tool_call_id="clock",
        tool_call=function_call("get_server_time", {}, call_id="clock"),
    )
    await tool.on_invoke_tool(wrapper, "{}")
    denied = await tool.on_invoke_tool(wrapper, "{}")
    assert json.loads(str(denied))["error"]["code"] == "tool_call_limit"


async def test_tool_timeout_returns_safe_result() -> None:
    import asyncio

    async def slow() -> str:
        await asyncio.Event().wait()
        return "never"

    registry = ToolRegistry()
    registry.register(slow, policy(name="slow", timeout_s=0.01))
    model = ScriptedModel(
        [
            [function_call("slow", {}, call_id="slow-1")],
            [assistant_message("Thử lại sau.")],
        ]
    )
    result = await Runner.run(
        Agent(name="test", tools=registry.sdk_tools()),
        "test",
        context=SimpleNamespace(budget=RunToolBudget()),
        run_config=RunConfig(
            model=model, tracing_disabled=True, trace_include_sensitive_data=False
        ),
    )
    assert result.final_output == "Thử lại sau."
    output = next(x.output for x in result.new_items if x.type == "tool_call_output_item")
    assert "tool_timeout" in str(output)
