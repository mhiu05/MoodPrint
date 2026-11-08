"""Propose → approve → save against PostgreSQL: nothing is written before a bound approval.

Everything here uses the real ProposalStore/ApprovalService/IncidentService/ActionPlanService,
RLS and the audit trail. Only the model is scripted.
"""

import asyncio
from uuid import uuid4

import pytest
from agents.testing import ModelStep, ScriptedModel, assistant_message, function_call
from agents.usage import Usage
from app.agent_gateway.proposals import SqlConfirmedEventWriter, SqlPlanWriter, SqlProposalStore
from app.agent_gateway.sse import RunStream, produce
from app.modules.conversations.approvals import ApprovalService
from app.modules.conversations.service import ConversationService
from app.modules.incidents.schemas import CaseCreate
from app.modules.incidents.service import IncidentService
from app.modules.plans.service import ActionPlanService
from moodprint_agent.runtime import CompanionRuntime
from moodprint_agent.tools.factory import build_registry
from moodprint_agent.tools.proposals import event_id_for
from moodprint_shared.config import AppConfig
from moodprint_shared.contracts.errors import NotFound, VersionConflict
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from backend.tests.integration.conftest import local_value

pytestmark = pytest.mark.integration
CFG = AppConfig()


@pytest.fixture
async def admin():
    engine = create_async_engine(local_value("TEST_ADMIN_DATABASE_URL"), hide_parameters=True)
    try:
        yield engine
    finally:
        await engine.dispose()


def usage() -> Usage:
    return Usage(requests=1, input_tokens=5, output_tokens=5, total_tokens=10)


def runtime_for(*steps: ModelStep) -> CompanionRuntime:
    return CompanionRuntime(CFG, build_registry(CFG), model=ScriptedModel(list(steps)))


async def run_turn(service, auth, conversation_id, runtime, content, **extra):
    turn = await service.begin_turn(auth, conversation_id, uuid4(), content)
    await produce(
        stream=RunStream(),
        runtime=runtime,
        service=service,
        auth=auth,
        turn=turn,
        request_id="it",
        content=content,
        **extra,
    )
    return turn


PROPOSE = {
    "description": "Bạn A nhắn tin chế giễu trong nhóm lớp.",
    "basis": "user_stated",
    "rationale": "Bạn vừa kể điều này.",
    "when": "2026-11-03",
    "time_precision": "day",
    "place": "Nhóm chat lớp",
}


async def rows(admin, sql, **params):
    async with admin.connect() as conn:
        return (await conn.execute(text(sql), params)).mappings().all()


async def count_events(admin, case_id):
    return (
        await rows(admin, "SELECT count(*) AS n FROM app.case_events WHERE case_id=:c", c=case_id)
    )[0]["n"]


async def propose_via_agent(service, auth, case_id, conversation_id):
    runtime = runtime_for(
        ModelStep(
            output=[
                function_call(
                    "propose_case_event", {"case_id": str(case_id), **PROPOSE}, call_id="p1"
                )
            ],
            usage=usage(),
        ),
        ModelStep(
            output=[assistant_message("Mình soạn sẵn một mốc, CHƯA LƯU. Bạn muốn lưu không?")],
            usage=usage(),
        ),
    )
    await run_turn(service, auth, conversation_id, runtime, "Hôm 3/11 bạn A chế giễu mình")


async def ask_to_save(service, auth, conversation_id, proposal_id):
    runtime = runtime_for(
        ModelStep(
            output=[
                function_call(
                    "save_confirmed_event", {"proposal_id": str(proposal_id)}, call_id="s1"
                )
            ],
            usage=usage(),
        ),
        ModelStep(output=[assistant_message("Đã lưu mốc vào hồ sơ.")], usage=usage()),
    )
    turn = await run_turn(service, auth, conversation_id, runtime, "Có, lưu đi")
    (checkpoint,) = runtime.pending_approvals(turn.run_id)
    return runtime, turn, checkpoint


