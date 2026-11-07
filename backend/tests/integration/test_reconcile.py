from uuid import uuid4

import pytest
from app.core.uow import user_uow
from app.jobs.reconcile import reconcile_once
from app.modules.conversations.service import ConversationService
from sqlalchemy import text

pytestmark = pytest.mark.integration


async def test_stale_run_marked_interrupted_and_next_turn_repairs(db_engine, identities):
    auth = identities[0]
    service = ConversationService(db_engine)
    conversation = await service.create(auth, uuid4())
    turn = await service.begin_turn(auth, conversation["id"], uuid4(), "Synthetic")
    session = await service.open_session(auth, conversation["id"])
    await session.add_items(
        [
            {
                "type": "function_call",
                "call_id": "unfinished",
                "name": "get_server_time",
                "arguments": "{}",
            }
        ]
    )
    async with user_uow(db_engine, auth) as uow:
        await uow.session.execute(
            text(
                "UPDATE app.agent_runs SET heartbeat_at=now()-interval '1 hour' WHERE id=:id AND owner_id=:owner"
            ),
            {"id": turn.run_id, "owner": auth.user_id},
        )
    assert await reconcile_once(db_engine) >= 1
    assert (await service.get_run(auth, turn.run_id))["status"] == "interrupted"
    assert await (await service.open_session(auth, conversation["id"])).get_items() == []


async def test_expired_approval_releases_conversation_for_next_turn(db_engine, identities):
    auth = identities[0]
    service = ConversationService(db_engine)
    conversation = await service.create(auth, uuid4())
    turn = await service.begin_turn(auth, conversation["id"], uuid4(), "Synthetic approval")
    approval = uuid4()
    async with user_uow(db_engine, auth) as uow:
        await uow.session.execute(
            text(
                "UPDATE app.agent_runs SET status='awaiting_approval' WHERE id=:id AND owner_id=:owner"
            ),
            {"id": turn.run_id, "owner": auth.user_id},
        )
        await uow.session.execute(
            text(
                "INSERT INTO app.tool_approvals(id,run_id,owner_id,tool_name,tool_call_id,arguments_preview,run_state,expires_at) VALUES(:id,:run,:owner,'synthetic','expired-call','{}','{}',now()-interval '1 minute')"
            ),
            {"id": approval, "run": turn.run_id, "owner": auth.user_id},
        )
    # The function's integer counts stale-heartbeat runs; approval expiry is
    # reconciled separately in the same invocation. Assert the recovery state.
    await reconcile_once(db_engine)
    assert (await service.get_run(auth, turn.run_id))["status"] == "interrupted"
    async with user_uow(db_engine, auth) as uow:
        assert (
            await uow.session.scalar(
                text("SELECT status FROM app.tool_approvals WHERE id=:id AND owner_id=:owner"),
                {"id": approval, "owner": auth.user_id},
            )
            == "expired"
        )
    next_turn = await service.begin_turn(auth, conversation["id"], uuid4(), "Thử lại")
    assert next_turn.run_id != turn.run_id
