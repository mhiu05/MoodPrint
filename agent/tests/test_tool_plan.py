"""Action-plan tools (U-AG-60…70 plan part): validation, progress preservation, approval gate."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any, cast
from uuid import UUID, uuid4

import pytest
from agents import RunContextWrapper
from moodprint_agent.budget import RunToolBudget
from moodprint_agent.tools.context import CompanionToolContext, ToolDeps
from moodprint_agent.tools.factory import build_registry
from moodprint_agent.tools.plan import PlanItemIn, get_action_plan, propose_action_plan, save_plan
from moodprint_agent.tools.proposals import ApplyOutcome, StoredProposal, payload_sha256
from moodprint_shared.config import AppConfig
from moodprint_shared.contracts.agent import AgentServices
from moodprint_shared.contracts.auth import AuthContext
from moodprint_shared.contracts.context import ContextBundle
from moodprint_shared.contracts.errors import NotFound
from moodprint_shared.contracts.plans import ActionPlan, PlanItem

OWNER, CASE = uuid4(), uuid4()
T0 = datetime(2026, 11, 8, tzinfo=UTC)


class Store:
    def __init__(self) -> None:
        self.rows: dict[UUID, StoredProposal] = {}

    async def create(
        self,
        auth,
        *,
        conversation_id,
        run_id,
        kind,
        target_case_id,
        payload,
        preview,
        base_version,
        request_key,
    ):
        for row in self.rows.values():
            if (row.owner_id, row.run_id, row.request_key) == (auth.user_id, run_id, request_key):
                return row
        row = StoredProposal(
            id=uuid4(),
            owner_id=auth.user_id,
            conversation_id=conversation_id,
            run_id=run_id,
            kind=kind,
            target_case_id=target_case_id,
            payload=payload,
            payload_sha256=payload_sha256(payload),
            preview=preview,
            base_version=base_version,
            request_key=request_key,
            status="proposed",
            result=None,
            created_at=datetime.now(UTC),
            expires_at=datetime.now(UTC) + timedelta(minutes=30),
        )
        self.rows[row.id] = row
        return row

    async def get(self, auth, proposal_id):
        row = self.rows.get(proposal_id)
        return row if row and row.owner_id == auth.user_id else None


class Writer:
    def __init__(self) -> None:
        self.calls, self.outcome = 0, ApplyOutcome("applied", result={"planId": "p1"})

    async def apply(self, auth, *, proposal_id, run_id):
        self.calls += 1
        return self.outcome


def existing_plan(version: int = 4, **overrides: Any) -> ActionPlan:
    done = PlanItem(
        id=uuid4(),
        label="Nói với cô chủ nhiệm",
        status="done",
        notes="đã nói thứ Hai",
        priority="high",
        reason="an toàn",
    )
    doing = PlanItem(id=uuid4(), label="Ghi lại sự việc", status="doing", priority="normal")
    return ActionPlan(
        id=uuid4(),
        case_id=CASE,
        owner_id=OWNER,
        version=version,
        goal="Được hỗ trợ",
        status=overrides.pop("status", "active"),
        items=[done, doing],
        created_at=T0,
        updated_at=T0,
    )


def make(plan: ActionPlan | None = None, *, owner: UUID = OWNER):
    class Incidents:
        async def get_case(self, auth, cid):
            if cid != CASE or auth.user_id != OWNER:
                raise NotFound()
            return SimpleNamespace(id=CASE, version=2)

    class Plans:
        async def get_for_case(self, auth, cid):
            return plan if auth.user_id == OWNER else None

    store, writer = Store(), Writer()
    ctx = CompanionToolContext(
        auth=AuthContext(owner, "s", "aal1", "{}"),
        request_id="r",
        conversation_id=uuid4(),
        run_id=uuid4(),
        age_band=None,
        services=cast(AgentServices, SimpleNamespace(incidents=Incidents(), plans=Plans())),
        context=ContextBundle(),
        budget=RunToolBudget(),
        deps=ToolDeps(proposals=store, plans=writer),
        tool_call_id="call-1",
    )
    return ctx, store, writer


def items(*pairs: tuple[str, str]) -> list[PlanItemIn]:
    return [
        PlanItemIn(label=label, priority=cast(Any, priority), reason="vì sao")
        for label, priority in pairs
    ]


async def propose(ctx, **kwargs):
    args = dict(
        case_id=str(CASE),
        goal="Được hỗ trợ ở trường",
        rationale="Bạn muốn có người giúp.",
        base_version=None,
    )
    args.update(kwargs)
    return await propose_action_plan(RunContextWrapper(ctx), **args)


async def test_new_plan_orders_high_first_stably_and_saves_nothing() -> None:
    ctx, store, writer = make()
    out = await propose(
        ctx,
        items=items(
            ("Viết lại sự việc", "normal"),
            ("Nói với cô", "high"),
            ("Hỏi bạn thân", "normal"),
            ("Gặp tư vấn", "high"),
        ),
    )
    stored = store.rows[UUID(out["proposalId"])]
    labels = [i["label"] for i in stored.payload["plan"]["items"]]
    assert labels == ["Nói với cô", "Gặp tư vấn", "Viết lại sự việc", "Hỏi bạn thân"]
    assert stored.payload["plan"]["status"] == "draft" and stored.base_version is None
    assert stored.payload["plan"]["chosen_option_id"] == "" and writer.calls == 0
    assert "CHƯA LƯU" in out["note"]


async def test_revision_keeps_id_status_and_notes_of_matching_items() -> None:
    plan = existing_plan()
    ctx, store, _ = make(plan)
    out = await propose(
        ctx,
        base_version=4,
        items=items(
            ("nói với  cô chủ nhiệm", "high"), ("Ghi lại sự việc", "normal"), ("Bước mới", "normal")
        ),
    )
    saved = {i["label"]: i for i in store.rows[UUID(out["proposalId"])].payload["plan"]["items"]}
    assert (
        saved["nói với cô chủ nhiệm"]["status"] == "done"
        and saved["nói với cô chủ nhiệm"]["notes"] == "đã nói thứ Hai"
    )
    assert saved["nói với cô chủ nhiệm"]["id"] == str(plan.items[0].id)
    assert saved["Ghi lại sự việc"]["status"] == "doing"
    assert saved["Bước mới"]["status"] == "not_started"


async def test_completed_status_is_never_proposed() -> None:
    ctx, store, _ = make(existing_plan(status="completed"))
    out = await propose(ctx, base_version=4, items=items(("Bước", "normal")))
    assert store.rows[UUID(out["proposalId"])].payload["plan"]["status"] == "active"


async def test_stale_or_missing_base_version_is_a_structured_conflict() -> None:
    ctx, store, _ = make(existing_plan(version=4))
    for base in (None, 3, 5):
        out = await propose(ctx, base_version=base, items=items(("Bước", "normal")))
        assert out["error"]["code"] == "version_conflict" and out["latestVersion"] == 4
    assert store.rows == {}


@pytest.mark.parametrize(
    ("override", "code"),
    [
        ({"items": []}, "too_many_items"),
        ({"items": items(*[(f"Bước {i}", "normal") for i in range(9)])}, "too_many_items"),
        ({"items": items(*[(f"Bước {i}", "high") for i in range(4)])}, "too_many_high"),
        ({"items": items(("x" * 141, "normal"))}, "invalid_item"),
        ({"items": items(("", "normal"))}, "invalid_item"),
        ({"items": items(("Bước", "normal"), ("  bước ", "normal"))}, "duplicate_item"),
        ({"goal": ""}, "invalid_field"),
        ({"items": items(("Đối đầu với bạn đó ngay", "high"))}, "unsafe_step"),
        ({"items": items(("Tự điều tra tài khoản ẩn danh", "normal"))}, "unsafe_step"),
        ({"items": items(("MoodPrint sẽ liên hệ nhà trường", "normal"))}, "unsafe_step"),
    ],
)
async def test_limits_are_reported_not_silently_trimmed(override, code) -> None:
    ctx, store, _ = make()
    out = await propose(ctx, **{"items": items(("Bước", "normal")), **override})
    assert out["error"]["code"] == code and store.rows == {}


async def test_other_users_case_is_not_found_and_nothing_is_stored() -> None:
    ctx, store, _ = make(owner=uuid4())
    out = await propose(ctx, items=items(("Bước", "normal")))
    assert out["error"]["code"] == "not_found" and store.rows == {}


async def test_get_action_plan_reports_progress_and_missing_plan() -> None:
    ctx, _, _ = make(existing_plan())
    out = await get_action_plan(RunContextWrapper(ctx), str(CASE))
    assert out["exists"] and out["progress"] == {"done": 1, "total": 2} and out["version"] == 4
    ctx2, _, _ = make(None)
    assert await get_action_plan(RunContextWrapper(ctx2), str(CASE)) == {"exists": False}
    ctx3, _, _ = make(existing_plan(), owner=uuid4())
    assert (await get_action_plan(RunContextWrapper(ctx3), str(CASE)))["error"][
        "code"
    ] == "not_found"


async def test_save_needs_an_approved_proposal_and_reports_version_conflicts() -> None:
    ctx, store, writer = make(existing_plan())
    pid = UUID((await propose(ctx, base_version=4, items=items(("Bước", "normal"))))["proposalId"])
    assert (await save_plan(RunContextWrapper(ctx), proposal_id=str(pid)))["error"][
        "code"
    ] == "not_approved"
    assert writer.calls == 0
    from dataclasses import replace

    store.rows[pid] = replace(store.rows[pid], status="approved")
    writer.outcome = ApplyOutcome("conflict", latest_version=7, error="version_conflict")
    out = await save_plan(RunContextWrapper(ctx), proposal_id=str(pid))
    assert out["error"]["code"] == "version_conflict" and out["latestVersion"] == 7
    writer.outcome = ApplyOutcome("applied", result={"planId": "p1"})
    assert (await save_plan(RunContextWrapper(ctx), proposal_id=str(pid))) == {
        "status": "applied",
        "result": {"planId": "p1"},
    }


def test_inventory_for_plan_tools() -> None:
    registry = build_registry(AppConfig())
    assert registry.tool_signatures()["save_plan"] == ("proposal_id",)
    assert registry.requires_approval("save_plan")
    assert not registry.requires_approval("propose_action_plan")
    assert "set_item_status" not in registry.names() and "update_plan_item" not in registry.names()
