"""Real PostgreSQL tests for the mood lifecycle and the self-insight summary.

Breaks caught: client-chosen day boundaries, duplicate same-day rows under
concurrency, replayed writes bumping versions, cross-user reads/deletes,
imputed missing days and out-of-window summary ranges.
"""

import asyncio
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import func, select, update

from app.infrastructure.database.models import Mood, User
from tests.test_social import key

pytestmark = pytest.mark.postgres


def today(zone="Asia/Bangkok") -> date:
    return datetime.now(ZoneInfo(zone)).date()


def body(value=3, note="", expected=0, zone="Asia/Bangkok"):
    return {"value": value, "note": note, "timezone": zone, "expectedVersion": expected}


async def test_mood_create_edit_delete_and_reload(clients):
    _, actors = clients
    client, _ = actors[0]
    path = f"/api/v1/moods/{today()}"
    created = await client.put(path, json=body(4, "  Một ngày yên bình  "), headers=key())
    assert created.status_code == 200, created.text
    assert created.json()["note"] == "Một ngày yên bình"
    assert created.json()["version"] == 1
    edited = await client.put(path, json=body(2, "Mệt", expected=1), headers=key())
    assert edited.status_code == 200, edited.text
    assert (edited.json()["value"], edited.json()["version"]) == (2, 2)
    listed = (await client.get("/api/v1/moods")).json()
    assert [(m["localDate"], m["value"], m["note"]) for m in listed] == [(str(today()), 2, "Mệt")]
    stale = await client.request("DELETE", path, json={"expectedVersion": 1}, headers=key())
    assert stale.status_code == 409
    deleted = await client.request("DELETE", path, json={"expectedVersion": 2}, headers=key())
    assert deleted.status_code == 200, deleted.text
    assert (await client.get("/api/v1/moods")).json() == []
    missing = await client.request("DELETE", path, json={"expectedVersion": 2}, headers=key())
    assert missing.status_code == 404


async def test_mood_replay_is_idempotent_and_conflicting_reuse_is_rejected(clients):
    _, actors = clients
    client, _ = actors[0]
    path, headers = f"/api/v1/moods/{today()}", key()
    first = await client.put(path, json=body(5), headers=headers)
    replay = await client.put(path, json=body(5), headers=headers)
    assert first.status_code == replay.status_code == 200
    assert replay.json()["version"] == first.json()["version"] == 1
    reused = await client.put(path, json=body(1), headers=headers)
    assert reused.status_code == 409
    assert reused.json()["error"]["code"] == "IDEMPOTENCY_CONFLICT"
    delete_headers = key()
    gone = await client.request("DELETE", path, json={"expectedVersion": 1}, headers=delete_headers)
    again = await client.request(
        "DELETE", path, json={"expectedVersion": 1}, headers=delete_headers
    )
    assert gone.status_code == again.status_code == 200
    assert gone.json() == again.json()


async def test_concurrent_same_day_creates_keep_one_row(clients):
    app, actors = clients
    client, owner = actors[0]
    path = f"/api/v1/moods/{today()}"
    responses = await asyncio.gather(
        *[client.put(path, json=body(v), headers=key()) for v in (2, 4)]
    )
    assert sorted(r.status_code for r in responses) == [200, 409]
    async with app.state.database.sessions() as db:
        assert await db.scalar(select(func.count()).where(Mood.user_id == owner)) == 1


async def test_day_boundaries_follow_the_account_timezone_not_the_request(clients):
    app, actors = clients
    client, owner = actors[0]
    async with app.state.database.sessions.begin() as db:
        await db.execute(update(User).where(User.id == owner).values(timezone="Etc/GMT+12"))
    # Kiritimati (UTC+14) is always at least one calendar day ahead of UTC-12.
    ahead = today("Pacific/Kiritimati")
    future = await client.put(
        f"/api/v1/moods/{ahead}", json=body(zone="Pacific/Kiritimati"), headers=key()
    )
    assert future.status_code == 422
    assert future.json()["error"]["code"] == "FUTURE_DATE"
    local = today("Etc/GMT+12")
    for day, status in ((local, 200), (local - timedelta(days=89), 200)):
        response = await client.put(
            f"/api/v1/moods/{day}", json=body(zone="Pacific/Kiritimati"), headers=key()
        )
        assert response.status_code == status, response.text
        assert response.json()["timezone"] == "Etc/GMT+12"
    expired = await client.put(
        f"/api/v1/moods/{local - timedelta(days=90)}", json=body(), headers=key()
    )
    assert expired.json()["error"]["code"] == "DATE_EXPIRED"
    assert len((await client.get("/api/v1/moods")).json()) == 2


