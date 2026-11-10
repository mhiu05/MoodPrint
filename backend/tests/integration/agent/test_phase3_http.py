"""I-AG-01…20: Phase 3 HTTP contracts on real PostgreSQL/RLS (only the model and Storage are fakes).

The isolation matrix is derived from the live OpenAPI document: a new owner-ID route that is not
listed below makes ``test_phase3_isolation_matrix`` fail.
"""

import asyncio
import json
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import httpx
import pytest
from agents.testing import ModelStep, ScriptedModel, assistant_message
from agents.usage import Usage
from app.core.auth import get_auth
from app.infrastructure.storage_gateway import ObjectInfo
from app.main import create_app
from app.modules.analysis.store import SqlAnalysisStore
from app.modules.evidence.schemas import NoteCreate, UploadCreate
from app.modules.evidence.service import EvidenceService
from app.modules.incidents.schemas import CaseCreate
from app.modules.incidents.service import IncidentService
from app.modules.memory.service import MemoryService
from app.modules.roleplay.schemas import RoleplayCreate
from app.modules.roleplay.service import RoleplayService
from moodprint_agent.evidence.orchestrator import CONSENT_VERSION
from moodprint_agent.runtime import CompanionRuntime
from moodprint_agent.tools.factory import build_registry
from moodprint_shared.config import AppConfig
from moodprint_shared.contracts.memory import MemoryCandidateCreate, MemoryCreate
from moodprint_shared.testing.knowledge_fixture import FixtureKnowledgeRetriever
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from backend.tests.integration.conftest import local_value
from backend.tests.integration.test_phase1_domains import Files

pytestmark = pytest.mark.integration
CFG = AppConfig()
USAGE = Usage(requests=1, input_tokens=4, output_tokens=4, total_tokens=8)
PREFIXES = (
    "/v1/conversations",
    "/v1/runs",
    "/v1/memories",
    "/v1/memory-candidates",
    "/v1/analyses",
    "/v1/roleplay",
)


class LiveUser:
    async def require_live_user(self, auth, token):
        return None


@pytest.fixture
async def admin():
    engine = create_async_engine(local_value("TEST_ADMIN_DATABASE_URL"), hide_parameters=True)
    try:
        yield engine
    finally:
        await engine.dispose()


def build_app(settings, engine, user, files, model: ScriptedModel | None = None):
    app = create_app(settings)
    app.state.engine, app.state.storage, app.state.auth_admin = engine, files, LiveUser()
    app.state.run_tasks = set()
    # Deterministic harness: the synthetic retriever is chosen on purpose, never by a silent default.
    app.state.knowledge = FixtureKnowledgeRetriever()
    app.state.runtime = CompanionRuntime(CFG, build_registry(CFG), model=model or ScriptedModel([]))
    app.dependency_overrides[get_auth] = lambda: user
    return app


def client_for(app) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
        headers={"Authorization": "Bearer synthetic"},
    )


def reply(model_text: str = "Mình nghe đây.") -> ModelStep:
    return ModelStep(output=[assistant_message(model_text)], usage=USAGE)


async def new_conversation(client: httpx.AsyncClient) -> str:
    created = await client.post("/v1/conversations", json={"id": str(uuid4()), "title": "Thử"})
    assert created.status_code == 200, created.text
    return created.json()["id"]


async def upload_image(engine, files: Files, auth, name="anh.png") -> UUID:
    service = EvidenceService(engine, files, CFG)
    upload = UploadCreate(id=uuid4(), filename=name, mime_type="image/png", byte_size=8)
    pending = await service.init_upload(auth, upload)
    files.objects[pending.upload.object_name] = ObjectInfo(8, "image/png", "etag")
    await service.complete(auth, upload.id)
    return upload.id


async def rows(admin, sql: str, **params: Any):
    async with admin.connect() as conn:
        return (await conn.execute(text(sql), params)).mappings().all()


