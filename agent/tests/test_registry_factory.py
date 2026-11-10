"""Registry invariants that every Phase 3 tool group inherits."""

import json
from dataclasses import replace
from types import SimpleNamespace
from typing import Any
from uuid import uuid4

import pytest
from agents import RunContextWrapper
from agents.testing import function_call
from agents.tool_context import ToolContext
from moodprint_agent.budget import RunToolBudget
from moodprint_agent.tools.context import CompanionToolContext, RunScratch, ToolDeps
from moodprint_agent.tools.factory import build_registry
from moodprint_agent.tools.proposals import (
    can_transition,
    event_id_for,
    payload_sha256,
)
from moodprint_agent.tools.registry import ToolRegistry, ToolSpec
from moodprint_shared.config import AppConfig
from moodprint_shared.contracts.agent import ToolPolicy


def _policy(name: str = "probe", **changes: Any) -> ToolPolicy:
    return replace(ToolPolicy(name, "1", "read", False, 5, 2), **changes)


async def probe(ctx: RunContextWrapper[Any], note: str = "") -> dict[str, str]:
    """Probe tool."""
    return {"seen": note}


def test_factory_is_pure_and_needs_no_runtime_state() -> None:
    first, second = build_registry(AppConfig()), build_registry(AppConfig())
    assert first.version() == second.version()
    assert first.names() == second.names()


def test_register_group_registers_all_or_reports_duplicates() -> None:
    registry = ToolRegistry()
    registry.register_group([ToolSpec(probe, _policy(), "Thử")])
    assert registry.names() == ("probe",)
    with pytest.raises(ValueError, match="duplicate"):
        registry.register_group([ToolSpec(probe, _policy(), "Thử")])


def test_write_tools_must_require_approval_and_policy_changes_version() -> None:
    with pytest.raises(ValueError, match="approval"):
        ToolRegistry().register(probe, _policy(access="write"))
    ok, other = ToolRegistry(), ToolRegistry()
    ok.register(probe, _policy(access="write", needs_approval=True))
    other.register(probe, _policy(access="write", needs_approval=True, version="2"))
    assert ok.requires_approval("probe") and ok.version() != other.version()


def test_model_visible_signature_never_exposes_identity() -> None:
    registry = ToolRegistry()
    registry.register(probe, _policy())
    for params in registry.tool_signatures().values():
        assert not {"user_id", "owner_id", "engine", "token", "jwt"} & set(params)


async def test_budget_exempt_tool_does_not_consume_the_run_total() -> None:
    registry = ToolRegistry()
    registry.register(probe, _policy(max_calls_per_run=1), budget_exempt=True)
    registry.register(_other(), _policy("other"))
    budget = RunToolBudget(max_calls=1)
    wrapper = ToolContext.from_agent_context(
        RunContextWrapper(SimpleNamespace(budget=budget)),
        tool_call_id="c",
        tool_call=function_call("probe", {}, call_id="c"),
    )
    tools = {t.name: t for t in registry.sdk_tools()}
    await tools["probe"].on_invoke_tool(wrapper, "{}")
    assert budget.total_calls == 0
    denied = await tools["probe"].on_invoke_tool(wrapper, "{}")
    assert json.loads(str(denied))["error"]["code"] == "tool_call_limit"
    await tools["other"].on_invoke_tool(wrapper, "{}")
    assert budget.total_calls == 1
    restored = RunToolBudget.from_snapshot(budget.snapshot())
    assert restored.total_calls == 1


def _other():
    async def other(ctx: RunContextWrapper[Any]) -> dict[str, bool]:
        """Other tool."""
        return {"ok": True}

    return other


async def test_async_preview_comes_from_the_server_not_the_tool_arguments() -> None:
    async def stored_preview(ctx: Any, args: dict[str, Any]) -> dict[str, Any]:
        return {"summary": "từ bản lưu của máy chủ"}

    registry = ToolRegistry()
    registry.register(
        probe,
        _policy(access="write", needs_approval=True),
        async_preview=stored_preview,
        preview=lambda args: {"summary": "do model viết"},
    )
    preview = await registry.approval_preview_for("probe", '{"note":"x"}', SimpleNamespace())  # type: ignore[arg-type]
    assert preview == {"summary": "từ bản lưu của máy chủ"}


async def test_tool_context_records_the_sdk_tool_call_id() -> None:
    seen: list[str | None] = []

    async def capture(ctx: RunContextWrapper[CompanionToolContext]) -> dict[str, bool]:
        """Capture."""
        seen.append(ctx.context.tool_call_id)
        return {"ok": True}

    registry = ToolRegistry()
    registry.register(capture, _policy("capture"))
    ctx = SimpleNamespace(budget=RunToolBudget(), tool_call_id=None)
    wrapper = ToolContext.from_agent_context(
        RunContextWrapper(ctx),
        tool_call_id="call-7",
        tool_call=function_call("capture", {}, call_id="call-7"),
    )
    await registry.sdk_tools()[0].on_invoke_tool(wrapper, "{}")
    assert seen == ["call-7"]


def test_scratch_snapshot_roundtrip_keeps_citation_ledger() -> None:
    from moodprint_shared.contracts.knowledge import SourceCitation

    citation = SourceCitation(
        source_id="s-1",
        document_id="d-1",
        title="Tài liệu",
        publisher="NXB",
        url=None,
        section=None,
        published_at=None,
        last_reviewed=None,
        applicability="VN",
        country_scope=["VN"],
    )
    scratch = RunScratch()
    assert scratch.register_citation(citation) == "S1"
    assert scratch.register_citation(citation) == "S1"
    scratch.proposals["p"] = "case_event"
    restored = RunScratch.from_snapshot(json.loads(json.dumps(scratch.snapshot())))
    assert restored.citations == scratch.citations and restored.proposals == scratch.proposals


def test_toolcontext_deps_default_to_nothing_and_hold_no_secrets() -> None:
    deps = ToolDeps()
    assert all(getattr(deps, name) is None for name in deps.__slots__)
    assert not {"engine", "jwt", "token", "secret"} & set(deps.__slots__)
    assert uuid4() != uuid4()


def test_proposal_state_machine_and_deterministic_ids() -> None:
    assert can_transition("proposed", "approved") and can_transition("approved", "applied")
    for terminal in ("rejected", "applied", "expired", "failed"):
        assert not can_transition(terminal, "approved")  # type: ignore[arg-type]
    assert not can_transition("proposed", "applied")  # no write without approval
    owner, proposal = uuid4(), uuid4()
    assert event_id_for(owner, proposal) == event_id_for(owner, proposal)
    assert event_id_for(owner, proposal) != event_id_for(uuid4(), proposal)
    assert payload_sha256({"b": 1, "a": "é"}) == payload_sha256({"a": "é", "b": 1})
