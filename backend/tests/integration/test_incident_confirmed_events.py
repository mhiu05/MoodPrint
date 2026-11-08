"""Confirmed domain writes stay owner scoped, transactional and distinct from REST."""

import asyncio
from uuid import uuid4

import httpx
import pytest
from app.core.auth import get_auth
from app.core.errors import ApiError
from app.main import create_app
from app.modules.evidence.schemas import NoteCreate, UploadCreate
from app.modules.evidence.service import EvidenceService
from app.modules.incidents.schemas import CaseCreate
from app.modules.incidents.service import IncidentService
from moodprint_shared.contracts.incidents import EventCreate
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from backend.tests.integration.conftest import local_value
from backend.tests.integration.test_phase1_domains import Files

pytestmark = pytest.mark.integration


@pytest.fixture
async def audit_admin():
    engine = create_async_engine(local_value("TEST_ADMIN_DATABASE_URL"), hide_parameters=True)
    try:
        yield engine
    finally:
        await engine.dispose()


async def audits(engine, event_id):
    async with engine.connect() as conn:
        return (
            (
                await conn.execute(
                    text("""SELECT actor_id, action, entity_type, metadata
                        FROM app.audit_events WHERE entity_id=:id"""),
                    {"id": event_id},
                )
            )
            .mappings()
            .all()
        )


def confirmed(**changes):
    return EventCreate.model_validate(
        {
            "id": uuid4(),
            "description": "Synthetic confirmed event",
            "provenance": "user_confirmed",
            **changes,
        }
    )


async def test_confirmed_event_persists_once_and_exact_retry_does_not_bump_case_version(
    db_engine, identities, audit_admin
):
    owner = identities[0]
    service = IncidentService(db_engine)
    case = await service.create(owner, CaseCreate(id=uuid4()))
    data, proposal_id = confirmed(), uuid4()
    first = await service.add_confirmed_event(owner, case.id, data, proposal_id=proposal_id)
    after = await service.get_case(owner, case.id)
    retry = await IncidentService(db_engine).add_confirmed_event(
        owner, case.id, data, proposal_id=proposal_id
    )
    assert first == retry
    assert first.provenance == "user_confirmed"
    assert after.events == [first]
    assert after.version == case.version + 1
    assert (await service.get_case(owner, case.id)).version == after.version
    rows = await audits(audit_admin, data.id)
    assert len(rows) == 1
    assert dict(rows[0]) == {
        "actor_id": owner.user_id,
        "action": "case.event_confirmed_from_proposal",
        "entity_type": "case_event",
        "metadata": {"proposalId": str(proposal_id)},
    }


async def test_concurrent_identical_confirmed_writes_are_idempotent(
    db_engine, identities, audit_admin
):
    owner = identities[0]
    service = IncidentService(db_engine)
    case = await service.create(owner, CaseCreate(id=uuid4()))
    data, proposal_id = confirmed(), uuid4()
    first, second = await asyncio.gather(
        service.add_confirmed_event(owner, case.id, data, proposal_id=proposal_id),
        IncidentService(db_engine).add_confirmed_event(
            owner, case.id, data, proposal_id=proposal_id
        ),
    )
    assert first == second
    assert len(await audits(audit_admin, data.id)) == 1
    assert (await service.get_case(owner, case.id)).version == case.version + 1


async def test_other_owner_cannot_save_or_retry_confirmed_event(db_engine, identities):
    owner, other = identities
    service = IncidentService(db_engine)
    case = await service.create(owner, CaseCreate(id=uuid4()))
    data, proposal_id = confirmed(), uuid4()
    for saved in (False, True):
        if saved:
            await service.add_confirmed_event(owner, case.id, data, proposal_id=proposal_id)
        with pytest.raises(ApiError) as hidden:
            await service.add_confirmed_event(other, case.id, data, proposal_id=proposal_id)
        assert hidden.value.status_code == 404


@pytest.mark.parametrize(
    "changes",
    [
        {"description": "Changed payload"},
        {"place": "Changed location"},
        {"needs_review": True},
        {"time_precision": "day", "when": "2026-11-08"},
        {"evidence_ids": [uuid4()]},
    ],
)
async def test_retry_with_changed_payload_rejects_conflict_without_audit_or_version_change(
    db_engine, identities, audit_admin, changes
):
    owner = identities[0]
    service = IncidentService(db_engine)
    case = await service.create(owner, CaseCreate(id=uuid4()))
    data, proposal_id = confirmed(), uuid4()
    original = await service.add_confirmed_event(owner, case.id, data, proposal_id=proposal_id)
    version = (await service.get_case(owner, case.id)).version
    with pytest.raises(ApiError) as conflict:
        await service.add_confirmed_event(
            owner, case.id, data.model_copy(update=changes), proposal_id=proposal_id
        )
    assert conflict.value.status_code == 409
    assert conflict.value.code == "conflict"
    after = await service.get_case(owner, case.id)
    assert after.events == [original]
    assert after.version == version
    assert len(await audits(audit_admin, data.id)) == 1


