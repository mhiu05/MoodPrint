"""HTTP contracts and real PostgreSQL pagination, including ties and owner boundaries."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import httpx
import pytest
from app.core.auth import get_auth
from app.core.uow import user_uow
from app.main import create_app
from app.modules.memory.service import content_hash
from sqlalchemy import text

from backend.tests.integration.conftest import db_engine as db_engine
from backend.tests.integration.conftest import identities as identities

LIST_PATHS = (
    "/v1/conversations",
    "/v1/conversations/{id}/messages",
    "/v1/memories",
    "/v1/memory-candidates",
)


def test_phase0_openapi_declares_typed_responses_and_stream_content(settings):
    schema = create_app(settings).openapi()
    for path, methods in schema["paths"].items():
        if not path.startswith("/v1/"):
            continue
        for method, operation in methods.items():
            if method == "delete":
                assert "204" in operation["responses"]
                continue
            response = operation["responses"]["200"]
            if method == "post" and (path.endswith("/messages") or "/approvals/" in path):
                assert response["content"]["text/event-stream"]["schema"]["type"] == "string"
            else:
                body = response["content"]["application/json"]["schema"]
                assert "$ref" in body or any("$ref" in item for item in body.get("anyOf", [])), (
                    path,
                    method,
                )
    components = schema["components"]["schemas"]
    conversation = components["ConversationRead"]["properties"]
    assert set(conversation) == {
        "id",
        "ownerId",
        "title",
        "linkedCaseId",
        "sourceArticleId",
        "summary",
        "status",
        "lastMessageAt",
        "createdAt",
        "updatedAt",
    }
    assert components["RunRead"]["properties"]["usage"]["$ref"].endswith("/RunUsage")


def test_phase0_openapi_documents_bounded_cursor_pagination(settings):
    schema = create_app(settings).openapi()
    for path in LIST_PATHS:
        parameters = {p["name"]: p["schema"] for p in schema["paths"][path]["get"]["parameters"]}
        assert parameters["limit"]["default"] == 50
        assert parameters["limit"]["minimum"] == 1
        assert parameters["limit"]["maximum"] == 100
        assert "cursor" in parameters


def test_phase0_openapi_documents_bearer_security_and_error_envelope(settings):
    schema = create_app(settings).openapi()
    assert schema["components"]["securitySchemes"]["HTTPBearer"] == {
        "type": "http",
        "scheme": "bearer",
    }
    for path, methods in schema["paths"].items():
        if path.startswith("/v1/"):
            for operation in methods.values():
                assert operation["security"] == [{"HTTPBearer": []}]
                for status in ("401", "404", "422", "500"):
                    body = operation["responses"][status]["content"]["application/json"]["schema"]
                    assert body == {"$ref": "#/components/schemas/ErrorEnvelope"}


async def seed_page_rows(engine, auth, kind, *, count):
    base = datetime(2026, 11, 1, tzinfo=UTC)
    conversation_id = uuid4()
    rows = []
    async with user_uow(engine, auth) as uow:
        if kind == "messages":
            await uow.session.execute(
                text("INSERT INTO app.conversations(id,owner_id) VALUES(:id,:owner)"),
                {"id": conversation_id, "owner": auth.user_id},
            )
        for index in range(count):
            at = base + timedelta(seconds=index // 3)
            id = uuid4()
            params = {
                "id": id,
                "owner": auth.user_id,
                "at": at,
                "content": f"Synthetic row {index}",
            }
            if kind == "conversations":
                # Exercise both timestamp ties and the NULLS LAST cursor transition.
                params["at"] = at if index < count - 11 else None
                sql = "INSERT INTO app.conversations(id,owner_id,title,last_message_at) VALUES(:id,:owner,:content,:at)"
            elif kind == "messages":
                params["conversation"] = conversation_id
                sql = "INSERT INTO app.messages(id,owner_id,conversation_id,role,content,created_at) VALUES(:id,:owner,:conversation,'user',:content,:at)"
            elif kind == "memories":
                params["hash"] = content_hash(params["content"])
                sql = "INSERT INTO app.user_memories(id,owner_id,category,content,content_hash,source_kind,updated_at) VALUES(:id,:owner,'preference',:content,:hash,'user_created',:at)"
            else:
                sql = "INSERT INTO app.memory_candidates(id,owner_id,category,content,source_kind,created_at) VALUES(:id,:owner,'preference',:content,'agent_proposed',:at)"
            await uow.session.execute(text(sql), params)
            rows.append((id, params["at"]))
    if kind == "conversations":
        rows.sort(key=lambda row: (row[1] is None, -row[1].timestamp() if row[1] else 0, row[0]))
    elif kind == "memories":
        rows.sort(key=lambda row: (-row[1].timestamp(), row[0]))
    else:
        rows.sort(key=lambda row: (row[1], row[0]))
    path = (
        f"/v1/conversations/{conversation_id}/messages"
        if kind == "messages"
        else f"/v1/{kind.replace('_', '-')}"
    )
    return path, [str(row[0]) for row in rows]


@pytest.mark.integration
@pytest.mark.parametrize("kind", ["conversations", "messages", "memories", "memory_candidates"])
async def test_http_keyset_pages_cover_all_rows_once_and_reject_foreign_cursors(
    settings, db_engine, identities, kind
):
    a, b = identities
    path, expected = await seed_page_rows(db_engine, a, kind, count=56)
    foreign_path, foreign = await seed_page_rows(db_engine, b, kind, count=14)
    actor = [a]
    app = create_app(settings)
    app.state.engine = db_engine
    app.dependency_overrides[get_auth] = lambda: actor[0]
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        default = await client.get(path)
        assert default.status_code == 200
        assert len(default.json()["items"]) == 50
        assert default.json()["nextCursor"]
        collected, cursor = [], None
        for _ in range(12):
            params = {"limit": 7}
            if cursor:
                params["cursor"] = cursor
            response = await client.get(path, params=params)
            assert response.status_code == 200, response.text
            page = response.json()
            collected.extend(item["id"] for item in page["items"])
            cursor = page["nextCursor"]
            if cursor is None:
                break
        else:
            pytest.fail("Pagination did not terminate")
        assert collected == expected
        assert len(set(collected)) == 56
        assert not set(collected).intersection(foreign)
        all_rows = await client.get(path, params={"limit": 100})
        assert len(all_rows.json()["items"]) == 56
        assert all_rows.json()["nextCursor"] is None
        for params in ({"limit": 101}, {"limit": 0}, {"cursor": "not-a-cursor"}, {"cursor": ""}):
            response = await client.get(path, params=params)
            assert response.status_code == 422
            assert response.json()["error"]["code"] == "validation_failed"
        actor[0] = b
        response = await client.get(foreign_path, params={"limit": 1})
        foreign_cursor = response.json()["nextCursor"]
        assert foreign_cursor
        actor[0] = a
        response = await client.get(path, params={"cursor": foreign_cursor})
        assert response.status_code == 422
        if kind == "messages":
            assert (await client.get(foreign_path)).status_code == 404


@pytest.mark.integration
async def test_cursor_cannot_be_reused_for_another_resource(settings, db_engine, identities):
    auth = identities[0]
    path, _ = await seed_page_rows(db_engine, auth, "conversations", count=14)
    app = create_app(settings)
    app.state.engine = db_engine
    app.dependency_overrides[get_auth] = lambda: auth
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        cursor = (await client.get(path, params={"limit": 1})).json()["nextCursor"]
        response = await client.get("/v1/memories", params={"cursor": cursor})
        assert response.status_code == 422
