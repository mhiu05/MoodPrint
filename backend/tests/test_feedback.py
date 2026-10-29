"""Feedback submission: rating alone, strict validation, replay, per-owner and network limits, expiry."""

import asyncio
from contextlib import asynccontextmanager
from datetime import timedelta
from uuid import UUID, uuid4

import pytest
from pydantic import SecretStr
from sqlalchemy import text

from tests.conftest import add_actor
from tests.guest_helpers import add_guest, db_now

pytestmark = pytest.mark.postgres

LIFETIME = timedelta(seconds=7200)
RELEASE = "2026.10.28+test"


def enable(app) -> None:
    settings = app.state.settings
    settings.feedback_enabled = True
    settings.guest_abuse_hmac_key = SecretStr("k" * 48)
    settings.release_version = RELEASE


def payload(**fields):
    return {"rating": 5, "disclosureVersion": "feedback-v1", **fields}


async def submit(client, body=None, key=None, **kwargs):
    return await client.post(
        "/api/v1/feedback",
        json=body if body is not None else payload(),
        headers={"Idempotency-Key": key or str(uuid4())},
        **kwargs,
    )


async def stored(app):
    async with app.state.database.sessions() as db:
        feedback = await db.scalar(text("select count(*) from moodprint.app_feedback"))
        receipts = await db.scalar(
            text("select count(*) from moodprint.feedback_submission_receipts")
        )
    return feedback, receipts


async def accepted_counter(app) -> int:
    async with app.state.database.sessions() as db:
        return (
            await db.scalar(
                text(
                    "select coalesce(sum(count),0) from moodprint.guest_abuse_buckets"
                    " where scope='feedback'"
                )
            )
            or 0
        )


async def next_minute(app) -> None:
    """Forget the per-identity attempt windows, as if a fresh UTC minute had started."""
    async with app.state.database.sessions.begin() as db:
        await db.execute(
            text("delete from moodprint.guest_abuse_buckets where scope='feedback_attempt'")
        )


async def test_rating_only_guest_and_registered(clients):
    app, actors = clients
    enable(app)
    guest = await add_guest(app)
    registered, _ = actors[0]

    first = await submit(guest.client)
    assert first.status_code == 201, first.text
    receipt = first.json()
    assert set(receipt) == {"feedbackId", "createdAt", "status"} and receipt["status"] == "received"
    UUID(receipt["feedbackId"])

    second = await submit(registered, payload(rating=2, categories=["bug", "ease_of_use"]))
    assert second.status_code == 201, second.text

    async with app.state.database.sessions() as db:
        rows = (
            await db.execute(
                text(
                    "select rating, categories, comment, context, account_kind, app_version,"
                    " disclosure_version, status, version from moodprint.app_feedback"
                    " order by rating desc"
                )
            )
        ).all()
    assert tuple(rows[0]) == (5, [], None, "general", "guest", RELEASE, "feedback-v1", "new", 1)
    # Stored in the documented category order whatever the client sent.
    assert rows[1].categories == ["ease_of_use", "bug"] and rows[1].account_kind == "registered"


@pytest.mark.parametrize(
    "fields",
    [
        {"rating": True},
        {"rating": "5"},
        {"rating": 1.5},
        {"rating": 0},
        {"rating": 6},
        {"categories": ["bug", "bug"]},
        {"categories": ["unknown"]},
        {"comment": "x" * 1001},
        {"comment": "😀" * 1001},
        {"comment": "a\x01b"},
        {"comment": "a\u0085b"},
        {"userId": str(uuid4())},
        {"url": "https://example.test/#/private"},
        {"appVersion": "9.9"},
        {"conversationId": str(uuid4())},
        {"screenshot": "data:image/png;base64,AAAA"},
        {"context": "https://example.test"},
        {"disclosureVersion": "feedback-v2"},
    ],
    ids=lambda fields: ",".join(f"{k}={str(v)[:14]!r}" for k, v in fields.items()),
)
async def test_invalid_bodies_are_rejected_without_a_trace(clients, fields):
    app, actors = clients
    enable(app)
    response = await submit(actors[0][0], payload(**fields))
    assert response.status_code == 422, response.text
    assert await stored(app) == (0, 0)
    # A refused body must not echo the submitted text or leak SQL/driver detail.
    assert "Traceback" not in response.text and "psycopg" not in response.text.lower()


async def test_boundary_and_markup_comments_are_stored_as_text(clients):
    app, actors = clients
    enable(app)
    hostile = "<script>alert(1)</script> ' OR 1=1; -- [x](javascript:alert(1)) {{7*7}}"
    for fields in ({"comment": "😀" * 1000}, {"comment": hostile}, {"comment": "   \n "}):
        client, _ = await add_actor(app, 20 + len(fields["comment"]) % 7)
        response = await submit(client, payload(**fields))
        assert response.status_code == 201, response.text
    async with app.state.database.sessions() as db:
        comments = set((await db.scalars(text("select comment from moodprint.app_feedback"))).all())
    assert comments == {"😀" * 1000, hostile, None}


