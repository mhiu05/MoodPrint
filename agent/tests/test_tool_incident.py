"""Incident tools and the propose → approve → save protocol (U-AG-60…70), no database needed.

The fakes below mirror the *contract* of the backend ProposalStore/ConfirmedEventWriter so the
tool-side rules (owner/run binding, hash, expiry, idempotence) are tested in isolation. The real
adapter is exercised against PostgreSQL in the backend integration tests.
"""

import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any, cast
from uuid import UUID, uuid4

import pytest
from agents import RunContextWrapper, SQLiteSession
from agents.testing import ModelStep, ScriptedModel, assistant_message, function_call
from agents.usage import Usage
from safevoice_agent.budget import RunToolBudget
from safevoice_agent.runtime import CompanionRuntime
from safevoice_agent.tools.context import CompanionToolContext, ToolDeps
from safevoice_agent.tools.factory import build_registry
from safevoice_agent.tools.incident import (
    get_case_context,
    propose_case_event,
    save_confirmed_event,
)
from safevoice_agent.tools.proposals import ApplyOutcome, StoredProposal, payload_sha256
from safevoice_shared.config import AppConfig
from safevoice_shared.contracts.agent import AgentServices
from safevoice_shared.contracts.auth import AuthContext
from safevoice_shared.contracts.context import ContextBundle
from safevoice_shared.contracts.errors import NotFound

NOW = datetime(2026, 11, 8, 12, 0, tzinfo=UTC)


class FakeProposalStore:
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
        return row if row is not None and row.owner_id == auth.user_id else None

    def set(self, proposal_id: UUID, **changes: Any) -> None:
        self.rows[proposal_id] = replace(self.rows[proposal_id], **changes)


class FakeWriter:
    def __init__(self, store: FakeProposalStore) -> None:
        self.store, self.applied, self.calls = store, [], 0

    async def apply(self, auth, *, proposal_id, run_id):
        self.calls += 1
        row = await self.store.get(auth, proposal_id)
        if row is None or row.status != "approved":
            return ApplyOutcome("failed", error="not_approved")
        self.applied.append(row.payload["event"]["description"])
        self.store.set(proposal_id, status="applied", result={"eventId": "e-1"})
        return ApplyOutcome("applied", result={"eventId": "e-1"})


def make_world():
    owner = uuid4()
    case_id = uuid4()
    evidence_id = uuid4()
    case = SimpleNamespace(
        id=case_id,
        title="Hồ sơ A",
        status="active",
        perspective="self",
        version=3,
        summary="Mình bị chặn khỏi nhóm.",
        people="",
        place="Lớp 9A",
        occurred_at="",
        category_tags=[],
        events=[],
        plan_progress=None,
    )

    class Incidents:
        async def get_case(self, auth, cid):
            if cid != case_id or auth.user_id != owner:
                raise NotFound()
            return case

        async def list_cases(self, auth, query):
            return SimpleNamespace(items=[case] if auth.user_id == owner else [])

    class Evidence:
        async def get(self, auth, eid):
            if eid != evidence_id or auth.user_id != owner:
                raise NotFound()
            return SimpleNamespace(id=eid, upload_status="uploaded", original_filename="anh1.png")

        async def list_for_case(self, auth, cid):
            return [
                SimpleNamespace(
                    id=evidence_id,
                    kind="image",
                    original_filename="anh1.png",
                    review_status="unreviewed",
                    user_edited_text=None,
                    original_text="NỘI DUNG GỐC KHÔNG ĐƯỢC LỘ",
                )
            ]

    store = FakeProposalStore()
    writer = FakeWriter(store)
    services = SimpleNamespace(incidents=Incidents(), evidence=Evidence(), knowledge=None)
    return owner, case_id, evidence_id, store, writer, services


