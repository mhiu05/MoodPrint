from uuid import uuid4

import pytest
from app.modules.conversations.service import ConversationService
from moodprint_shared.contracts.conversations import RunUsage, TurnResult
from moodprint_shared.contracts.errors import NotFound, RunInProgress
from sqlalchemy.ext.asyncio import create_async_engine

from backend.tests.integration.conftest import local_value

pytestmark = pytest.mark.integration


async def test_session_survives_engine_restart_utf8_and_owner(db_engine, identities):
    a, b = identities
    service = ConversationService(db_engine)
    conversation = await service.create(a, uuid4(), "Tiếng Việt tổng hợp")
    session = await service.open_session(a, conversation["id"])
    await session.add_items([{"role": "user", "content": "Mình muốn nói chuyện với bạn thân"}])
    with pytest.raises(NotFound):
        await service.open_session(b, conversation["id"])
    fresh = create_async_engine(local_value("TEST_DATABASE_URL"))
    try:
        restored = await ConversationService(fresh).open_session(a, conversation["id"])
        assert (await restored.get_items())[0]["content"] == "Mình muốn nói chuyện với bạn thân"
    finally:
        await fresh.dispose()
    assert await service.recent_messages(a, conversation["id"], 10) == []
    await service.delete(a, conversation["id"])


async def test_begin_turn_concurrent_idempotency_and_usage(db_engine, identities):
    a = identities[0]
    service = ConversationService(db_engine)
    conversation = await service.create(a, uuid4(), "Synthetic")
    client_id = uuid4()
    turn = await service.begin_turn(a, conversation["id"], client_id, "Xin chào")
    with pytest.raises(RunInProgress):
        await service.begin_turn(a, conversation["id"], uuid4(), "second")
    message_id = uuid4()
    await service.finish_turn(
        a,
        turn,
        TurnResult(
            status="completed",
            content="Chào bạn",
            message_id=message_id,
            usage=RunUsage(input_tokens=10, output_tokens=5, total_tokens=15, requests=1),
        ),
    )
    replay = await service.begin_turn(a, conversation["id"], client_id, "Xin chào")
    assert replay.replay and replay.run_id == turn.run_id
    assert replay.existing_result.content == "Chào bạn"
    assert [m.content for m in await service.recent_messages(a, conversation["id"], 10)] == [
        "Xin chào",
        "Chào bạn",
    ]
    run = await service.get_run(a, turn.run_id)
    assert run["total_tokens"] == 15
    await service.delete(a, conversation["id"])