async def test_endpoint_is_absent_while_the_flag_is_off(clients):
    app, actors = clients
    client = actors[0][0]
    assert (await submit(client)).status_code == 404
    assert (await client.get("/api/v1/feedback/submission-state")).status_code == 404
    assert await stored(app) == (0, 0)


async def test_authentication_csrf_and_key_are_required(clients):
    import httpx

    app, actors = clients
    enable(app)
    anonymous = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")
    try:
        assert (await submit(anonymous)).status_code == 401
    finally:
        await anonymous.aclose()
    client = actors[0][0]
    no_csrf = await client.post(
        "/api/v1/feedback",
        json=payload(),
        headers={"Idempotency-Key": "k-1", "X-CSRF-Token": "wrong"},
    )
    assert no_csrf.status_code == 403 and no_csrf.json()["error"]["code"] == "CSRF_DENIED"
    missing_key = await client.post("/api/v1/feedback", json=payload())
    assert missing_key.status_code == 422
    assert missing_key.json()["error"]["code"] == "IDEMPOTENCY_REQUIRED"
    assert await stored(app) == (0, 0)


async def test_replay_conflict_and_one_per_guest_lifecycle(clients):
    app, _ = clients
    enable(app)
    guest = await add_guest(app)
    created = await submit(guest.client, key="same-key")
    assert created.status_code == 201

    replay = await submit(guest.client, key="same-key")
    assert replay.status_code == 200 and replay.json() == created.json()

    changed = await submit(guest.client, payload(rating=1), key="same-key")
    assert changed.status_code == 409
    assert changed.json()["error"]["code"] == "IDEMPOTENCY_CONFLICT"

    await next_minute(app)  # three attempts per identity per minute is a separate rule
    again = await submit(guest.client, key="a-new-key")
    assert again.status_code == 409
    assert again.json()["error"]["code"] == "FEEDBACK_ALREADY_SUBMITTED"
    assert await stored(app) == (1, 1)
    assert await accepted_counter(app) == 1, "a replay or refusal never charges the accepted counter"


async def test_registered_users_get_one_per_bangkok_day_with_retry_after(clients):
    app, actors = clients
    enable(app)
    client, uid = actors[0]
    assert (await submit(client)).status_code == 201
    limited = await submit(client)
    assert limited.status_code == 429
    assert limited.json()["error"]["code"] == "FEEDBACK_DAILY_LIMIT"
    assert 1 <= int(limited.headers["Retry-After"]) <= 86_400

    # Yesterday's (Bangkok) receipt no longer counts: move it back a day and send again.
    async with app.state.database.sessions.begin() as db:
        await db.execute(
            text(
                "update moodprint.feedback_submission_receipts"
                " set created_at = created_at - interval '1 day' where user_id=:u"
            ),
            {"u": uid},
        )
        # Fresh attempt window so only the daily rule is being exercised.
        await db.execute(text("delete from moodprint.guest_abuse_buckets"))
    assert (await submit(client)).status_code == 201
    assert (await stored(app))[0] == 2


async def test_submission_state_reports_only_the_owners_receipt(clients):
    app, actors = clients
    enable(app)
    guest = await add_guest(app)
    client, registered_id = actors[0]
    for who in (guest.client, client):
        empty = await who.get("/api/v1/feedback/submission-state")
        assert empty.status_code == 200
        assert empty.json() == {"submitted": False, "lastSubmittedAt": None}
    await submit(guest.client)
    state = (await guest.client.get("/api/v1/feedback/submission-state")).json()
    assert state["submitted"] is True and state["lastSubmittedAt"]
    assert set(state) == {"submitted", "lastSubmittedAt"}, "no content and no review status"
    other = (await client.get("/api/v1/feedback/submission-state")).json()
    assert other == {"submitted": False, "lastSubmittedAt": None}

    # A registered receipt counts for 30 days only; a guest's receipt lives as long as the trial.
    await submit(client)
    assert (await client.get("/api/v1/feedback/submission-state")).json()["submitted"] is True
    async with app.state.database.sessions.begin() as db:
        await db.execute(
            text(
                "update moodprint.feedback_submission_receipts"
                " set created_at = created_at - interval '31 days' where user_id = :u"
            ),
            {"u": registered_id},
        )
    assert (await client.get("/api/v1/feedback/submission-state")).json() == {
        "submitted": False,
        "lastSubmittedAt": None,
    }
    assert (await guest.client.get("/api/v1/feedback/submission-state")).json()["submitted"] is True


