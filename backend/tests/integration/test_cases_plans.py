"""Real transaction tests for ownership, lost updates, ordering and persistence."""

from uuid import uuid4

import pytest
from app.core.errors import ApiError
from app.modules.incidents.schemas import CaseCreate, CasePatch
from app.modules.incidents.service import IncidentService
from app.modules.plans.service import ActionPlanService
from safevoice_shared.contracts.incidents import CaseQuery, EventCreate
from safevoice_shared.contracts.plans import PlanItem, PlanUpsert

pytestmark = pytest.mark.integration


async def test_case_events_plan_survive_new_service_and_owner_isolation(db_engine, identities):
    a, b = identities
    service = IncidentService(db_engine)
    event = EventCreate(id=uuid4(), description="Synthetic unknown time")
    case = await service.create(
        a,
        CaseCreate(
            id=uuid4(),
            title="Nhóm bạn",
            summary="Synthetic case",
            status="active",
            first_event=event,
        ),
    )
    assert case.events[0].when == "" and case.events[0].time_precision == "unknown"
    assert (await service.create(a, CaseCreate(id=case.id))).id == case.id
    assert (await service.list_cases(b, CaseQuery())).items == []
    with pytest.raises(ApiError) as hidden:
        await service.get_case(b, case.id)
    assert hidden.value.status_code == 404
    plans = ActionPlanService(db_engine)
    step = PlanItem(id=uuid4(), label="Synthetic safe next step")
    plan = await plans.upsert(
        a,
        case.id,
        PlanUpsert(id=uuid4(), goal="Synthetic goal", items=[step]),
        expected_version=None,
    )
    assert (await ActionPlanService(db_engine).get_for_case(a, case.id)) == plan
    changed = await plans.set_item_status(a, plan.id, step.id, "done")
    detail = await IncidentService(db_engine).get_case(a, case.id)
    assert detail.plan_progress.done == 1 and detail.linked_plan_id == plan.id
    assert changed.version == 2
    with pytest.raises(ApiError) as conflict:
        await plans.upsert(a, case.id, plan, expected_version=1)
    assert conflict.value.status_code == 409
    assert conflict.value.details["latest"]["items"][0]["status"] == "done"


async def test_case_version_transition_search_and_pagination(db_engine, identities):
    a, b = identities
    service = IncidentService(db_engine)
    case = await service.create(
        a, CaseCreate(id=uuid4(), title="Bạn thân", summary="Synthetic", status="active")
    )
    updated = await service.update(a, case.id, CasePatch(version=1, status="monitoring"))
    assert updated.version == 2
    with pytest.raises(ApiError) as stale:
        await service.update(a, case.id, CasePatch(version=1, summary="Stale edit"))
    assert stale.value.status_code == 409 and stale.value.details["latest"]["version"] == 2
    with pytest.raises(ApiError) as invalid:
        await service.update(a, case.id, CasePatch(version=2, status="draft"))
    assert invalid.value.status_code == 422
    assert [x.id for x in (await service.list_cases(a, CaseQuery(q="ban than"))).items] == [case.id]
    for title in ("Alpha", "Zulu"):
        await service.create(a, CaseCreate(id=uuid4(), title=title))
    first = await service.list_cases(a, CaseQuery(limit=1, sort="title"))
    second = await service.list_cases(a, CaseQuery(limit=1, sort="title", cursor=first.next_cursor))
    assert first.items[0].title == "Alpha" and first.items[0].id != second.items[0].id
    with pytest.raises(ApiError):
        await service.list_cases(b, CaseQuery(limit=1, sort="title", cursor=first.next_cursor))


async def test_plan_reorder_atomic_and_completed_requires_all_done(db_engine, identities):
    a = identities[0]
    case = await IncidentService(db_engine).create(a, CaseCreate(id=uuid4()))
    service = ActionPlanService(db_engine)
    items = [PlanItem(id=uuid4(), label=label) for label in ("First", "Second", "Third")]
    plan = await service.upsert(
        a, case.id, PlanUpsert(id=uuid4(), items=items), expected_version=None
    )
    reordered = await service.upsert(
        a, case.id, plan.model_copy(update={"items": list(reversed(items))}), expected_version=1
    )
    assert [item.id for item in reordered.items] == [item.id for item in reversed(items)]
    with pytest.raises(ApiError) as invalid:
        await service.upsert(
            a,
            case.id,
            reordered.model_copy(update={"status": "completed", "goal": "Synthetic goal"}),
            expected_version=2,
        )
    assert invalid.value.status_code == 422
    assert (await service.get_for_case(a, case.id)).version == 2


async def test_event_edit_delete_and_case_delete_cascade(db_engine, identities):
    a, b = identities
    cases = IncidentService(db_engine)
    case = await cases.create(a, CaseCreate(id=uuid4()))
    unknown = await cases.add_event(a, case.id, EventCreate(id=uuid4(), description="Unknown"))
    day = await cases.add_event(
        a,
        case.id,
        EventCreate(id=uuid4(), description="Known day", time_precision="day", when="2026-11-07"),
    )
    assert [e.id for e in (await cases.get_case(a, case.id)).events] == [day.id, unknown.id]
    with pytest.raises(ApiError) as hidden:
        await cases.remove_event(b, case.id, day.id)
    assert hidden.value.status_code == 404
    await cases.remove_event(a, case.id, day.id)
    assert len((await cases.get_case(a, case.id)).events) == 1
    await cases.delete(a, case.id)
    with pytest.raises(ApiError) as deleted:
        await cases.get_case(a, case.id)
    assert deleted.value.status_code == 404


async def test_notes_only_patch_preserves_completed_checkbox(db_engine, identities):
    a = identities[0]
    case = await IncidentService(db_engine).create(a, CaseCreate(id=uuid4()))
    plans = ActionPlanService(db_engine)
    item = PlanItem(id=uuid4(), label="Synthetic step", status="done")
    plan = await plans.upsert(
        a, case.id, PlanUpsert(id=uuid4(), items=[item]), expected_version=None
    )
    changed = await plans.patch_item(a, plan.id, item.id, notes="Synthetic note")
    assert changed.items[0].status == "done" and changed.items[0].notes == "Synthetic note"


async def test_foreign_plan_item_body_id_is_hidden_and_transaction_rolls_back(
    db_engine, identities
):
    a, b = identities
    cases = IncidentService(db_engine)
    ca = await cases.create(a, CaseCreate(id=uuid4()))
    cb = await cases.create(b, CaseCreate(id=uuid4()))
    plans = ActionPlanService(db_engine)
    foreign = PlanItem(id=uuid4(), label="Foreign synthetic step")
    await plans.upsert(a, ca.id, PlanUpsert(id=uuid4(), items=[foreign]), expected_version=None)
    with pytest.raises(ApiError) as hidden:
        await plans.upsert(b, cb.id, PlanUpsert(id=uuid4(), items=[foreign]), expected_version=None)
    assert hidden.value.status_code == 404
    assert await plans.get_for_case(b, cb.id) is None
