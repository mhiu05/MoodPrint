from uuid import uuid4

import pytest

from tests.social_helpers import key

pytestmark = pytest.mark.postgres


async def test_deletion_denies_old_data_immediately_and_worker_retry_is_idempotent(clients):
    from app.modules.users.lifecycle import process_deletions

    app, actors = clients
    a, _ = actors[0]
    await a.post(
        "/api/v1/profiles/private-items", json={"text": "Private deletion canary"}, headers=key()
    )
    snapshot = (await a.get("/api/v1/session")).json()
    receipt = await a.post(
        "/api/v1/data-deletions",
        json={"scope": "all_private", "expectedVersion": snapshot["dataVersion"]},
        headers=key(),
    )
    assert receipt.status_code == 202, receipt.text
    assert (await a.get("/api/v1/profiles/private-items")).status_code == 409
    await process_deletions(app)
    await process_deletions(app)
    status = await a.get(f"/api/v1/data-deletions/{receipt.json()['id']}")
    assert status.json()["status"] == "completed"
    assert (await a.get("/api/v1/profiles/private-items")).json() == []
    assert (
        await actors[1][0].get(f"/api/v1/data-deletions/{receipt.json()['id']}")
    ).status_code == 404


async def test_export_is_owner_only_current_and_one_use_without_peer_transcripts(clients):
    _, actors = clients
    a, _ = actors[0]
    await a.post("/api/v1/profiles/private-items", json={"text": "Own export"}, headers=key())
    created = await a.post(
        "/api/v1/exports",
        json={"scopes": ["account", "private_items", "memories", "moods"]},
        headers=key(),
    )
    assert created.status_code == 201, created.text
    job = created.json()
    assert (await actors[1][0].get(f"/api/v1/exports/{job['id']}/download")).status_code == 404
    result = await a.get(f"/api/v1/exports/{job['id']}/download")
    assert result.status_code == 200 and result.json()["privateItems"][0]["text"] == "Own export"
    assert "messages" not in result.json()
    assert (await a.get(f"/api/v1/exports/{job['id']}/download")).status_code == 410


async def _auth_rows(app, *uids):
    from sqlalchemy import text

    async with app.state.database.sessions.begin() as db:
        for uid in uids:
            await db.execute(text("insert into auth.users(id) values (:id)"), {"id": uid})


async def _auth_exists(app, uid):
    from sqlalchemy import text

    async with app.state.database.sessions() as db:
        return bool(await db.scalar(text("select count(*) from auth.users where id=:id"), {"id": uid}))


async def test_account_deletion_requires_step_up_and_removes_provider_identity(clients):
    from datetime import timedelta

    from sqlalchemy import func, select, update

    from app.infrastructure.database.models import AiRun, AuthSession, Memory, User, now
    from app.modules.users.lifecycle import process_deletions

    app, actors = clients
    (a, uid), (b, other) = actors
    await _auth_rows(app, uid, other)
    async with app.state.database.sessions.begin() as db:
        db.add(Memory(user_id=uid, bot_id="may", text="Account canary", proposal_id=uid))
        db.add(AiRun(user_id=uid, conversation_id=uid, bot_id="may"))
        await db.execute(
            update(AuthSession)
            .where(AuthSession.user_id == uid)
            .values(reauthenticated_at=now() - timedelta(minutes=10))
        )
    version = (await a.get("/api/v1/session")).json()["dataVersion"]
    body = {"scope": "account", "expectedVersion": version}
    stale = await a.post("/api/v1/data-deletions", json=body, headers=key())
    assert stale.status_code == 401 and stale.json()["error"]["code"] == "REAUTH_REQUIRED"
    async with app.state.database.sessions.begin() as db:
        await db.execute(
            update(AuthSession).where(AuthSession.user_id == uid).values(reauthenticated_at=now())
        )
    receipt = await a.post("/api/v1/data-deletions", json=body, headers=key())
    assert receipt.status_code == 202, receipt.text
    # The deleting account is signed out immediately, before the worker runs.
    assert (await a.get("/api/v1/session")).status_code == 401
    await process_deletions(app)
    async with app.state.database.sessions() as db:
        user = await db.get(User, uid)
        assert (user.status, user.deletion_pending) == ("deleted", False)
        assert await db.scalar(select(func.count()).select_from(Memory).where(Memory.user_id == uid)) == 0
        assert await db.scalar(select(func.count()).select_from(AiRun).where(AiRun.user_id == uid)) == 0
    assert not await _auth_exists(app, uid)
    assert await _auth_exists(app, other)
    assert (await b.get("/api/v1/session")).status_code == 200


async def test_identity_helper_refuses_live_accounts(clients):
    from sqlalchemy import text

    app, actors = clients
    uid = actors[0][1]
    await _auth_rows(app, uid)
    async with app.state.database.sessions.begin() as db:
        removed = await db.scalar(
            text("select moodprint.delete_provider_identity(:id)"), {"id": uid}
        )
    assert removed is False
    assert await _auth_exists(app, uid)


async def test_private_item_deletion_keeps_unrelated_memories(clients):
    from sqlalchemy import select

    from app.infrastructure.database.models import Memory, PrivateItem
    from app.modules.users.lifecycle import process_deletions

    app, actors = clients
    a, uid = actors[0]
    async with app.state.database.sessions.begin() as db:
        item = PrivateItem(user_id=uid, text="Private source")
        db.add(item)
        await db.flush()
        db.add(Memory(user_id=uid, bot_id="may", text="Derived", proposal_id=uuid4(),
                      source_id=item.id, source_version=item.version))
        db.add(Memory(user_id=uid, bot_id="may", text="Unrelated", proposal_id=uuid4()))
    version = (await a.get("/api/v1/session")).json()["dataVersion"]
    receipt = await a.post(
        "/api/v1/data-deletions",
        json={"scope": "private_items", "expectedVersion": version},
        headers=key(),
    )
    assert receipt.status_code == 202, receipt.text
    await process_deletions(app)
    async with app.state.database.sessions() as db:
        texts = (await db.scalars(select(Memory.text).where(Memory.user_id == uid))).all()
    assert texts == ["Unrelated"]


async def test_exhausted_deletion_job_releases_the_user(clients):
    from datetime import timedelta

    from sqlalchemy import update

    from app.infrastructure.database.models import User, now
    from app.modules.users.lifecycle import process_deletions
    from app.modules.users.models import DataJob

    app, actors = clients
    a, uid = actors[0]
    async with app.state.database.sessions.begin() as db:
        job = DataJob(user_id=uid, kind="deletion", scope="moods", status="running",
                      attempts=5, lease_until=now() - timedelta(seconds=1))
        db.add(job)
        await db.execute(update(User).where(User.id == uid).values(deletion_pending=True))
    await process_deletions(app)
    async with app.state.database.sessions() as db:
        assert (await db.get(User, uid)).deletion_pending is False
        assert (await db.get(DataJob, job.id)).status == "failed"
