from uuid import uuid4

import pytest
from app.modules.conversations.service import ConversationService
from app.modules.incidents.schemas import CaseCreate
from app.modules.incidents.service import IncidentService
from moodprint_shared.contracts.conversations import RunUsage, TurnResult
from moodprint_shared.contracts.errors import NotFound, RunInProgress
from sqlalchemy.ext.asyncio import create_async_engine

from backend.tests.integration.conftest import local_value

pytestmark = pytest.mark.integration


async def test_linked_case_is_persisted_and_rejects_foreign_or_missing_ownership(
    db_engine, identities
):
    a, b = identities
    case = await IncidentService(db_engine).create(
        a, CaseCreate(id=uuid4(), title="Synthetic linked case")
    )
    service = ConversationService(db_engine)
    conversation = await service.create(a, uuid4(), linked_case_id=case.id)
    assert (await service.get(a, conversation["id"]))["linked_case_id"] == case.id
    with pytest.raises(NotFound):
        await service.create(b, uuid4(), linked_case_id=case.id)
    with pytest.raises(NotFound):
        await service.create(a, uuid4(), linked_case_id=uuid4())


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


@pytest.mark.parametrize("terminal", ["failed", "cancelled", "interrupted"])
async def test_retry_of_an_unanswered_terminal_turn_reruns_the_same_message(
    db_engine, identities, terminal
):
    """A retry (same client id, no answer) is a new run on the stored message, not a replay of the
    failure: a replay has no terminal event and could never succeed."""
    a = identities[0]
    service = ConversationService(db_engine)
    conversation = await service.create(a, uuid4(), "Synthetic")
    client_id = uuid4()
    first = await service.begin_turn(a, conversation["id"], client_id, "Mình muốn kể chuyện")
    await service.finish_turn(
        a, first, TurnResult(status=terminal, error_code="internal_error", usage=RunUsage())
    )
    retry = await service.begin_turn(a, conversation["id"], client_id, "Mình muốn kể chuyện")
    assert not retry.replay
    assert retry.run_id != first.run_id and retry.message_id == first.message_id
    # one stored user message, now owned by the new run
    assert [m.content for m in await service.recent_messages(a, conversation["id"], 10)] == [
        "Mình muốn kể chuyện"
    ]
    # while the retry runs, a further retry is refused rather than starting a third run
    with pytest.raises(RunInProgress):
        await service.begin_turn(a, conversation["id"], client_id, "Mình muốn kể chuyện")
    await service.finish_turn(
        a,
        retry,
        TurnResult(
            status="completed", content="Mình nghe đây", message_id=uuid4(), usage=RunUsage()
        ),
    )
    again = await service.begin_turn(a, conversation["id"], client_id, "Mình muốn kể chuyện")
    assert again.replay and again.existing_result.content == "Mình nghe đây"
    assert [m.content for m in await service.recent_messages(a, conversation["id"], 10)] == [
        "Mình muốn kể chuyện",
        "Mình nghe đây",
    ]
    await service.delete(a, conversation["id"])