async def world(db_engine, identities):
    auth, other = identities
    service = ConversationService(db_engine)
    case = await IncidentService(db_engine).create(auth, CaseCreate(id=uuid4()))
    conversation = await service.create(auth, uuid4())
    return auth, other, service, case, conversation["id"]


async def finish_resume(service, auth, paused_runtime, turn, checkpoint, approved):
    row, message = await ApprovalService(service.engine).decide(
        auth, turn.run_id, checkpoint.id, approved
    )
    handle = type(turn)(
        run_id=row["run_id"],
        conversation_id=row["conversation_id"],
        message_id=message["id"],
        client_message_id=message["client_message_id"],
    )
    await produce(
        stream=RunStream(),
        runtime=paused_runtime,
        service=service,
        auth=auth,
        turn=handle,
        request_id="it",
        content="",
        resume={**row, "approved": approved},
    )


async def test_nothing_is_written_until_the_bound_approval_then_exactly_one_confirmed_event(
    db_engine, identities, admin
):
    auth, other, service, case, conv = await world(db_engine, identities)
    await propose_via_agent(service, auth, case.id, conv)
    (proposal,) = await rows(
        admin, "SELECT * FROM app.agent_proposals WHERE target_case_id=:c", c=case.id
    )
    assert proposal["status"] == "proposed" and await count_events(admin, case.id) == 0

    paused, turn, checkpoint = await ask_to_save(service, auth, conv, proposal["id"])
    assert await count_events(admin, case.id) == 0  # the SDK is paused on approval
    (pending,) = await rows(
        admin,
        "SELECT status,arguments_preview FROM app.tool_approvals WHERE run_id=:r",
        r=turn.run_id,
    )
    assert pending["status"] == "pending" and pending["arguments_preview"]["proposalId"] == str(
        proposal["id"]
    )

    await finish_resume(service, auth, paused, turn, checkpoint, approved=True)
    (done,) = await rows(admin, "SELECT * FROM app.agent_proposals WHERE id=:i", i=proposal["id"])
    assert done["status"] == "applied" and done["approval_binding"]["decision"] == "approve"
    assert done["approval_binding"]["payload_sha256"] == done["payload_sha256"]
    events = await rows(
        admin, "SELECT id,provenance,description FROM app.case_events WHERE case_id=:c", c=case.id
    )
    assert len(events) == 1 and events[0]["provenance"] == "user_confirmed"
    assert events[0]["id"] == event_id_for(auth.user_id, proposal["id"])
    assert events[0]["description"] == PROPOSE["description"]  # exactly what the user saw
    audits = await rows(
        admin, "SELECT metadata FROM app.audit_events WHERE entity_id=:e", e=events[0]["id"]
    )
    assert len(audits) == 1 and audits[0]["metadata"]["proposalId"] == str(proposal["id"])


async def test_reject_writes_nothing_and_the_proposal_stays_rejected(db_engine, identities, admin):
    auth, other, service, case, conv = await world(db_engine, identities)
    await propose_via_agent(service, auth, case.id, conv)
    (proposal,) = await rows(
        admin, "SELECT id FROM app.agent_proposals WHERE target_case_id=:c", c=case.id
    )
    paused, turn, checkpoint = await ask_to_save(service, auth, conv, proposal["id"])
    await finish_resume(service, auth, paused, turn, checkpoint, approved=False)
    (after,) = await rows(
        admin,
        "SELECT status,approval_binding FROM app.agent_proposals WHERE id=:i",
        i=proposal["id"],
    )
    assert after["status"] == "rejected" and after["approval_binding"] is None
    assert await count_events(admin, case.id) == 0