async def seed_waiting_run(admin, conversation_id: str, owner: UUID, *, minutes: int = 10):
    """A run parked at an approval, with a stored proposal behind it (as the gateway leaves it)."""
    run_id, approval_id, proposal_id = uuid4(), uuid4(), uuid4()
    case_id = uuid4()
    async with admin.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO app.agent_runs(id,conversation_id,owner_id,status,model,prompt_version,"
                "tools_version) VALUES(:r,:c,:o,'awaiting_approval','gpt-6-luna','companion_v2','t')"
            ),
            {"r": run_id, "c": conversation_id, "o": owner},
        )
        await conn.execute(
            text(
                "INSERT INTO app.messages(id,conversation_id,owner_id,role,content,client_message_id,"
                "run_id) VALUES(:m,:c,:o,'user','Lưu giúp mình',:cm,:r)"
            ),
            {"m": uuid4(), "c": conversation_id, "o": owner, "cm": uuid4(), "r": run_id},
        )
        await conn.execute(
            text(
                "INSERT INTO app.cases(id,owner_id,title,template,perspective,summary,status) "
                "VALUES(:id,:o,'Hồ sơ thử','TPL-FREE','self','tóm tắt','active')"
            ),
            {"id": case_id, "o": owner},
        )
        await conn.execute(
            text(
                "INSERT INTO app.agent_proposals(id,owner_id,conversation_id,run_id,kind,"
                "target_case_id,payload,payload_sha256,preview,base_version,request_key,expires_at) "
                "VALUES(:p,:o,:c,:r,'case_event',:case,CAST('{}' AS jsonb),:sha,"
                "CAST(:preview AS jsonb),1,'call-1',now()+interval '30 minutes')"
            ),
            {
                "p": proposal_id,
                "o": owner,
                "c": conversation_id,
                "r": run_id,
                "case": case_id,
                "sha": "0" * 64,
                "preview": json.dumps({"kind": "case_event", "summary": "Thêm mốc thử"}),
            },
        )
        await conn.execute(
            text(
                "INSERT INTO app.tool_approvals(id,run_id,owner_id,tool_name,tool_call_id,"
                "arguments_preview,run_state,expires_at) VALUES(:a,:r,:o,'save_confirmed_event',"
                "'call-1',CAST(:preview AS jsonb),'{}',:exp)"
            ),
            {
                "a": approval_id,
                "r": run_id,
                "o": owner,
                "preview": json.dumps({"summary": "Thêm mốc thử", "proposalId": str(proposal_id)}),
                "exp": datetime.now(UTC) + timedelta(minutes=minutes),
            },
        )
    return run_id, approval_id, proposal_id


async def test_pending_approvals_show_the_stored_preview_to_the_owner_only(
    settings, db_engine, identities, admin
):
    a, b = identities
    files = Files()
    async with client_for(build_app(settings, db_engine, a, files)) as client_a:
        conversation = await new_conversation(client_a)
        run_id, approval_id, _ = await seed_waiting_run(admin, conversation, a.user_id)
        pending = await client_a.get(f"/v1/runs/{run_id}/approvals")
        assert pending.status_code == 200
        [item] = pending.json()["items"]
        assert item["id"] == str(approval_id) and item["tool"] == "save_confirmed_event"
        assert item["preview"]["summary"] == "Thêm mốc thử" and item["status"] == "pending"
        assert "runState" not in item and "run_state" not in item  # the checkpoint never leaves
    async with client_for(build_app(settings, db_engine, b, files)) as client_b:
        assert (await client_b.get(f"/v1/runs/{run_id}/approvals")).status_code == 404

    # An expired approval is not offered again.
    async with admin.begin() as conn:
        await conn.execute(
            text("UPDATE app.tool_approvals SET expires_at=now()-interval '1 minute' WHERE id=:id"),
            {"id": approval_id},
        )
    async with client_for(build_app(settings, db_engine, a, files)) as client_a:
        assert (await client_a.get(f"/v1/runs/{run_id}/approvals")).json()["items"] == []


async def test_cancelling_a_run_that_waits_for_approval_applies_nothing(
    settings, db_engine, identities, admin
):
    a, b = identities
    files = Files()
    async with client_for(build_app(settings, db_engine, a, files)) as client:
        conversation = await new_conversation(client)
        run_id, approval_id, proposal_id = await seed_waiting_run(admin, conversation, a.user_id)
        cancelled = await client.post(f"/v1/runs/{run_id}/cancel")
        assert cancelled.json() == {"status": "cancelled"}
        again = await client.post(f"/v1/runs/{run_id}/cancel")
        assert again.json() == {"status": "cancelled"}  # idempotent
        assert (await client.get(f"/v1/runs/{run_id}/approvals")).json()["items"] == []
        decided = await client.post(
            f"/v1/runs/{run_id}/approvals/{approval_id}", json={"decision": "approve"}
        )
        assert decided.status_code == 409  # a cancelled run can no longer be approved
    proposal = (
        await rows(admin, "SELECT status FROM app.agent_proposals WHERE id=:p", p=proposal_id)
    )[0]
    assert proposal["status"] == "expired"
    events = await rows(
        admin, "SELECT count(*) AS n FROM app.case_events WHERE owner_id=:o", o=a.user_id
    )
    assert events[0]["n"] == 0
    async with client_for(build_app(settings, db_engine, b, files)) as client_b:
        assert (await client_b.post(f"/v1/runs/{run_id}/cancel")).status_code == 404


