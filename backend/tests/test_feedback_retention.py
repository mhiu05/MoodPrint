"""Feedback retention keeps voluntary ratings while erasing temporary identity links."""

from datetime import timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.infrastructure.database.models import User
from app.modules.feedback.models import AppFeedback, FeedbackReviewEvent, FeedbackSubmissionReceipt
from tests.guest_helpers import add_guest, db_now

pytestmark = pytest.mark.postgres


async def seed(db, uid, created_at, *, kind="registered", receipt_at=None, staff=None):
    row = AppFeedback(
        rating=4, categories=[], account_kind=kind, app_version="test",
        context="general", disclosure_version="feedback-v1", created_at=created_at,
    )
    db.add(row)
    await db.flush()
    db.add(FeedbackSubmissionReceipt(
        user_id=uid, idempotency_key=str(uuid4()), payload_digest="a" * 64,
        feedback_id=row.id, created_at=receipt_at or created_at,
    ))
    if staff:
        db.add(FeedbackReviewEvent(
            feedback_id=row.id, staff_id=staff, action="status", from_status="new",
            to_status="reviewed", resulting_version=2,
        ))
    return row.id


async def test_feedback_retention_exact_cutoff(clients, monkeypatch):
    from app.modules.feedback import retention

    app, actors = clients
    uid, staff = actors[0][1], actors[1][1]
    instant = await db_now(app)

    async def clock(db):
        return instant

    monkeypatch.setattr(retention, "database_time", clock)
    async with app.state.database.sessions.begin() as db:
        old = await seed(db, uid, instant - timedelta(days=180), staff=staff)
        newer = await seed(db, uid, instant - timedelta(days=180) + timedelta(microseconds=1))
    async with app.state.database.sessions.begin() as db:
        assert await retention.purge_feedback(db) == 1
    async with app.state.database.sessions() as db:
        assert await db.get(AppFeedback, old) is None
        assert await db.get(AppFeedback, newer) is not None
        assert not (await db.scalars(select(FeedbackReviewEvent))).all()
        assert not (await db.scalars(select(FeedbackSubmissionReceipt))).all()


async def test_registered_receipts_expire_at_30_days_but_guest_receipts_do_not(clients, monkeypatch):
    from app.modules.feedback import retention

    app, actors = clients
    guest = await add_guest(app)
    instant = await db_now(app)

    async def clock(db):
        return instant

    monkeypatch.setattr(retention, "database_time", clock)
    async with app.state.database.sessions.begin() as db:
        old = await seed(db, actors[0][1], instant, receipt_at=instant - timedelta(days=30))
        recent = await seed(db, actors[0][1], instant, receipt_at=instant - timedelta(days=30) + timedelta(microseconds=1))
        guest_id = await seed(db, guest.user_id, instant, kind="guest", receipt_at=instant - timedelta(days=31))
    async with app.state.database.sessions.begin() as db:
        assert await retention.purge_feedback(db) == 0
    async with app.state.database.sessions() as db:
        assert set((await db.scalars(select(AppFeedback.id))).all()) == {old, recent, guest_id}
        assert set((await db.scalars(select(FeedbackSubmissionReceipt.feedback_id))).all()) == {recent, guest_id}


async def test_retention_is_bounded_and_replay_safe_with_collection_flags_off(clients):
    from app.modules.feedback.retention import purge_feedback

    app, actors = clients
    instant = await db_now(app)
    async with app.state.database.sessions.begin() as db:
        for _ in range(3):
            await seed(db, actors[0][1], instant - timedelta(days=181))
    for expected in (2, 1, 0):
        async with app.state.database.sessions.begin() as db:
            assert await purge_feedback(db, batch_size=2) == expected


async def test_scheduled_retention_runs_even_with_all_feedback_flags_off(clients):
    from app.jobs.retention import purge_expired

    app, actors = clients
    async with app.state.database.sessions.begin() as db:
        fid = await seed(db, actors[0][1], await db_now(app) - timedelta(days=181))
    assert not app.state.settings.feedback_enabled and not app.state.settings.feedback_admin_enabled
    await purge_expired(app)
    async with app.state.database.sessions() as db:
        assert await db.get(AppFeedback, fid) is None


async def test_registered_account_deletion_unlinks_feedback_but_keeps_tombstone(clients):
    from app.modules.users.lifecycle import process_deletions
    from tests.social_helpers import key

    app, actors = clients
    client, uid = actors[0]
    async with app.state.database.sessions.begin() as db:
        fid = await seed(db, uid, await db_now(app))
    version = (await client.get("/api/v1/session")).json()["dataVersion"]
    response = await client.post(
        "/api/v1/data-deletions", json={"scope": "account", "expectedVersion": version}, headers=key(),
    )
    assert response.status_code == 202, response.text
    await process_deletions(app)
    async with app.state.database.sessions() as db:
        assert (await db.get(User, uid)).status == "deleted"
        assert await db.get(AppFeedback, fid) is not None
        assert not (await db.scalars(select(FeedbackSubmissionReceipt).where(FeedbackSubmissionReceipt.user_id == uid))).all()