def make_ctx(owner, services, store, writer, **overrides) -> CompanionToolContext:
    return CompanionToolContext(
        auth=AuthContext(owner, "s", "aal1", '{"private":"jwt-canary"}'),
        request_id="r",
        conversation_id=overrides.pop("conversation_id", uuid4()),
        run_id=overrides.pop("run_id", uuid4()),
        age_band=None,
        services=cast(AgentServices, services),
        context=ContextBundle(),
        budget=RunToolBudget(),
        deps=ToolDeps(proposals=store, events=writer),
        tool_call_id=overrides.pop("tool_call_id", "call-1"),
        **overrides,
    )


async def propose(ctx, case_id, **kwargs) -> dict[str, Any]:
    args = dict(
        case_id=str(case_id),
        description="Bạn A nhắn tin chế giễu trong nhóm lớp.",
        basis="user_stated",
        rationale="Bạn vừa kể điều này.",
        when="2026-11-03",
        time_precision="day",
        place="Nhóm chat lớp",
    )
    args.update(kwargs)
    return await propose_case_event(RunContextWrapper(ctx), **args)


# --- propose ------------------------------------------------------------------------------------
async def test_propose_stores_an_unsaved_proposal_and_writes_nothing() -> None:
    owner, case_id, evidence_id, store, writer, services = make_world()
    ctx = make_ctx(owner, services, store, writer)
    out = await propose(ctx, case_id, evidence_ids=[str(evidence_id)])
    assert out["status"] == "proposed" and "CHƯA LƯU" in out["note"]
    stored = store.rows[UUID(out["proposalId"])]
    assert stored.base_version == 3 and stored.preview["evidence"] == ["anh1.png"]
    assert stored.payload["event"]["basis"] == "user_stated"
    assert writer.calls == 0
    assert ctx.scratch.proposals == {out["proposalId"]: "case_event"}


async def test_inferred_basis_is_refused_with_guidance_to_ask_the_user() -> None:
    owner, case_id, _, store, writer, services = make_world()
    out = await propose(make_ctx(owner, services, store, writer), case_id, basis="inferred")
    assert out["error"]["code"] == "basis_not_allowed" and "xác nhận" in out["error"]["message"]
    assert store.rows == {}


async def test_unknown_precision_never_carries_an_invented_date() -> None:
    owner, case_id, _, store, writer, services = make_world()
    out = await propose(
        make_ctx(owner, services, store, writer),
        case_id,
        when="2026-11-03",
        time_precision="unknown",
    )
    stored = store.rows[UUID(out["proposalId"])]
    assert stored.payload["event"]["when"] == "" and stored.preview["when"] == "chưa rõ ngày"


@pytest.mark.parametrize(
    ("override", "code"),
    [
        ({"description": ""}, "invalid_description"),
        ({"description": "x" * 501}, "invalid_description"),
        ({"rationale": "x" * 201}, "invalid_field"),
        ({"when": "not-a-date", "time_precision": "day"}, "invalid_time"),
        ({"when": "2026-11-03", "time_precision": "exact"}, "invalid_time"),
    ],
)
async def test_invalid_content_is_refused_before_anything_is_stored(override, code) -> None:
    owner, case_id, _, store, writer, services = make_world()
    out = await propose(make_ctx(owner, services, store, writer), case_id, **override)
    assert out["error"]["code"] == code and store.rows == {}


async def test_exact_time_error_explains_the_missing_timezone_without_guessing_one() -> None:
    owner, case_id, _, store, writer, services = make_world()
    out = await propose(
        make_ctx(owner, services, store, writer),
        case_id,
        when="2026-11-09T10:00:00",
        time_precision="exact",
    )
    assert out["error"]["code"] == "invalid_time"
    assert "timezone-aware ISO" in out["error"]["message"]
    assert "YYYY-MM-DD" in out["error"]["message"]
    assert store.rows == {} and writer.calls == 0