async def send(client: httpx.AsyncClient, conversation: str, content: str, **extra: Any):
    return await client.post(
        f"/v1/conversations/{conversation}/messages",
        json={"clientMessageId": str(uuid4()), "content": content, **extra},
    )


async def test_attachments_are_validated_stored_listed_and_never_read_into_the_prompt(
    settings, db_engine, identities, admin
):
    a, b = identities
    files = Files()
    mine = await upload_image(db_engine, files, a, "man-hinh-1.png")
    theirs = await upload_image(db_engine, files, b, "cua-nguoi-khac.png")
    note = (
        await EvidenceService(db_engine, files, CFG).create_note(
            a, NoteCreate(id=uuid4(), original_text="Ghi chú")
        )
    ).id
    model = ScriptedModel([reply(), reply()])
    async with client_for(build_app(settings, db_engine, a, files, model)) as client:
        conversation = await new_conversation(client)
        for bad, status in (
            ([str(theirs)], 404),  # someone else's evidence looks like a missing one
            ([str(uuid4())], 404),
            ([str(note)], 422),  # not an image
            ([str(uuid4()) for _ in range(4)], 422),  # more than three
        ):
            response = await send(client, conversation, "Xem giúp mình", attachments=bad)
            assert response.status_code == status, (bad, response.text)
        assert model.calls == ()  # refused before any run exists
        runs = await rows(
            admin,
            "SELECT count(*) AS n FROM app.agent_runs WHERE conversation_id=:c",
            c=conversation,
        )
        assert runs[0]["n"] == 0

        ok = await send(client, conversation, "Xem giúp mình", attachments=[str(mine), str(mine)])
        assert ok.status_code == 200 and "run.completed" in ok.text
        listed = (await client.get(f"/v1/conversations/{conversation}/attachments")).json()["items"]
        assert len(listed) == 1 and listed[0]["evidenceIds"] == [str(mine)]  # de-duplicated
        # The model is told an image exists (id, name) but is given neither bytes nor contents.
        instructions = model.calls[0].system_instructions or ""
        assert str(mine) in instructions and "man-hinh-1.png" in instructions
        assert "analyze_evidence" in instructions and str(theirs) not in instructions
        assert "data:image" not in json.dumps(model.calls[0].input)
    async with client_for(build_app(settings, db_engine, b, files)) as client_b:
        assert (
            await client_b.get(f"/v1/conversations/{conversation}/attachments")
        ).status_code == 404