async def test_an_expired_proposal_cannot_be_approved_and_the_decision_rolls_back(
    db_engine, identities, admin
):
    auth, other, service, case, conv = await world(db_engine, identities)
    await propose_via_agent(service, auth, case.id, conv)
    (proposal,) = await rows(
        admin, "SELECT id FROM app.agent_proposals WHERE target_case_id=:c", c=case.id
    )
    paused, turn, checkpoint = await ask_to_save(service, auth, conv, proposal["id"])
    async with admin.begin() as conn:  # time passes (the owner role cannot touch expires_at)
        await conn.execute(
            text(
                "UPDATE app.agent_proposals SET expires_at=now()-interval '1 second', created_at=now()-interval '1 hour' WHERE id=:i"
            ),
            {"i": proposal["id"]},
        )
    with pytest.raises(VersionConflict):
        await ApprovalService(db_engine).decide(auth, turn.run_id, checkpoint.id, True)
    (approval,) = await rows(
        admin, "SELECT status FROM app.tool_approvals WHERE id=:i", i=checkpoint.id
    )
    assert approval["status"] == "pending"  # the whole decision was rolled back
    assert await count_events(admin, case.id) == 0


async def test_a_dialog_whose_preview_no_longer_matches_the_stored_proposal_cannot_approve(
    db_engine, identities, admin
):
    auth, other, service, case, conv = await world(db_engine, identities)
    await propose_via_agent(service, auth, case.id, conv)
    (proposal,) = await rows(
        admin, "SELECT id FROM app.agent_proposals WHERE target_case_id=:c", c=case.id
    )
    paused, turn, checkpoint = await ask_to_save(service, auth, conv, proposal["id"])
    async with admin.begin() as conn:  # the preview the user saw is altered after the fact
        await conn.execute(
            text(
                "UPDATE app.tool_approvals SET arguments_preview=jsonb_set(arguments_preview,'{description}','\"khác hẳn\"') WHERE id=:i"
            ),
            {"i": checkpoint.id},
        )
    with pytest.raises(VersionConflict):
        await ApprovalService(db_engine).decide(auth, turn.run_id, checkpoint.id, True)
    assert await count_events(admin, case.id) == 0


async def test_other_users_cannot_read_decide_or_apply_a_proposal(db_engine, identities, admin):
    auth, other, service, case, conv = await world(db_engine, identities)
    await propose_via_agent(service, auth, case.id, conv)
    (proposal,) = await rows(
        admin, "SELECT id FROM app.agent_proposals WHERE target_case_id=:c", c=case.id
    )
    paused, turn, checkpoint = await ask_to_save(service, auth, conv, proposal["id"])
    store = SqlProposalStore(db_engine, CFG)
    assert await store.get(other, proposal["id"]) is None
    with pytest.raises(NotFound):
        await ApprovalService(db_engine).decide(other, turn.run_id, checkpoint.id, True)
    writer = SqlConfirmedEventWriter(store, IncidentService(db_engine))
    outcome = await writer.apply(other, proposal_id=proposal["id"], run_id=turn.run_id)
    assert outcome.status == "not_found" and await count_events(admin, case.id) == 0
    with pytest.raises(NotFound):  # another user's case cannot even receive a proposal
        await store.create(
            other,
            conversation_id=conv,
            run_id=turn.run_id,
            kind="case_event",
            target_case_id=case.id,
            payload={"a": 1},
            preview={"b": 2},
            base_version=1,
            request_key="x",
        )


async def approved_proposal(db_engine, admin, auth, service, case, conv):
    """A proposal that went through the real approval path, but not yet applied."""
    await propose_via_agent(service, auth, case.id, conv)
    (proposal,) = await rows(
        admin, "SELECT id FROM app.agent_proposals WHERE target_case_id=:c", c=case.id
    )
    paused, turn, checkpoint = await ask_to_save(service, auth, conv, proposal["id"])
    await ApprovalService(db_engine).decide(auth, turn.run_id, checkpoint.id, True)
    return proposal["id"], turn.run_id