async def test_exact_time_preserves_the_explicit_offset_in_the_approval_payload() -> None:
    owner, case_id, _, store, writer, services = make_world()
    when = "2026-11-09T10:00:00+07:00"
    out = await propose(
        make_ctx(owner, services, store, writer), case_id, when=when, time_precision="exact"
    )
    stored = store.rows[UUID(out["proposalId"])]
    assert stored.payload["event"]["when"] == when
    assert stored.preview["when"] == when
    assert writer.calls == 0


async def test_other_users_case_or_evidence_is_not_found() -> None:
    owner, case_id, evidence_id, store, writer, services = make_world()
    intruder = make_ctx(uuid4(), services, store, writer)
    assert (await propose(intruder, case_id))["error"]["code"] == "not_found"
    mine = make_ctx(owner, services, store, writer)
    assert (await propose(mine, uuid4()))["error"]["code"] == "not_found"
    assert (await propose(mine, case_id, evidence_ids=[str(uuid4())]))["error"][
        "code"
    ] == "not_found"
    assert (await propose(mine, "not-a-uuid"))["error"]["code"] == "not_found"
    assert store.rows == {}


async def test_retrying_the_same_tool_call_returns_the_same_proposal() -> None:
    owner, case_id, _, store, writer, services = make_world()
    ctx = make_ctx(owner, services, store, writer)
    first, second = await propose(ctx, case_id), await propose(ctx, case_id)
    assert first["proposalId"] == second["proposalId"] and len(store.rows) == 1


async def test_same_call_id_with_different_content_is_a_conflict() -> None:
    owner, case_id, _, store, writer, services = make_world()
    ctx = make_ctx(owner, services, store, writer)
    await propose(ctx, case_id)
    again = await propose(ctx, case_id, description="Một nội dung khác hẳn.")
    assert again["error"]["code"] == "request_conflict" and len(store.rows) == 1


# --- get_case_context -----------------------------------------------------------------------------
async def test_case_context_labels_user_text_and_never_returns_evidence_content() -> None:
    owner, case_id, _, store, writer, services = make_world()
    out = await get_case_context(
        RunContextWrapper(make_ctx(owner, services, store, writer)), str(case_id)
    )
    assert out["userReported"]["label"] == "[người dùng kể]"
    assert out["evidence"][0]["filename"] == "anh1.png"
    assert "NỘI DUNG GỐC" not in json.dumps(out, ensure_ascii=False)
    stranger = await get_case_context(
        RunContextWrapper(make_ctx(uuid4(), services, store, writer)), str(case_id)
    )
    assert stranger == {"error": {"code": "not_found", "retryable": False}}


# --- save: every gate -----------------------------------------------------------------------------
async def saved(ctx, proposal_id) -> dict[str, Any]:
    return await save_confirmed_event(RunContextWrapper(ctx), proposal_id=str(proposal_id))


async def approved_proposal(ctx, store, case_id) -> UUID:
    pid = UUID((await propose(ctx, case_id))["proposalId"])
    store.set(pid, status="approved", approval_binding={"decision": "approve"}, decided_at=NOW)
    return pid


async def test_save_applies_exactly_once_and_is_idempotent() -> None:
    owner, case_id, _, store, writer, services = make_world()
    ctx = make_ctx(owner, services, store, writer)
    pid = await approved_proposal(ctx, store, case_id)
    first, second = await saved(ctx, pid), await saved(ctx, pid)
    assert first == {"status": "applied", "result": {"eventId": "e-1"}} == second
    assert writer.calls == 1 and writer.applied == ["Bạn A nhắn tin chế giễu trong nhóm lớp."]


async def test_save_before_approval_does_not_reach_the_writer() -> None:
    owner, case_id, _, store, writer, services = make_world()
    ctx = make_ctx(owner, services, store, writer)
    pid = UUID((await propose(ctx, case_id))["proposalId"])
    assert (await saved(ctx, pid))["error"]["code"] == "not_approved" and writer.calls == 0