async def test_phase3_isolation_matrix(settings, db_engine, identities, admin):
    """User B calls every Phase 3 owner-ID route with user A's real IDs: always 404."""
    a, b = identities
    files = Files()
    memory = MemoryService(db_engine, CFG)
    fact = await memory.create(a, MemoryCreate(category="preference", content="Thích đọc truyện"))
    candidate = await memory.propose(
        a,
        MemoryCandidateCreate(
            category="preference", content="Thích vẽ", source_kind="user_explicit"
        ),
    )
    session = await RoleplayService(db_engine, CFG).create(
        a,
        RoleplayCreate(id=uuid4(), role="teacher", scenario_key="teacher-group-chat", difficulty=1),
        age_band=None,
        case_exists=False,
    )
    evidence = await upload_image(db_engine, files, a)
    analysis_id = uuid4()
    store = SqlAnalysisStore(db_engine)
    await store.begin(
        a,
        request_id=analysis_id,
        evidence_id=evidence,
        consent_version=CONSENT_VERSION,
        source_sha256="a" * 64,
        request_sha256="b" * 64,
    )
    async with client_for(build_app(settings, db_engine, a, files)) as owner_client:
        conversation = await new_conversation(owner_client)
    run_id, approval_id, _ = await seed_waiting_run(admin, conversation, a.user_id)
    case = await IncidentService(db_engine).create(a, CaseCreate(id=uuid4(), title="Hồ sơ của A"))

    ids = {
        "id": {
            "/v1/conversations/{id}": conversation,
            "/v1/conversations/{id}/messages": conversation,
            "/v1/conversations/{id}/attachments": conversation,
            "/v1/memories/{id}": str(fact.id),
            "/v1/memory-candidates/{id}/decision": str(candidate.id),
            "/v1/runs/{id}": str(run_id),
            "/v1/runs/{id}/cancel": str(run_id),
            "/v1/runs/{id}/approvals": str(run_id),
            "/v1/runs/{id}/approvals/{approvalId}": str(run_id),
        }
    }
    message = {"clientMessageId": str(uuid4()), "content": "Cho mình vào"}
    configs: dict[tuple[str, str], Any] = {
        ("/v1/conversations/{id}", "get"): None,
        ("/v1/conversations/{id}", "delete"): None,
        ("/v1/conversations/{id}/messages", "get"): None,
        ("/v1/conversations/{id}/messages", "post"): message,
        ("/v1/conversations/{id}/attachments", "get"): None,
        ("/v1/memories/{id}", "patch"): {"content": "Sửa trộm"},
        ("/v1/memories/{id}", "delete"): None,
        ("/v1/memory-candidates/{id}/decision", "post"): {"decision": "approve"},
        ("/v1/runs/{id}", "get"): None,
        ("/v1/runs/{id}/cancel", "post"): None,
        ("/v1/runs/{id}/approvals", "get"): None,
        ("/v1/runs/{id}/approvals/{approvalId}", "post"): {"decision": "approve"},
        ("/v1/analyses/{analysis_id}", "get"): None,
        ("/v1/roleplay/sessions/{session_id}", "get"): None,
        ("/v1/roleplay/sessions/{session_id}/complete", "post"): None,
        ("/v1/roleplay/sessions/{session_id}/abandon", "post"): None,
    }
    app = build_app(settings, db_engine, b, files)
    discovered = {
        (path, method)
        for path, methods in app.openapi()["paths"].items()
        if path.startswith(PREFIXES) and "{" in path
        for method in methods
        if method in {"get", "post", "patch", "put", "delete"}
    }
    assert discovered == set(configs), "Every new owner-ID route must join the isolation matrix"
    values = {
        "id": ids["id"],
        "analysis_id": str(analysis_id),
        "session_id": str(session.id),
    }
    async with client_for(app) as client:
        for path, method in sorted(discovered):
            if "{analysis_id}" in path:
                url = path.format(analysis_id=values["analysis_id"])
            elif "{session_id}" in path:
                url = path.format(session_id=values["session_id"])
            else:
                url = path.format(
                    id=values["id"][path.replace("/{approvalId}", "")]
                    if path in values["id"]
                    else values["id"][path],
                    approvalId=str(approval_id),
                )
            response = await client.request(method, url, json=configs[path, method])
            assert response.status_code == 404, (method, path, response.status_code, response.text)
            assert response.json()["error"]["code"] == "not_found", (method, path)
        # Body-referenced IDs: A's evidence in an analysis, A's case in a roleplay session.
        analysis = await client.post(
            "/v1/analyses",
            json={
                "id": str(uuid4()),
                "evidenceId": str(evidence),
                "consent": {"version": CONSENT_VERSION, "accepted": True},
            },
        )
        assert analysis.status_code in (404, 503), analysis.text  # 503 only if no model client
        roleplay = await client.post(
            "/v1/roleplay/sessions",
            json={
                "id": str(uuid4()),
                "role": "teacher",
                "scenarioKey": "teacher-group-chat",
                "linkedCaseId": str(case.id),
                "useCaseContext": True,
            },
        )
        assert roleplay.status_code == 404, roleplay.text
        assert (await client.get("/v1/roleplay/sessions")).json()["items"] == []
    # Nothing of A's changed.
    assert (await memory.list(a))[0].content == "Thích đọc truyện"
    status = await rows(admin, "SELECT status FROM app.agent_runs WHERE id=:r", r=run_id)
    assert status[0]["status"] == "awaiting_approval"


async def test_twenty_concurrent_conversations_finish_cleanly_and_leak_nothing(
    settings, db_engine, identities, admin
):
    a, _ = identities
    files = Files()
    model = ScriptedModel([reply(f"Trả lời số {n}") for n in range(20)])
    app = build_app(settings, db_engine, a, files, model)
    async with client_for(app) as client:
        conversations = [await new_conversation(client) for _ in range(20)]
        responses = await asyncio.gather(
            *(
                send(client, conversation, f"Xin chào {n}")
                for n, conversation in enumerate(conversations)
            )
        )
        assert all(r.status_code == 200 and "run.completed" in r.text for r in responses)
        answers = sorted(
            row["content"]
            for row in await rows(
                admin,
                "SELECT content FROM app.messages WHERE owner_id=:o AND role='assistant'",
                o=a.user_id,
            )
        )
        assert answers == sorted(f"Trả lời số {n}" for n in range(20))  # each answer exactly once
        runs = await rows(
            admin,
            "SELECT status, count(*) AS n FROM app.agent_runs WHERE owner_id=:o GROUP BY status",
            o=a.user_id,
        )
        assert {r["status"]: r["n"] for r in runs} == {"completed": 20}
    for _ in range(50):  # background run tasks unregister themselves right after the stream ends
        if not app.state.run_tasks:
            break
        await asyncio.sleep(0.05)
    assert not app.state.run_tasks
    assert db_engine.pool.checkedout() == 0  # type: ignore[attr-defined]
