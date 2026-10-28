"""Feedback review requires a live registered admin, independent flags and recent step-up."""

import asyncio
from datetime import timedelta
from uuid import uuid4

import pytest
from sqlalchemy import delete, select, update

from app.core.errors import DomainError
from app.core.security import Actor
from app.infrastructure.database.models import AuthSession, User
from app.modules.feedback.models import AppFeedback, FeedbackReviewEvent
from app.modules.moderation.models import StaffRole
from tests.conftest import add_actor
from tests.guest_helpers import add_guest, db_now

pytestmark = pytest.mark.postgres


async def grant(app, uid, role="admin"):
    async with app.state.database.sessions.begin() as db:
        db.add(StaffRole(user_id=uid, role=role, granted_by="synthetic"))


async def test_feedback_admin_role_and_reauth_matrix(clients):
    app, actors = clients
    app.state.settings.feedback_admin_enabled = True
    app.state.settings.moderation_admin_enabled = False
    guest = await add_guest(app)
    await grant(app, guest.user_id)
    normal = actors[0][0]
    moderator, moderator_id = actors[1]
    await grant(app, moderator_id, "moderator")
    for client in (guest.client, normal, moderator):
        response = await client.get("/api/v1/admin/feedback")
        assert response.status_code == 403, response.text
    admin, uid = await add_actor(app, 9)
    await grant(app, uid)
    response = await admin.get("/api/v1/admin/feedback")
    assert response.status_code == 200, response.text
    assert response.json() == {"items": [], "nextCursor": None}
    async with app.state.database.sessions.begin() as db:
        await db.execute(
            update(AuthSession)
            .where(AuthSession.user_id == uid)
            .values(
                reauthenticated_at=await db_now(app) - timedelta(hours=13),
            )
        )
    stale = await admin.get("/api/v1/admin/feedback")
    assert stale.status_code == 403 and stale.json()["error"]["code"] == "REAUTH_REQUIRED"
    app.state.settings.feedback_admin_enabled = False
    app.state.settings.moderation_admin_enabled = True
    assert (await admin.get("/api/v1/admin/feedback")).status_code == 404


async def test_feedback_flag_independent_and_live_role_rechecked(clients):
    app, actors = clients
    admin, uid = actors[0]
    await grant(app, uid)
    app.state.settings.feedback_admin_enabled = True
    assert (await admin.get("/api/v1/admin/feedback")).status_code == 200
    async with app.state.database.sessions.begin() as db:
        await db.execute(delete(StaffRole).where(StaffRole.user_id == uid))
    assert (await admin.get("/api/v1/admin/feedback")).status_code == 403


async def test_revoked_role_cannot_update_after_wait(clients):
    from app.modules.moderation.staff import assert_feedback_admin

    app, actors = clients
    uid = actors[0][1]
    await grant(app, uid)
    async with app.state.database.sessions() as db:
        session = await db.scalar(select(AuthSession).where(AuthSession.user_id == uid))
        actor = Actor(uid, session.id, 1)
    reached = asyncio.Event()

    async def waiting_review():
        async with app.state.database.sessions.begin() as db:
            reached.set()
            await assert_feedback_admin(db, actor, lock=True)
            # This point must never be reached by a revoked actor after the owner-lock wait.
            db.add(
                AppFeedback(
                    rating=1,
                    app_version="forbidden",
                    account_kind="registered",
                    disclosure_version="feedback-v1",
                )
            )

    async with app.state.database.sessions.begin() as db:
        await db.scalar(select(User).where(User.id == uid).with_for_update())
        pending = asyncio.create_task(waiting_review())
        await reached.wait()
        await db.execute(delete(StaffRole).where(StaffRole.user_id == uid))
    with pytest.raises(DomainError) as caught:
        await asyncio.wait_for(pending, 5)
    assert caught.value.status == 403 and caught.value.code == "STAFF_REQUIRED"
    async with app.state.database.sessions() as db:
        assert not (await db.scalars(select(AppFeedback))).all()
        assert not (await db.scalars(select(FeedbackReviewEvent))).all()


async def test_feedback_admin_denies_ineligible_and_suspended_role_holders(clients):
    app, actors = clients
    app.state.settings.feedback_admin_enabled = True
    admin, uid = actors[0]
    await grant(app, uid)
    async with app.state.database.sessions.begin() as db:
        await db.execute(update(User).where(User.id == uid).values(age_band="unknown"))
    assert (await admin.get("/api/v1/admin/feedback")).status_code == 403
    async with app.state.database.sessions.begin() as db:
        await db.execute(
            update(User)
            .where(User.id == uid)
            .values(
                age_band="adult",
                suspended_until=await db_now(app) + timedelta(hours=1),
            )
        )
    denied = await admin.get("/api/v1/admin/feedback")
    assert denied.status_code == 403 and denied.json()["error"]["code"] == "ACCOUNT_SUSPENDED"


async def admin_setup(clients):
    app, actors = clients
    client, uid = actors[0]
    app.state.settings.feedback_admin_enabled = True
    await grant(app, uid)
    return app, client, uid