@pytest.mark.parametrize("terminal", ["rejected", "failed"])
async def test_rejected_or_failed_proposals_never_write(terminal) -> None:
    owner, case_id, _, store, writer, services = make_world()
    ctx = make_ctx(owner, services, store, writer)
    pid = UUID((await propose(ctx, case_id))["proposalId"])
    store.set(pid, status=terminal)
    assert (await saved(ctx, pid))["error"]["code"] == f"proposal_{terminal}" and writer.calls == 0


async def test_expired_proposal_never_writes() -> None:
    owner, case_id, _, store, writer, services = make_world()
    ctx = make_ctx(owner, services, store, writer)
    pid = await approved_proposal(ctx, store, case_id)
    store.set(pid, expires_at=datetime.now(UTC) - timedelta(seconds=1))
    assert (await saved(ctx, pid))["error"]["code"] == "proposal_expired" and writer.calls == 0


async def test_tampered_payload_fails_the_hash_check() -> None:
    owner, case_id, _, store, writer, services = make_world()
    ctx = make_ctx(owner, services, store, writer)
    pid = await approved_proposal(ctx, store, case_id)
    row = store.rows[pid]
    store.set(
        pid, payload={**row.payload, "event": {**row.payload["event"], "description": "đã bị sửa"}}
    )
    assert (await saved(ctx, pid))["error"]["code"] == "payload_mismatch" and writer.calls == 0


async def test_foreign_wrong_conversation_and_unknown_ids_are_not_found() -> None:
    owner, case_id, _, store, writer, services = make_world()
    ctx = make_ctx(owner, services, store, writer)
    pid = await approved_proposal(ctx, store, case_id)
    assert (await saved(make_ctx(uuid4(), services, store, writer), pid))["error"][
        "code"
    ] == "not_found"
    other_conv = make_ctx(owner, services, store, writer)  # a different conversation
    assert (await saved(other_conv, pid))["error"]["code"] == "not_found"
    assert (await saved(ctx, uuid4()))["error"]["code"] == "not_found"
    assert (await saved(ctx, "not-a-uuid"))["error"]["code"] == "not_found"
    assert writer.calls == 0


def test_save_tool_takes_only_a_proposal_id_and_requires_approval() -> None:
    registry = build_registry(AppConfig())
    assert registry.tool_signatures()["save_confirmed_event"] == ("proposal_id",)
    assert registry.requires_approval("save_confirmed_event")
    assert registry.policy("save_confirmed_event").access == "write"
    assert not registry.requires_approval("propose_case_event")


# --- full flow through the real runtime ----------------------------------------------------------------
def usage() -> Usage:
    return Usage(requests=1, input_tokens=5, output_tokens=5, total_tokens=10)


PROPOSE_ARGS = {
    "description": "Bạn A nhắn tin chế giễu.",
    "basis": "user_stated",
    "rationale": "Bạn vừa kể.",
    "when": "2026-11-03",
    "time_precision": "day",
    "place": "Nhóm lớp",
}


async def drive_to_pending_approval():
    """Turn 1 proposes (nothing saved); turn 2 asks to save and pauses for the user."""
    owner, case_id, _, store, writer, services = make_world()
    conversation_id = uuid4()
    session = SQLiteSession(str(conversation_id))

    ctx1 = make_ctx(owner, services, store, writer, conversation_id=conversation_id)
    turn1 = ScriptedModel(
        [
            ModelStep(
                output=[
                    function_call(
                        "propose_case_event",
                        {"case_id": str(case_id), **PROPOSE_ARGS},
                        call_id="call-1",
                    )
                ],
                usage=usage(),
            ),
            ModelStep(
                output=[assistant_message("Mình soạn sẵn một mốc, CHƯA LƯU. Bạn muốn lưu không?")],
                usage=usage(),
            ),
        ]
    )
    runtime = CompanionRuntime(AppConfig(), build_registry(AppConfig()), model=turn1)
    events1 = [
        e
        async for e in runtime.stream_turn(
            ctx=ctx1, user_input="Hôm 3/11 bạn A chế giễu mình", session=session
        )
    ]
    (pid,) = list(store.rows)

    ctx2 = make_ctx(
        owner, services, store, writer, conversation_id=conversation_id, tool_call_id="call-2"
    )
    turn2 = ScriptedModel(
        [
            ModelStep(
                output=[
                    function_call(
                        "save_confirmed_event", {"proposal_id": str(pid)}, call_id="call-2"
                    )
                ],
                usage=usage(),
            ),
            ModelStep(output=[assistant_message("Đã lưu mốc vào hồ sơ.")], usage=usage()),
        ]
    )
    runtime = CompanionRuntime(AppConfig(), build_registry(AppConfig()), model=turn2)
    events2 = [
        e async for e in runtime.stream_turn(ctx=ctx2, user_input="Có, lưu đi", session=session)
    ]
    return store, writer, pid, runtime, ctx2, session, events1, events2