async def test_attempts_are_limited_per_identity_per_minute(clients):
    app, actors = clients
    enable(app)
    client = actors[0][0]
    created = await submit(client, key="k-1")
    assert created.status_code == 201
    assert (await submit(client, key="k-1")).status_code == 200
    assert (await submit(client, key="k-1")).status_code == 200
    blocked = await submit(client, key="k-1")
    assert blocked.status_code == 429 and "Retry-After" in blocked.headers
    assert blocked.json()["error"]["code"] == "FEEDBACK_RATE_LIMITED"
    # Another identity on the same network is not affected by this one's attempts.
    other = await submit(actors[1][0])
    assert other.status_code == 201


async def test_network_limit_counts_accepted_submissions_only(clients):
    app, actors = clients
    enable(app)
    sent = 0
    for index in range(2, 22):
        client, _ = await add_actor(app, index)
        response = await submit(client)
        assert response.status_code == 201, (index, response.text)
        sent += 1
    assert sent == 20 and await accepted_counter(app) == 20
    client, _ = await add_actor(app, 30)
    over = await submit(client)
    assert over.status_code == 429 and "Retry-After" in over.headers
    assert over.json()["error"]["code"] == "FEEDBACK_RATE_LIMITED"
    assert await stored(app) == (20, 20)
    assert await accepted_counter(app) == 20, "the refused 21st submission was not counted"


async def test_concurrent_feedback_replay_and_expiry(clients, monkeypatch):
    app, _ = clients
    enable(app)
    guest = await add_guest(app)

    # Three simultaneous requests with one key: exactly one row, one receipt, all report it.
    results = await asyncio.gather(*(submit(guest.client, key="race") for _ in range(3)))
    assert sorted(response.status_code for response in results) == [200, 200, 201]
    assert len({response.json()["feedbackId"] for response in results}) == 1
    assert await stored(app) == (1, 1)

    # A submission whose transaction only finishes after T rolls back feedback, receipt and counter.
    from app.modules.feedback import routes

    late = await add_guest(app, started_ago=LIFETIME - timedelta(seconds=3))
    counter = await accepted_counter(app)
    from app.core import security

    real = security.transaction
    reached_end, release = asyncio.Event(), asyncio.Event()

    @asynccontextmanager
    async def slow(request, actor, **kwargs):
        async with real(request, actor, **kwargs) as (db, user):
            yield db, user
            reached_end.set()
            await release.wait()

    monkeypatch.setattr(routes, "transaction", slow)
    pending = asyncio.create_task(submit(late.client, key="too-late"))
    await asyncio.wait_for(reached_end.wait(), 5)
    await asyncio.sleep(max(0.0, (late.expires_at - await db_now(app)).total_seconds()) + 0.3)
    release.set()
    response = await asyncio.wait_for(pending, 5)
    assert response.status_code == 401 and response.json()["error"]["code"] == "GUEST_EXPIRED"
    assert await stored(app) == (1, 1), "nothing from the late submission was kept"
    assert await accepted_counter(app) == counter, "the accepted counter rolled back with it"


async def test_a_trial_that_ended_cannot_submit(clients):
    app, _ = clients
    enable(app)
    ended = await add_guest(app, started_ago=LIFETIME + timedelta(seconds=1))
    response = await submit(ended.client)
    assert response.status_code == 401 and response.json()["error"]["code"] == "GUEST_EXPIRED"
    assert await stored(app) == (0, 0)


async def test_unexpected_storage_failure_is_sanitized_and_leaves_nothing(clients, monkeypatch):
    from app.modules.feedback import routes

    app, actors = clients
    enable(app)

    async def broken(*args, **kwargs):
        raise RuntimeError("password=hunter2 host=db.internal")

    monkeypatch.setattr(routes, "submit_feedback", broken)
    response = await submit(actors[0][0])
    assert response.status_code == 500
    assert "hunter2" not in response.text and "db.internal" not in response.text
    assert await stored(app) == (0, 0)


async def test_temporary_storage_failure_is_retryable_and_sanitized(clients, monkeypatch):
    from sqlalchemy.exc import OperationalError

    from app.modules.feedback import routes

    app, actors = clients
    enable(app)

    async def unavailable(*args, **kwargs):
        raise OperationalError("private SQL", {}, Exception("private database detail"))

    monkeypatch.setattr(routes, "submit_feedback", unavailable)
    response = await submit(actors[0][0])
    assert response.status_code == 503
    assert response.json()["error"]["retryable"] is True
    assert "private" not in response.text
    assert await stored(app) == (0, 0)


async def test_no_identity_is_copied_into_the_feedback_row(clients):
    app, actors = clients
    enable(app)
    guest = await add_guest(app)
    await submit(guest.client, payload(comment="Dễ dùng", categories=["interface"]))
    async with app.state.database.sessions() as db:
        row = (
            await db.execute(text("select * from moodprint.app_feedback limit 1"))
        ).mappings().one()
        owner = await db.scalar(
            text("select user_id from moodprint.feedback_submission_receipts limit 1")
        )
    assert owner == guest.user_id
    flat = " ".join(str(value) for value in row.values())
    assert str(guest.user_id) not in flat and str(guest.session_id) not in flat