async def test_crash_after_domain_commit_before_applied_retries_without_a_second_event(
    db_engine, identities, admin
):
    auth, other, service, case, conv = await world(db_engine, identities)
    pid, run_id = await approved_proposal(db_engine, admin, auth, service, case, conv)
    incidents = IncidentService(db_engine)
    writer = SqlConfirmedEventWriter(SqlProposalStore(db_engine, CFG), incidents)
    # Simulate the crash window: the domain write committed, the proposal still says "approved".
    store = SqlProposalStore(db_engine, CFG)
    stored = await store.get(auth, pid)
    from moodprint_shared.contracts.incidents import EventCreate

    event = stored.payload["event"]
    await incidents.add_confirmed_event(
        auth,
        case.id,
        EventCreate(
            id=event_id_for(auth.user_id, pid),
            when=event["when"],
            time_precision=event["time_precision"],
            place=event["place"],
            description=event["description"],
            provenance="user_confirmed",
        ),
        proposal_id=pid,
    )
    version_after_domain_write = (await incidents.get_case(auth, case.id)).version
    outcome = await writer.apply(auth, proposal_id=pid, run_id=run_id)
    assert outcome.status == "applied"
    assert await count_events(admin, case.id) == 1
    assert (await incidents.get_case(auth, case.id)).version == version_after_domain_write
    assert (
        len(
            await rows(
                admin,
                "SELECT 1 FROM app.audit_events WHERE entity_id=:e",
                e=event_id_for(auth.user_id, pid),
            )
        )
        == 1
    )
    again = await writer.apply(auth, proposal_id=pid, run_id=run_id)
    assert again.status == "applied" and again.result == outcome.result


async def test_two_concurrent_applies_produce_one_event_and_one_audit(db_engine, identities, admin):
    auth, other, service, case, conv = await world(db_engine, identities)
    pid, run_id = await approved_proposal(db_engine, admin, auth, service, case, conv)
    incidents = IncidentService(db_engine)
    results = await asyncio.gather(
        *[
            SqlConfirmedEventWriter(SqlProposalStore(db_engine, CFG), incidents).apply(
                auth, proposal_id=pid, run_id=run_id
            )
            for _ in range(4)
        ]
    )
    assert {r.status for r in results} == {"applied"}
    assert await count_events(admin, case.id) == 1
    assert (
        len(
            await rows(
                admin,
                "SELECT 1 FROM app.audit_events WHERE entity_id=:e",
                e=event_id_for(auth.user_id, pid),
            )
        )
        == 1
    )


async def test_a_stale_case_version_fails_the_proposal_without_writing(
    db_engine, identities, admin
):
    auth, other, service, case, conv = await world(db_engine, identities)
    pid, run_id = await approved_proposal(db_engine, admin, auth, service, case, conv)
    async with admin.begin() as conn:  # someone else edits the case after the proposal was made
        await conn.execute(
            text("UPDATE app.cases SET version=version+1 WHERE id=:c"), {"c": case.id}
        )
    writer = SqlConfirmedEventWriter(SqlProposalStore(db_engine, CFG), IncidentService(db_engine))
    outcome = await writer.apply(auth, proposal_id=pid, run_id=run_id)
    assert outcome.status == "conflict" and outcome.error == "version_conflict"
    assert await count_events(admin, case.id) == 0
    (row,) = await rows(admin, "SELECT status FROM app.agent_proposals WHERE id=:i", i=pid)
    assert row["status"] == "failed"


async def test_a_cancelled_run_never_starts_a_domain_write(db_engine, identities, admin):
    auth, other, service, case, conv = await world(db_engine, identities)
    pid, run_id = await approved_proposal(db_engine, admin, auth, service, case, conv)
    async with admin.begin() as conn:
        await conn.execute(
            text("UPDATE app.agent_runs SET status='cancelled', finished_at=now() WHERE id=:r"),
            {"r": run_id},
        )
    writer = SqlConfirmedEventWriter(SqlProposalStore(db_engine, CFG), IncidentService(db_engine))
    outcome = await writer.apply(auth, proposal_id=pid, run_id=run_id)
    assert outcome.status == "failed" and outcome.error == "run_not_active"
    assert await count_events(admin, case.id) == 0


