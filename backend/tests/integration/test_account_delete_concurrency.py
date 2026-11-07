"""Account deletion serializes its snapshot against every user transaction."""

import asyncio
from uuid import uuid4

import pytest
from app.core.errors import ApiError
from app.core.uow import user_uow
from app.infrastructure.storage_gateway import ObjectInfo
from app.modules.conversations.service import ConversationService
from app.modules.evidence.schemas import UploadCreate
from app.modules.evidence.service import EvidenceService
from app.modules.incidents.schemas import CaseCreate
from app.modules.incidents.service import IncidentService
from app.modules.profiles.service import ProfileService
from moodprint_shared.contracts.errors import RunInProgress
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from backend.tests.integration.conftest import local_value
from backend.tests.integration.test_phase1_domains import Files

pytestmark = pytest.mark.integration


class DeleteAuth:
    async def require_live_user(self, auth, token):
        pass

    async def delete_user(self, auth):
        pass


class PausedFiles(Files):
    def __init__(self):
        super().__init__()
        self.entered = asyncio.Event()
        self.release = asyncio.Event()
        self.fail_once = True

    async def delete(self, keys):
        self.entered.set()
        await self.release.wait()
        if self.fail_once:
            self.fail_once = False
            raise ApiError("upstream_error", "Storage unavailable", 502)
        await super().delete(keys)


async def test_deletion_blocks_second_tab_mutations_during_io_and_retry_cleans_sdk(
    db_engine,
    identities,
):
    owner, peer = identities
    profile = ProfileService(db_engine, DeleteAuth())
    await profile.get(owner)
    storage = PausedFiles()
    evidence = EvidenceService(db_engine, storage)
    pending = await evidence.init_upload(
        owner, UploadCreate(id=uuid4(), filename="original.bin", byte_size=8)
    )
    storage.objects[pending.upload.object_name] = ObjectInfo(8, "application/octet-stream", "etag")
    await evidence.complete(owner, pending.evidence.id)
    conversation_id = uuid4()
    conversations = ConversationService(db_engine)
    await conversations.create(owner, conversation_id)
    session = await conversations.open_session(owner, conversation_id)
    await session.add_items([{"role": "user", "content": "Synthetic replay"}])
    task = asyncio.create_task(profile.delete_account(owner, "synthetic", storage))
    try:
        await asyncio.wait_for(storage.entered.wait(), timeout=5)
        for operation in (
            lambda: IncidentService(db_engine).create(owner, CaseCreate(id=uuid4())),
            lambda: conversations.create(owner, uuid4()),
            lambda: conversations.begin_turn(owner, conversation_id, uuid4(), "new run"),
            lambda: conversations.open_session(owner, conversation_id),
            lambda: evidence.init_upload(
                owner, UploadCreate(id=uuid4(), filename="new.bin", byte_size=8)
            ),
        ):
            with pytest.raises(ApiError) as blocked:
                await asyncio.wait_for(operation(), timeout=3)
            assert blocked.value.code == "account_deleting"
            assert blocked.value.status_code == 409
        # The lock is transaction scoped: another owner can still write while Storage waits.
        peer_case = await asyncio.wait_for(
            IncidentService(db_engine).create(peer, CaseCreate(id=uuid4())), timeout=3
        )
        assert peer_case.owner_id == peer.user_id
    finally:
        storage.release.set()
        with pytest.raises(ApiError) as failed:
            await task
        assert failed.value.code == "upstream_error"
    with pytest.raises(ApiError) as persisted:
        await conversations.create(owner, uuid4())
    assert persisted.value.code == "account_deleting"
    await profile.delete_account(owner, "synthetic", storage)
    assert storage.objects == {}
    admin = create_async_engine(local_value("TEST_ADMIN_DATABASE_URL"), hide_parameters=True)
    try:
        async with admin.connect() as conn:
            assert (
                await conn.scalar(
                    text("SELECT count(*) FROM app.evidence_items WHERE owner_id=:owner"),
                    {"owner": owner.user_id},
                )
                == 0
            )
            assert (
                await conn.scalar(
                    text("SELECT count(*) FROM app.conversations WHERE owner_id=:owner"),
                    {"owner": owner.user_id},
                )
                == 0
            )
            assert (
                await conn.scalar(
                    text("SELECT count(*) FROM agent_store.agent_sessions WHERE session_id=:id"),
                    {"id": str(conversation_id)},
                )
                == 0
            )
    finally:
        await admin.dispose()


@pytest.mark.parametrize("status", ["running", "awaiting_approval"])
async def test_active_run_prevents_deletion_before_flag_is_set(db_engine, identities, status):
    owner = identities[0]
    profiles = ProfileService(db_engine, DeleteAuth())
    await profiles.get(owner)
    conversations = ConversationService(db_engine)
    conversation_id = uuid4()
    await conversations.create(owner, conversation_id)
    turn = await conversations.begin_turn(owner, conversation_id, uuid4(), "Synthetic request")
    if status == "awaiting_approval":
        async with user_uow(db_engine, owner) as uow:
            await uow.session.execute(
                text("UPDATE app.agent_runs SET status='awaiting_approval' WHERE id=:id"),
                {"id": turn.run_id},
            )
    with pytest.raises(RunInProgress):
        await profiles.delete_account(owner, "synthetic", Files())
    # Rejection must not strand the account in the deleting state.
    assert (await profiles.get(owner)).user_id == owner.user_id