async def feedback_row(db, instant, **fields):
    row = AppFeedback(
        rating=fields.pop("rating", 5),
        app_version=fields.pop("app_version", "test-v1"),
        account_kind=fields.pop("account_kind", "guest"),
        disclosure_version="feedback-v1",
        created_at=instant,
        **fields,
    )
    db.add(row)
    await db.flush()
    return row.id


async def test_feedback_filters_share_summary_cohort(clients):
    app, client, _ = await admin_setup(clients)
    instant = await db_now(app)
    async with app.state.database.sessions.begin() as db:
        await feedback_row(
            db,
            instant,
            rating=1,
            categories=["bug", "interface"],
            comment="<script>canary</script>",
        )
        await feedback_row(db, instant, rating=5, categories=["bug"], account_kind="registered")
        await feedback_row(db, instant, rating=3, status="spam", app_version="test-v2")
        await feedback_row(db, instant - timedelta(days=40), rating=2)
    for query, count, mean in (
        ("", 2, 3),
        ("?includeSpam=true", 3, 3),
        ("?status=spam", 1, 3),
        ("?rating=1", 1, 1),
        ("?category=bug", 2, 3),
        ("?category=interface", 1, 1),
        ("?accountKind=registered", 1, 5),
        ("?appVersion=missing", 0, None),
        ("?appVersion=test-v2", 0, None),
        ("?appVersion=test-v2&includeSpam=true", 1, 3),
    ):
        listing = await client.get(f"/api/v1/admin/feedback{query}")
        response = await client.get(f"/api/v1/admin/feedback/summary{query}")
        assert listing.status_code == response.status_code == 200, (listing.text, response.text)
        summary = response.json()
        assert len(listing.json()["items"]) == summary["count"] == count
        assert summary["meanRating"] == mean
        assert sum(summary["ratingCounts"].values()) == count
        assert sum(summary["accountKindCounts"].values()) == count
        assert sum(bucket["count"] for bucket in summary["byDate"]) == count
        assert sum(bucket["count"] for bucket in summary["byVersion"]) == count
        if query == "":
            assert summary["categoryCounts"]["bug"] == 2
            assert sum(summary["categoryCounts"].values()) == 3
            assert "<script>canary</script>" in listing.text
    assert "staffId" not in listing.text and "userId" not in listing.text


async def test_feedback_summary_uses_bangkok_midnight_and_bounded_version_buckets(clients):
    from datetime import UTC, datetime

    app, client, _ = await admin_setup(clients)
    # Bangkok 2026-10-02 starts at 17:00 UTC on the previous day; the next midnight is excluded.
    midnight = datetime(2026, 10, 1, 17, tzinfo=UTC)
    async with app.state.database.sessions.begin() as db:
        await feedback_row(db, midnight - timedelta(microseconds=1), rating=1)
        await feedback_row(db, midnight + timedelta(days=1), rating=1)
        for index in range(52):
            await feedback_row(db, midnight, app_version=f"release-{index}", rating=4)
    query = "?fromDate=2026-10-02&toDate=2026-10-02"
    summary = (await client.get(f"/api/v1/admin/feedback/summary{query}")).json()
    assert summary["count"] == 52 and summary["meanRating"] == 4
    assert summary["byDate"] == [{"date": "2026-10-02", "count": 52, "meanRating": 4}]
    assert len(summary["byVersion"]) == 50
    assert sum(row["count"] for row in summary["byVersion"]) == 52
    assert any(row["appVersion"] == "(other)" and row["count"] == 3 for row in summary["byVersion"])


async def test_feedback_cursor_is_stable_bounded_and_bound_to_filters(clients):
    app, client, _ = await admin_setup(clients)
    instant = await db_now(app)
    async with app.state.database.sessions.begin() as db:
        ids = {str(await feedback_row(db, instant)) for _ in range(5)}
    seen = []
    cursor = None
    while True:
        result = await client.get(
            "/api/v1/admin/feedback", params={"limit": 2, **({"cursor": cursor} if cursor else {})}
        )
        assert result.status_code == 200, result.text
        page = result.json()
        assert len(page["items"]) <= 2
        seen.extend(row["id"] for row in page["items"])
        cursor = page["nextCursor"]
        if cursor is None:
            break
        assert len(cursor) <= 1024
        mismatch = await client.get(
            "/api/v1/admin/feedback", params={"cursor": cursor, "rating": 1}
        )
        assert mismatch.status_code == 422 and mismatch.json()["error"]["code"] == "INVALID_CURSOR"
    assert len(seen) == len(set(seen)) == 5 and set(seen) == ids
    for value in ("!!!!", "e30", "A" * 1025):
        assert (
            await client.get("/api/v1/admin/feedback", params={"cursor": value})
        ).status_code == 422
    for query in (
        "limit=51",
        "limit=0",
        "rating=6",
        "category=unknown",
        "fromDate=bad",
        "toDate=9999-12-31",
        "toDate=0001-01-01",
        "fromDate=2026-10-03&toDate=2026-10-02",
        "fromDate=2025-01-01&toDate=2026-10-02",
    ):
        assert (await client.get(f"/api/v1/admin/feedback?{query}")).status_code == 422
        if not query.startswith("limit"):
            assert (await client.get(f"/api/v1/admin/feedback/summary?{query}")).status_code == 422