async def test_unapproved_or_tampered_proposals_are_never_applied(db_engine, identities, admin):
    auth, other, service, case, conv = await world(db_engine, identities)
    await propose_via_agent(service, auth, case.id, conv)
    (proposal,) = await rows(
        admin, "SELECT id FROM app.agent_proposals WHERE target_case_id=:c", c=case.id
    )
    run = (
        await rows(admin, "SELECT run_id FROM app.agent_proposals WHERE id=:i", i=proposal["id"])
    )[0]["run_id"]
    writer = SqlConfirmedEventWriter(SqlProposalStore(db_engine, CFG), IncidentService(db_engine))
    assert (
        await writer.apply(auth, proposal_id=proposal["id"], run_id=run)
    ).status == "rejected"  # still "proposed"
    assert await count_events(admin, case.id) == 0
    async with (
        admin.begin() as conn
    ):  # a database owner tampers with the payload behind the app's back
        await conn.execute(
            text(
                "UPDATE app.agent_proposals SET status='approved', approval_binding=jsonb_build_object('decision','approve','payload_sha256',payload_sha256), decided_at=now(), payload=jsonb_set(payload,'{event,description}','\"đã bị sửa\"') WHERE id=:i"
            ),
            {"i": proposal["id"]},
        )
    outcome = await writer.apply(auth, proposal_id=proposal["id"], run_id=run)
    assert outcome.error == "payload_mismatch" and await count_events(admin, case.id) == 0


async def test_plan_proposal_applies_once_survives_a_crash_and_reports_version_conflicts(
    db_engine, identities, admin
):
    auth, other, service, case, conv = await world(db_engine, identities)
    plans = ActionPlanService(db_engine)
    store = SqlProposalStore(db_engine, CFG)
    run = (await service.begin_turn(auth, conv, uuid4(), "Lập kế hoạch")).run_id
    from uuid import uuid5

    from moodprint_agent.tools.plan import PLAN_NAMESPACE

    plan_id = uuid5(PLAN_NAMESPACE, f"plan:{case.id}")
    payload = {
        "case_id": str(case.id),
        "plan": {
            "id": str(plan_id),
            "goal": "Được hỗ trợ",
            "chosen_option_id": "",
            "status": "draft",
            "next_review_date": None,
            "outcome_notes": "",
            "items": [
                {
                    "id": str(uuid4()),
                    "label": "Nói với cô",
                    "status": "not_started",
                    "notes": "",
                    "priority": "high",
                    "reason": "an toàn",
                }
            ],
        },
        "rationale": "r",
    }
    proposal = await store.create(
        auth,
        conversation_id=conv,
        run_id=run,
        kind="action_plan",
        target_case_id=case.id,
        payload=payload,
        preview={"summary": "Kế hoạch"},
        base_version=None,
        request_key="plan-1",
    )
    async with (
        admin.begin() as conn
    ):  # approval bound as the gateway would do (tool approval first)
        await conn.execute(
            text("""INSERT INTO app.tool_approvals(id,run_id,owner_id,tool_name,tool_call_id,arguments_preview,run_state,status,expires_at)
            VALUES(gen_random_uuid(),:r,:o,'save_plan','plan-1','{}','{}','approved',now()+interval '10 minutes')"""),
            {"r": run, "o": auth.user_id},
        )
        await conn.execute(
            text(
                "UPDATE app.agent_proposals SET status='approved',decided_at=now(),approval_binding=jsonb_build_object('decision','approve','payload_sha256',payload_sha256) WHERE id=:i"
            ),
            {"i": proposal.id},
        )
    writer = SqlPlanWriter(store, plans)
    first = await writer.apply(auth, proposal_id=proposal.id, run_id=run)
    assert first.status == "applied"
    assert (await plans.get_for_case(auth, case.id)).goal == "Được hỗ trợ"
    assert (await writer.apply(auth, proposal_id=proposal.id, run_id=run)).result == first.result

    # Crash window: plan committed, proposal still "approved" => retry recognises its own plan.
    async with admin.begin() as conn:
        await conn.execute(
            text(
                "UPDATE app.agent_proposals SET status='approved',result=NULL,applied_at=NULL WHERE id=:i"
            ),
            {"i": proposal.id},
        )
    assert (await writer.apply(auth, proposal_id=proposal.id, run_id=run)).status == "applied"
    assert len(await rows(admin, "SELECT 1 FROM app.action_plans WHERE case_id=:c", c=case.id)) == 1
