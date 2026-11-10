import asyncio
import json
from dataclasses import replace
from uuid import uuid4

import httpx
import pytest
from agents.testing import ModelStep, ScriptedModel, assistant_message, function_call
from agents.usage import Usage
from app.agent_gateway.sse import RunStream, produce
from app.core.auth import get_auth
from app.main import create_app
from app.modules.conversations.service import ConversationService
from moodprint_agent.runtime import CompanionRuntime
from moodprint_shared.config import AppConfig
from moodprint_shared.env import EnvSettings
from moodprint_shared.testing.knowledge_fixture import FixtureKnowledgeRetriever

from backend.tests.integration.conftest import local_value

pytestmark = pytest.mark.integration


def test_settings():
    return EnvSettings(
        app_env="test",
        database_url=local_value("TEST_DATABASE_URL"),
        supabase_url=local_value("SUPABASE_URL"),
        supabase_publishable_key=local_value("SUPABASE_PUBLISHABLE_KEY"),
        supabase_secret_key=local_value("SUPABASE_SECRET_KEY"),
    )


test_settings.__test__ = False


def fixture_config() -> AppConfig:
    """The real lifespan runs here without a Voyage key: choose the fixture on purpose."""
    base = AppConfig()
    return replace(base, knowledge=replace(base.knowledge, retriever="fixture"))


async def test_scripted_sse_persists_transcript_usage_and_private_events(identities):
    app = create_app(test_settings(), cfg=fixture_config())
    app.dependency_overrides[get_auth] = lambda: identities[0]
    model = ScriptedModel(
        [
            ModelStep(
                output=[function_call("get_server_time", {}, call_id="clock")],
                usage=Usage(input_tokens=5, output_tokens=2, total_tokens=7, requests=1),
            ),
            ModelStep(
                output=[assistant_message("Mình đang nghe bạn.")],
                usage=Usage(input_tokens=8, output_tokens=4, total_tokens=12, requests=1),
            ),
        ]
    )
    async with app.router.lifespan_context(app):
        app.state.runtime = CompanionRuntime(AppConfig(), model=model)
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            id = str(uuid4())
            assert (await client.post("/v1/conversations", json={"id": id})).status_code == 200
            client_id = str(uuid4())
            response = await client.post(
                f"/v1/conversations/{id}/messages",
                json={"clientMessageId": client_id, "content": "Chào bạn"},
            )
            assert response.status_code == 200
            events = [
                json.loads(line[6:])
                for line in response.text.splitlines()
                if line.startswith("data: ")
            ]
            assert events[0]["event"] == "run.started"
            assert [e["event"] for e in events][-2:] == ["run.usage", "run.completed"]
            assert [e["seq"] for e in events] == list(range(1, len(events) + 1))
            assert "arguments" not in response.text and "claims_json" not in response.text
            run_id = events[0]["runId"]
            run = (await client.get(f"/v1/runs/{run_id}")).json()
            assert run["usage"]["totalTokens"] == 19
            messages = (await client.get(f"/v1/conversations/{id}/messages")).json()["items"]
            assert [m["content"] for m in messages] == ["Chào bạn", "Mình đang nghe bạn."]
            replay = await client.post(
                f"/v1/conversations/{id}/messages",
                json={"clientMessageId": client_id, "content": "Chào bạn"},
            )
            assert "message.completed" in replay.text
            await client.delete(f"/v1/conversations/{id}")
    model.assert_complete()


async def test_client_disconnect_run_completes_and_persists(db_engine, identities):
    service = ConversationService(db_engine)
    auth = identities[0]
    conversation = await service.create(auth, uuid4())
    turn = await service.begin_turn(auth, conversation["id"], uuid4(), "Xin chào")
    entered, release = asyncio.Event(), asyncio.Event()

    async def delayed(call):
        entered.set()
        await release.wait()
        return [assistant_message("Kết quả vẫn được lưu.")]

    runtime = CompanionRuntime(AppConfig(), model=ScriptedModel([ModelStep.respond(delayed)]))
    stream = RunStream()
    task = asyncio.create_task(
        produce(
            knowledge=FixtureKnowledgeRetriever(),
            stream=stream,
            runtime=runtime,
            service=service,
            auth=auth,
            turn=turn,
            request_id="disconnect-test",
            content="Xin chào",
        )
    )
    await asyncio.wait_for(entered.wait(), 10)
    stream.attached = False
    release.set()
    await asyncio.wait_for(task, 10)
    assert (await service.get_run(auth, turn.run_id))["status"] == "completed"
    assert (await service.recent_messages(auth, conversation["id"], 10))[
        -1
    ].content == "Kết quả vẫn được lưu."
    await service.delete(auth, conversation["id"])


async def test_approved_memory_retrieved_across_conversations_without_copying_to_replay(
    db_engine, identities
):
    from app.modules.memory.service import MemoryService
    from moodprint_shared.contracts.memory import MemoryCreate

    auth = identities[0]
    service = ConversationService(db_engine)
    first = await service.create(auth, uuid4(), "Synthetic source")
    second = await service.create(auth, uuid4(), "Synthetic later conversation")
    memory = MemoryService(db_engine)
    approved = await memory.create(
        auth,
        MemoryCreate(
            category="preference",
            content="Mình thích hướng dẫn từng bước: synthetic-memory-canary",
            source_conversation_id=first["id"],
        ),
    )
    model = ScriptedModel([[assistant_message("Mình sẽ chia thành từng bước.")]])
    runtime = CompanionRuntime(AppConfig(), model=model)
    turn = await service.begin_turn(auth, second["id"], uuid4(), "hướng dẫn từng bước")
    await produce(
        knowledge=FixtureKnowledgeRetriever(),
        stream=RunStream(),
        runtime=runtime,
        service=service,
        auth=auth,
        turn=turn,
        request_id="cross-conversation-memory",
        content="hướng dẫn từng bước",
    )
    assert "synthetic-memory-canary" in model.calls[0].system_instructions
    assert "synthetic-memory-canary" not in json.dumps(
        await (await service.open_session(auth, second["id"])).get_items(), ensure_ascii=False
    )
    await memory.delete(auth, approved.id)
    await service.delete(auth, first["id"])
    await service.delete(auth, second["id"])
