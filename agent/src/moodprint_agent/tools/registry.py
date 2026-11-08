"""Typed policy enforcement at the SDK function-tool boundary."""

import hashlib
import inspect
import json
from collections.abc import Awaitable, Callable, Iterable
from dataclasses import asdict, dataclass
from typing import Any, cast

from agents import FunctionTool, RunContextWrapper, function_tool
from agents.tool_context import ToolContext
from moodprint_shared.contracts.agent import AgentToolContext, ToolPolicy
from pydantic import BaseModel

from moodprint_agent.budget import RunToolBudget
from moodprint_agent.errors import PerToolBudgetExceeded

ToolFunction = Callable[..., Awaitable[Any]]
Preview = Callable[[dict[str, Any]], dict[str, Any]]
# Approval previews for stored proposals must come from the server-side record, not from the
# model's tool-call arguments, so they are resolved asynchronously against the turn context.
AsyncPreview = Callable[[AgentToolContext, dict[str, Any]], Awaitable[dict[str, Any]]]


@dataclass(frozen=True, slots=True)
class ToolSpec:
    """One tool of a group: function, policy and the metadata the UI needs."""

    fn: ToolFunction
    policy: ToolPolicy
    label: str
    preview: Preview | None = None
    async_preview: AsyncPreview | None = None
    budget_exempt: bool = False


@dataclass(frozen=True, slots=True)
class RegisteredTool:
    policy: ToolPolicy
    sdk_tool: FunctionTool
    label: str
    preview: Preview | None
    async_preview: AsyncPreview | None = None
    budget_exempt: bool = False


def _timeout_result(ctx: RunContextWrapper[Any], error: Exception) -> str:
    return '{"error":{"code":"tool_timeout","retryable":true}}'


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, RegisteredTool] = {}

    def register(
        self,
        fn: ToolFunction,
        policy: ToolPolicy,
        *,
        label: str | None = None,
        preview: Preview | None = None,
        async_preview: AsyncPreview | None = None,
        budget_exempt: bool = False,
    ) -> None:
        if policy.access == "write" and not policy.needs_approval:
            raise ValueError("write tools require approval")
        if policy.name in self._tools:
            raise ValueError("duplicate tool name")
        if policy.timeout_s <= 0 or policy.max_calls_per_run < 1:
            raise ValueError("tool limits must be positive")
        if {"user_id", "owner_id"}.intersection(inspect.signature(fn).parameters):
            raise ValueError("tool signature cannot accept caller identity")

        sdk_tool = function_tool(
            fn,
            name_override=policy.name,
            needs_approval=policy.needs_approval,
            failure_error_function=None,
            timeout=policy.timeout_s,
            timeout_behavior="error_as_result",
            timeout_error_function=_timeout_result,
        )
        invoke = sdk_tool.on_invoke_tool

        async def guarded(ctx: ToolContext[AgentToolContext], arguments: str) -> Any:
            try:
                budget = ctx.context.budget
                if budget_exempt and isinstance(budget, RunToolBudget):
                    budget.consume_exempt(policy.name, policy.max_calls_per_run)
                else:
                    budget.consume(policy.name, policy.max_calls_per_run)
            except PerToolBudgetExceeded:
                return '{"error":{"code":"tool_call_limit","retryable":false}}'
            # Tools run one at a time (parallel_tool_calls=False), so this is race free.
            if hasattr(ctx.context, "tool_call_id"):
                ctx.context.tool_call_id = ctx.tool_call_id  # type: ignore[attr-defined]
            output = await invoke(ctx, arguments)
            return output.model_dump_json() if isinstance(output, BaseModel) else output

        sdk_tool.on_invoke_tool = guarded
        self._tools[policy.name] = RegisteredTool(
            policy=policy,
            sdk_tool=sdk_tool,
            label=label or policy.name.replace("_", " "),
            preview=preview,
            async_preview=async_preview,
            budget_exempt=budget_exempt,
        )

    def register_group(self, specs: Iterable[ToolSpec]) -> None:
        for spec in specs:
            self.register(
                spec.fn,
                spec.policy,
                label=spec.label,
                preview=spec.preview,
                async_preview=spec.async_preview,
                budget_exempt=spec.budget_exempt,
            )

    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self._tools))

    def policy(self, name: str) -> ToolPolicy:
        return self._tools[name].policy

    def requires_approval(self, name: str) -> bool:
        tool = self._tools.get(name)
        return tool is not None and tool.policy.needs_approval

    def tool_signatures(self) -> dict[str, tuple[str, ...]]:
        """Model-visible parameter names per tool (used by inventory/privacy invariants)."""
        out: dict[str, tuple[str, ...]] = {}
        for name, tool in self._tools.items():
            schema = tool.sdk_tool.params_json_schema
            out[name] = tuple(sorted(cast(dict[str, Any], schema.get("properties", {}))))
        return out

    def sdk_tools(self) -> list[FunctionTool]:
        return [self._tools[name].sdk_tool for name in sorted(self._tools)]

    def version(self) -> str:
        policies = [asdict(self._tools[name].policy) for name in sorted(self._tools)]
        encoded = json.dumps(policies, sort_keys=True, separators=(",", ":")).encode()
        return hashlib.sha256(encoded).hexdigest()[:16]

    def label(self, name: str) -> str:
        return self._tools[name].label if name in self._tools else "Công cụ"

    async def approval_preview_for(
        self, name: str, arguments: str, ctx: AgentToolContext
    ) -> dict[str, Any]:
        """Preview shown to the user; stored-proposal tools resolve it from the server record."""
        tool = self._tools.get(name)
        if tool is not None and tool.async_preview is not None:
            parsed: Any = json.loads(arguments)
            args = cast(dict[str, Any], parsed) if isinstance(parsed, dict) else {}
            return await tool.async_preview(ctx, args)
        return self.approval_preview(name, arguments)

    def approval_preview(self, name: str, arguments: str) -> dict[str, Any]:
        tool = self._tools.get(name)
        if tool is None or tool.preview is None:
            return {}
        parsed: Any = json.loads(arguments)
        if not isinstance(parsed, dict):
            return {}
        return tool.preview(cast(dict[str, Any], parsed))


def diagnostic_registry() -> ToolRegistry:
    from moodprint_agent.tools.diagnostics import get_server_time

    registry = ToolRegistry()
    registry.register(
        get_server_time,
        ToolPolicy("get_server_time", "1", "read", False, 15, 2),
        label="Xem giờ máy chủ",
    )
    return registry