async def test_review_conflict_and_idempotency(clients):
    from app.infrastructure.database.models import Idempotency

    app, client, uid = await admin_setup(clients)
    async with app.state.database.sessions.begin() as db:
        fid = await feedback_row(db, await db_now(app), comment="private comment canary")
    path = f"/api/v1/admin/feedback/{fid}"
    body = {"status": "reviewed", "expectedVersion": 1}
    headers = {"Idempotency-Key": "review-once"}
    created = await client.patch(path, json=body, headers=headers)
    assert created.status_code == 200, created.text
    assert created.json()["version"] == 2 and created.json()["status"] == "reviewed"
    replay = await client.patch(path, json=body, headers=headers)
    assert replay.status_code == 200 and replay.json() == created.json()
    conflict = await client.patch(path, json={**body, "status": "resolved"}, headers=headers)
    assert (
        conflict.status_code == 409 and conflict.json()["error"]["code"] == "IDEMPOTENCY_CONFLICT"
    )
    stale = await client.patch(path, json=body, headers={"Idempotency-Key": "stale"})
    assert stale.status_code == 409 and stale.json()["error"]["code"] == "STALE_VERSION"
    noop = await client.patch(
        path, json={**body, "expectedVersion": 2}, headers={"Idempotency-Key": "noop"}
    )
    assert noop.status_code == 200 and noop.json() == created.json()
    async with app.state.database.sessions() as db:
        events = (await db.scalars(select(FeedbackReviewEvent))).all()
        assert len(events) == 1 and events[0].staff_id == uid
        assert (events[0].from_status, events[0].to_status, events[0].resulting_version) == (
            "new",
            "reviewed",
            2,
        )
        receipts = (await db.scalars(select(Idempotency))).all()
        assert len(receipts) == 2
        assert all(set(record.receipt) == {"id", "version"} for record in receipts)
        assert all("private comment" not in str(record.receipt) for record in receipts)
    assert (
        await client.patch(
            path, json=body, headers={"Idempotency-Key": "csrf", "X-CSRF-Token": "forged"}
        )
    ).status_code == 403
    assert (await client.patch(path, json=body)).status_code == 422
    assert (
        await client.patch(
            f"/api/v1/admin/feedback/{uuid4()}", json=body, headers={"Idempotency-Key": "missing"}
        )
    ).status_code == 404


async def test_two_admins_review_same_version_once_and_revoked_actor_cannot_patch(clients):
    app, first, uid = await admin_setup(clients)
    second, other = clients[1][1]
    await grant(app, other)
    async with app.state.database.sessions.begin() as db:
        fid = await feedback_row(db, await db_now(app))
    path = f"/api/v1/admin/feedback/{fid}"
    results = await asyncio.gather(
        *(
            client.patch(
                path,
                json={"status": status, "expectedVersion": 1},
                headers={"Idempotency-Key": status},
            )
            for client, status in ((first, "planned"), (second, "resolved"))
        )
    )
    assert sorted(response.status_code for response in results) == [200, 409]
    async with app.state.database.sessions.begin() as db:
        assert len((await db.scalars(select(FeedbackReviewEvent))).all()) == 1
        await db.execute(delete(StaffRole).where(StaffRole.user_id == uid))
    denied = await first.patch(
        path, json={"status": "spam", "expectedVersion": 2}, headers={"Idempotency-Key": "revoked"}
    )
    assert denied.status_code == 403


async def test_summary_keeps_one_cohort_during_concurrent_review(clients, monkeypatch):
    from sqlalchemy.ext.asyncio import AsyncSession

    app, client, _ = await admin_setup(clients)
    async with app.state.database.sessions.begin() as db:
        fid = await feedback_row(db, await db_now(app), rating=5)
    execute = AsyncSession.execute
    changed = False

    async def interpose(db, statement, *args, **kwargs):
        nonlocal changed
        result = await execute(db, statement, *args, **kwargs)
        sql = str(statement).lower()
        if not changed and "avg(" in sql and "app_feedback" in sql and "group by" not in sql:
            changed = True
            async with app.state.database.sessions.begin() as other:
                await other.execute(
                    update(AppFeedback).where(AppFeedback.id == fid).values(status="spam")
                )
        return result

    monkeypatch.setattr(AsyncSession, "execute", interpose)
    response = await client.get("/api/v1/admin/feedback/summary")
    assert response.status_code == 200, response.text
    summary = response.json()
    assert changed, "the test must change the cohort between aggregate queries"
    assert summary["count"] == sum(summary["ratingCounts"].values()) == 1
    assert summary["meanRating"] == 5