async def test_confirmed_id_cannot_reclassify_existing_user_event(
    db_engine, identities, audit_admin
):
    owner = identities[0]
    service = IncidentService(db_engine)
    case = await service.create(owner, CaseCreate(id=uuid4()))
    data = confirmed()
    await service.add_event(owner, case.id, data.model_copy(update={"provenance": "user_entered"}))
    with pytest.raises(ApiError) as conflict:
        await service.add_confirmed_event(owner, case.id, data, proposal_id=uuid4())
    assert conflict.value.status_code == 409
    assert await audits(audit_admin, data.id) == []


async def test_confirmed_event_evidence_must_be_uploaded_owned_and_in_same_case(
    db_engine, identities, audit_admin
):
    owner, other = identities
    service = IncidentService(db_engine)
    case = await service.create(owner, CaseCreate(id=uuid4()))
    other_case = await service.create(other, CaseCreate(id=uuid4()))
    own_elsewhere = await service.create(owner, CaseCreate(id=uuid4()))
    evidence_service = EvidenceService(db_engine, Files())
    valid = await evidence_service.create_note(
        owner, NoteCreate(id=uuid4(), case_id=case.id, original_text="Synthetic note")
    )
    foreign = await evidence_service.create_note(
        other, NoteCreate(id=uuid4(), case_id=other_case.id, original_text="Other note")
    )
    elsewhere = await evidence_service.create_note(
        owner, NoteCreate(id=uuid4(), case_id=own_elsewhere.id, original_text="Elsewhere note")
    )
    pending = await evidence_service.init_upload(
        owner, UploadCreate(id=uuid4(), case_id=case.id, filename="pending.png", byte_size=1)
    )
    for evidence_id in (foreign.id, elsewhere.id, pending.evidence.id, uuid4()):
        data = confirmed(evidence_ids=[evidence_id])
        with pytest.raises(ApiError) as hidden:
            await service.add_confirmed_event(owner, case.id, data, proposal_id=uuid4())
        assert hidden.value.status_code == 404
        assert await audits(audit_admin, data.id) == []
    data = confirmed(evidence_ids=[valid.id])
    event = await service.add_confirmed_event(owner, case.id, data, proposal_id=uuid4())
    assert event.evidence_ids == [valid.id]


async def test_rest_and_public_domain_add_event_still_reject_confirmed_provenance(
    settings, db_engine, identities
):
    owner = identities[0]
    service = IncidentService(db_engine)
    case = await service.create(owner, CaseCreate(id=uuid4()))
    data = confirmed()
    with pytest.raises(ApiError) as forbidden:
        await service.add_event(owner, case.id, data)
    assert forbidden.value.status_code == 403
    assert forbidden.value.details == {"reason": "fixture_not_allowed"}
    app = create_app(settings)
    app.state.engine = db_engine
    app.dependency_overrides[get_auth] = lambda: owner
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            f"/v1/cases/{case.id}/events", json=data.model_dump(mode="json", by_alias=True)
        )
    assert response.status_code == 403
    assert response.json()["error"]["details"] == {"reason": "fixture_not_allowed"}
    assert (await service.get_case(owner, case.id)).events == []


async def test_equivalent_exact_timestamp_retry_keeps_one_event_and_audit(
    db_engine, identities, audit_admin
):
    owner = identities[0]
    service = IncidentService(db_engine)
    case = await service.create(owner, CaseCreate(id=uuid4()))
    data, proposal_id = confirmed(time_precision="exact", when="2026-11-08T10:00:00+07:00"), uuid4()
    first = await service.add_confirmed_event(owner, case.id, data, proposal_id=proposal_id)
    retry = await service.add_confirmed_event(
        owner,
        case.id,
        data.model_copy(update={"when": "2026-11-08T03:00:00Z"}),
        proposal_id=proposal_id,
    )
    assert first == retry
    assert len(await audits(audit_admin, data.id)) == 1