async def test_note_is_trimmed_before_length_validation(clients):
    _, actors = clients
    client, _ = actors[0]
    path = f"/api/v1/moods/{today()}"
    padded = await client.put(path, json=body(note="  " + "a" * 120 + "  "), headers=key())
    assert padded.status_code == 200, padded.text
    too_long = await client.put(path, json=body(note="a" * 121, expected=1), headers=key())
    assert too_long.status_code == 422


async def test_moods_are_isolated_between_users(clients):
    _, actors = clients
    (owner, _), (other, _) = actors
    path = f"/api/v1/moods/{today()}"
    assert (await owner.put(path, json=body(4, "riêng tư"), headers=key())).status_code == 200
    assert (await other.get("/api/v1/moods")).json() == []
    assert (await other.get("/api/v1/moods/summary")).json()["count"] == 0
    denied = await other.request("DELETE", path, json={"expectedVersion": 1}, headers=key())
    assert denied.status_code == 404
    overwrite = await other.put(path, json=body(1, expected=1), headers=key())
    assert overwrite.status_code == 409
    assert (await owner.get("/api/v1/moods")).json()[0]["note"] == "riêng tư"


async def test_summary_ranges_keep_missing_days_null(clients):
    app, actors = clients
    client, owner = actors[0]
    now = today()
    async with app.state.database.sessions.begin() as db:
        db.add_all(
            Mood(user_id=owner, local_date=now - timedelta(days=d), value=v, note="", timezone="x")
            for d, v in ((0, 5), (2, 1), (6, 3), (7, 4))
        )
    week = (await client.get("/api/v1/moods/summary", params={"days": 7})).json()
    assert (week["from"], week["to"]) == (str(now - timedelta(days=6)), str(now))
    assert (week["count"], week["min"], week["max"], week["mean"]) == (3, 1, 5, 3.0)
    assert week["insightAvailable"] is True
    assert [b["value"] for b in week["buckets"]] == [3, None, None, None, 1, None, 5]
    assert len(week["buckets"]) == 7
    params = {"from": str(now - timedelta(days=7)), "to": str(now - timedelta(days=6))}
    custom = (await client.get("/api/v1/moods/summary", params=params)).json()
    assert [b["value"] for b in custom["buckets"]] == [4, 3]
    assert custom["insightAvailable"] is False
    empty = (
        await client.get(
            "/api/v1/moods/summary",
            params={"from": str(now - timedelta(days=5)), "to": str(now - timedelta(days=3))},
        )
    ).json()
    assert (empty["count"], empty["mean"], empty["min"]) == (0, None, None)
    for invalid in (
        {"from": str(now)},
        {"from": str(now), "to": str(now - timedelta(days=1))},
        {"from": str(now), "to": str(now + timedelta(days=1))},
        {"from": str(now - timedelta(days=90)), "to": str(now)},
        {"days": 91},
    ):
        response = await client.get("/api/v1/moods/summary", params=invalid)
        assert response.status_code == 422, invalid


async def test_ineligible_or_deleting_accounts_cannot_use_moods(clients):
    app, actors = clients
    (client, owner), (other, other_id) = actors
    async with app.state.database.sessions.begin() as db:
        await db.execute(update(User).where(User.id == owner).values(age_band="under16"))
        await db.execute(update(User).where(User.id == other_id).values(deletion_pending=True))
    assert (await client.get("/api/v1/moods")).status_code == 403
    assert (await client.put(f"/api/v1/moods/{today()}", json=body(), headers=key())).status_code == 403
    pending = await other.put(f"/api/v1/moods/{today()}", json=body(), headers=key())
    assert pending.json()["error"]["code"] == "DELETION_IN_PROGRESS"
