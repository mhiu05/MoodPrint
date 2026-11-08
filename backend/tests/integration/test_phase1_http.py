"""OpenAPI-derived owner-ID matrix and school visibility exercise real RLS and routers."""

from uuid import uuid4

import httpx
import pytest
from app.core.auth import get_auth
from app.core.errors import ApiError
from app.main import create_app
from app.modules.contacts.schemas import ContactCreate
from app.modules.contacts.service import ContactService
from app.modules.evidence.schemas import NoteCreate, UploadCreate
from app.modules.evidence.service import EvidenceService
from app.modules.incidents.schemas import CaseCreate, EventWrite
from app.modules.incidents.service import IncidentService
from app.modules.plans.service import ActionPlanService
from app.modules.sharing.schemas import ShareCreate, ShareSubmit
from app.modules.sharing.service import SharingService
from app.modules.support.schemas import DraftCreate
from app.modules.support.service import SupportService
from moodprint_shared.contracts.errors import Forbidden, NotFound
from moodprint_shared.contracts.plans import PlanItem, PlanUpsert
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from backend.tests.integration.conftest import local_value
from backend.tests.integration.test_phase1_domains import Files

pytestmark = pytest.mark.integration


class LiveUser:
    async def require_live_user(self, auth, token):
        return None


@pytest.fixture
async def school(db_engine, identities):
    school_id = uuid4()
    admin = create_async_engine(local_value("TEST_ADMIN_DATABASE_URL"), hide_parameters=True)
    try:
        async with admin.begin() as conn:
            await conn.execute(
                text(
                    "INSERT INTO app.schools(id,name,verification_status) VALUES(:id,'Synthetic school','verified')"
                ),
                {"id": school_id},
            )
            await conn.execute(
                text(
                    "INSERT INTO app.school_memberships(school_id,user_id,role,status) VALUES(:school,:user,'staff','active')"
                ),
                {"school": school_id, "user": identities[1].user_id},
            )
        yield school_id, admin
    finally:
        async with admin.begin() as conn:
            await conn.execute(
                text("DELETE FROM app.case_shares WHERE school_id=:id"), {"id": school_id}
            )
            await conn.execute(
                text("DELETE FROM app.school_memberships WHERE school_id=:id"), {"id": school_id}
            )
            await conn.execute(text("DELETE FROM app.schools WHERE id=:id"), {"id": school_id})
        await admin.dispose()


async def test_every_phase1_owner_id_route_returns_404_for_other_user(
    settings, db_engine, identities, school
):
    a, b = identities
    storage = Files()
    event_id = uuid4()
    cases = IncidentService(db_engine)
    case = await cases.create(
        a,
        CaseCreate(
            id=uuid4(),
            title="Synthetic",
            summary="Synthetic case",
            status="active",
            first_event=EventWrite(
                id=event_id, description="Synthetic event", time_precision="unknown", when=""
            ),
        ),
    )
    item_id = uuid4()
    plan = await ActionPlanService(db_engine).upsert(
        a,
        case.id,
        PlanUpsert(
            id=uuid4(), goal="Synthetic goal", items=[PlanItem(id=item_id, label="Synthetic step")]
        ),
        expected_version=None,
    )
    evidence = await EvidenceService(db_engine, storage).create_note(
        a, NoteCreate(id=uuid4(), case_id=case.id, original_text="Synthetic note")
    )
    contact = await ContactService(db_engine).create(
        a, ContactCreate(id=uuid4(), label="Teacher", role="Teacher")
    )
    draft = await SupportService(db_engine).create(
        a, DraftCreate(id=uuid4(), case_id=case.id, recipient_type="teacher")
    )
    share = await SharingService(db_engine, storage).create(
        a, ShareCreate(id=uuid4(), case_id=case.id, school_id=school[0])
    )
    app = create_app(settings)
    app.state.engine, app.state.storage, app.state.auth_admin = db_engine, storage, LiveUser()
    app.dependency_overrides[get_auth] = lambda: b
    ids = {
        "case": str(case.id),
        "event": str(event_id),
        "plan": str(plan.id),
        "item": str(item_id),
        "evidence": str(evidence.id),
        "contact": str(contact.id),
        "draft": str(draft.id),
        "share": str(share.id),
    }
    event_body = {
        "id": str(event_id),
        "description": "Synthetic event",
        "timePrecision": "unknown",
        "when": "",
    }
    configs = {
        ("/v1/cases/{id}", "get"): ("case", None),
        ("/v1/cases/{id}", "patch"): ("case", {"version": 1, "title": "Foreign edit"}),
        ("/v1/cases/{id}", "delete"): ("case", None),
        ("/v1/cases/{id}/related", "get"): ("case", None),
        ("/v1/cases/{id}/events", "post"): ("case", event_body),
        ("/v1/cases/{id}/events/{event_id}", "patch"): ("case", event_body),
        ("/v1/cases/{id}/events/{event_id}", "delete"): ("case", None),
        ("/v1/cases/{id}/plan", "get"): ("case", None),
        ("/v1/cases/{id}/plan", "put"): ("case", {"id": str(plan.id), "version": 1}),
        ("/v1/plans/{plan_id}/items/{item_id}", "patch"): ("plan", {"status": "done"}),
        ("/v1/cases/{id}/evidence/{evidenceId}/link", "post"): ("case", None),
        ("/v1/cases/{id}/evidence/{evidenceId}/link", "delete"): ("case", None),
        ("/v1/evidence/{id}", "get"): ("evidence", None),
        ("/v1/evidence/{id}", "patch"): ("evidence", {"reviewStatus": "confirmed"}),
        ("/v1/evidence/{id}", "delete"): ("evidence", None),
        ("/v1/evidence/{id}/upload-token", "post"): ("evidence", None),
        ("/v1/evidence/{id}/complete", "post"): ("evidence", None),
        ("/v1/evidence/{id}/download-url", "get"): ("evidence", None),
        ("/v1/trusted-contacts/{id}", "patch"): ("contact", {"label": "Foreign"}),
        ("/v1/trusted-contacts/{id}", "delete"): ("contact", None),
        ("/v1/support-drafts/{id}", "get"): ("draft", None),
        ("/v1/support-drafts/{id}", "patch"): ("draft", {"version": 1, "content": "Foreign"}),
        ("/v1/support-drafts/{id}", "delete"): ("draft", None),
        ("/v1/shares/{id}", "get"): ("share", None),
        ("/v1/shares/{id}", "patch"): ("share", {"version": 1, "sharedFields": ["summary"]}),
        ("/v1/shares/{id}/preview", "get"): ("share", None),
        ("/v1/shares/{id}/submit", "post"): (
            "share",
            {"confirmed": True, "confirmationVersion": "v1", "previewHash": "invalid"},
        ),
        ("/v1/shares/{id}/withdraw", "post"): ("share", None),
    }
    prefixes = (
        "/v1/cases/",
        "/v1/plans/",
        "/v1/evidence/",
        "/v1/trusted-contacts/",
        "/v1/support-drafts/",
        "/v1/shares/",
    )
    discovered = {
        (path, method)
        for path, methods in app.openapi()["paths"].items()
        if path.startswith(prefixes) and "{" in path
        for method in methods
        if method in {"get", "post", "patch", "put", "delete"}
    }
    assert discovered == set(configs), "Every new owner-ID route must join the isolation matrix"
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
        headers={"Authorization": "Bearer synthetic"},
    ) as client:
        for path, method in sorted(discovered):
            kind, body = configs[path, method]
            url = path.format(
                id=ids[kind],
                event_id=ids["event"],
                plan_id=ids["plan"],
                item_id=ids["item"],
                evidenceId=ids["evidence"],
            )
            response = await client.request(method, url, json=body)
            assert response.status_code == 404, (method, path, response.text)
            assert response.json()["error"]["code"] == "not_found"