async def test_proposing_saves_nothing_and_the_dialog_shows_the_stored_proposal() -> None:
    store, writer, pid, runtime, ctx2, session, events1, events2 = await drive_to_pending_approval()
    assert events1[-1].data.status == "completed" and store.rows[pid].status == "proposed"
    approval = next(e for e in events2 if e.event == "approval.required").data
    assert events2[-1].data.status == "awaiting_approval"
    assert approval.tool == "save_confirmed_event" and approval.label == "Lưu mốc vào hồ sơ"
    assert approval.preview["description"] == "Bạn A nhắn tin chế giễu."
    assert approval.preview["proposalId"] == str(pid)
    assert writer.calls == 0 and not [e for e in events2 if e.event == "message.completed"]


async def test_reject_never_calls_the_domain_and_leaves_the_proposal_unsaved() -> None:
    store, writer, pid, runtime, ctx2, session, *_ = await drive_to_pending_approval()
    (pending,) = runtime.pending_approvals(ctx2.run_id)
    events = [
        e
        async for e in runtime.resume_after_approval(
            ctx=ctx2,
            serialized_state=pending.serialized_state,
            approved=False,
            session=session,
            tool_call_id="call-2",
        )
    ]
    assert writer.calls == 0 and writer.applied == []
    assert store.rows[pid].status == "proposed"
    assert events[-1].event == "run.completed"


async def test_approve_after_the_gateway_binds_the_decision_saves_exactly_once() -> None:
    store, writer, pid, runtime, ctx2, session, *_ = await drive_to_pending_approval()
    (pending,) = runtime.pending_approvals(ctx2.run_id)
    # The gateway marks the stored proposal approved (with its binding) before resuming.
    store.set(pid, status="approved", approval_binding={"decision": "approve"}, decided_at=NOW)
    events = [
        e
        async for e in runtime.resume_after_approval(
            ctx=ctx2,
            serialized_state=pending.serialized_state,
            approved=True,
            session=session,
            tool_call_id="call-2",
        )
    ]
    assert writer.calls == 1 and writer.applied == ["Bạn A nhắn tin chế giễu."]
    assert store.rows[pid].status == "applied"
    done = next(e for e in events if e.event == "message.completed").data
    assert done.content == "Đã lưu mốc vào hồ sơ."


async def test_approval_without_the_gateway_binding_still_cannot_write() -> None:
    """If the SDK approval is granted but the proposal row was never approved, nothing is written."""
    store, writer, pid, runtime, ctx2, session, *_ = await drive_to_pending_approval()
    (pending,) = runtime.pending_approvals(ctx2.run_id)
    events = [
        e
        async for e in runtime.resume_after_approval(
            ctx=ctx2,
            serialized_state=pending.serialized_state,
            approved=True,
            session=session,
            tool_call_id="call-2",
        )
    ]
    assert writer.calls == 0 and store.rows[pid].status == "proposed"
    assert next(e for e in events if e.event == "tool.completed").data.ok is False