async def test_staff_download_selected_only_and_audit_scoped(db_engine, identities, school):
    from app.infrastructure.storage_gateway import ObjectInfo

    a, b = identities
    files = Files()
    case = await IncidentService(db_engine).create(a, CaseCreate(id=uuid4()))
    evidence = EvidenceService(db_engine, files)
    selected = await evidence.init_upload(
        a,
        UploadCreate(
            id=uuid4(),
            case_id=case.id,
            filename="selected.pdf",
            mime_type="application/pdf",
            byte_size=8,
        ),
    )
    unselected = await evidence.init_upload(
        a,
        UploadCreate(
            id=uuid4(),
            case_id=case.id,
            filename="unselected.pdf",
            mime_type="application/pdf",
            byte_size=8,
        ),
    )
    for item in (selected, unselected):
        files.objects[item.upload.object_name] = ObjectInfo(8, "application/pdf", "etag")
        await evidence.complete(a, item.evidence.id)
    shares = SharingService(db_engine, files)
    share = await shares.create(
        a,
        ShareCreate(
            id=uuid4(), case_id=case.id, school_id=school[0], evidence_ids=[selected.evidence.id]
        ),
    )
    preview = await shares.preview(a, share.id)
    await shares.submit(
        a,
        share.id,
        ShareSubmit(confirmed=True, confirmation_version="v1", preview_hash=preview.preview_hash),
    )
    assert (
        "download=selected.pdf"
        in (await shares.school_download(b, school[0], share.id, selected.evidence.id)).url
    )
    with pytest.raises(NotFound):
        await shares.school_download(b, school[0], share.id, unselected.evidence.id)
    with pytest.raises(Forbidden):
        await shares.school_get(a, school[0], share.id)
    with pytest.raises(NotFound):
        await evidence.get(b, selected.evidence.id)
    with pytest.raises(ApiError) as missing:
        await IncidentService(db_engine).get_case(b, case.id)
    assert missing.value.status_code == 404
    async with school[1].connect() as conn:
        count = await conn.scalar(
            text(
                "SELECT count(*) FROM app.audit_events WHERE actor_id=:actor AND entity_id=:evidence AND school_id=:school AND metadata->>'purpose'='school_share'"
            ),
            {"actor": b.user_id, "evidence": selected.evidence.id, "school": school[0]},
        )
        assert count == 1
    await shares.withdraw(a, share.id)
    with pytest.raises(NotFound):
        await shares.school_download(b, school[0], share.id, selected.evidence.id)
