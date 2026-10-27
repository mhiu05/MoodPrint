"""Owned provisioning intents, key/payload binding and durable creation admission (GE-04.1)."""

import asyncio
from datetime import timedelta
from uuid import uuid4

import pytest
from sqlalchemy import func, select

from tests.guest_helpers import db_now, enable_guest_entry, public_client

pytestmark = pytest.mark.postgres

ORIGIN = "http://127.0.0.1:5173"
INTENT_HEADERS = {"Origin": ORIGIN, "X-Guest-Intent": "1", "Content-Type": "application/json"}


async def attempts(app):
    from app.modules.guests.models import GuestProvisioningAttempt

    async with app.state.database.sessions() as db:
        return (await db.scalars(select(GuestProvisioningAttempt))).all()


async def identities(app):
    from app.infrastructure.database.models import User

    async with app.state.database.sessions() as db:
        return await db.scalar(select(func.count()).select_from(User))


async def claim(app, token, key, digest):
    from app.modules.guests.intents import claim_guest_attempt

    async with app.state.database.sessions.begin() as db:
        return await claim_guest_attempt(db, intent_token=token, key=key, payload_digest=digest)


async def test_intent_requires_origin_custom_header_and_cookie(clients):
    app, _ = clients
    enable_guest_entry(app)
    users_before = await identities(app)
    browser = public_client(app)

    async def post(headers):
        return await browser.post("/api/v1/auth/guest-intents", content=b"{}", headers=headers)

    for headers in (
        {k: v for k, v in INTENT_HEADERS.items() if k != "Origin"},
        {**INTENT_HEADERS, "Origin": "https://evil.example"},
        {k: v for k, v in INTENT_HEADERS.items() if k != "X-Guest-Intent"},
        {**INTENT_HEADERS, "X-Guest-Intent": "0"},
        {**INTENT_HEADERS, "Sec-Fetch-Site": "cross-site"},
    ):
        denied = await post(headers)
        assert denied.status_code == 403, headers
        assert "set-cookie" not in denied.headers
    assert await attempts(app) == [] and await identities(app) == users_before

    created = await post(INTENT_HEADERS)
    assert created.status_code == 204
    cookie = created.headers["set-cookie"]
    assert cookie.startswith("moodprint_guest_intent=")
    for flag in ("HttpOnly", "Path=/api/v1/auth", "SameSite=strict"):
        assert flag.lower() in cookie.lower(), flag
    assert "domain=" not in cookie.lower() and "secure" not in cookie.lower()
    max_age = int(cookie.lower().split("max-age=")[1].split(";")[0])
    assert 590 <= max_age <= 600

    # The same cookie reuses its single unbound intent; only a hash of the token is stored.
    again = await post(INTENT_HEADERS)
    assert again.status_code == 204
    stored = await attempts(app)
    assert len(stored) == 1 and stored[0].state == "intent" and stored[0].idempotency_hash is None
    token = cookie.split("=", 1)[1].split(";")[0]
    assert token not in stored[0].intent_hash and len(stored[0].provider_correlation) == 64
    assert stored[0].provider_correlation not in cookie, "the correlation never reaches a browser"
    window = stored[0].intent_expires_at - stored[0].created_at
    assert timedelta(seconds=599) <= window <= timedelta(seconds=601)
    assert await identities(app) == users_before, "an intent creates no identity"

    app.state.settings.cookie_secure = True
    secure = await public_client(app).post(
        "/api/v1/auth/guest-intents", content=b"{}", headers=INTENT_HEADERS
    )
    assert "secure" in secure.headers["set-cookie"].lower()


async def test_intent_is_unavailable_when_entry_is_off_or_unconfigured(clients):
    app, _ = clients
    browser = public_client(app)
    response = await browser.post(
        "/api/v1/auth/guest-intents", content=b"{}", headers=INTENT_HEADERS
    )
    assert response.status_code == 503 and "set-cookie" not in response.headers
    assert response.json()["error"]["code"] == "GUEST_DISABLED"
    enable_guest_entry(app)
    app.state.settings.guest_captcha_site_key = ""
    response = await browser.post(
        "/api/v1/auth/guest-intents", content=b"{}", headers=INTENT_HEADERS
    )
    assert response.status_code == 503 and "set-cookie" not in response.headers
    assert await attempts(app) == []


async def test_intent_binds_one_key_and_payload(clients):
    from app.core.errors import DomainError
    from app.modules.guests.intents import create_guest_intent_row, hash_token
    from app.modules.guests.models import GuestProvisioningAttempt

    app, _ = clients
    enable_guest_entry(app)
    async with app.state.database.sessions.begin() as db:
        token = await create_guest_intent_row(db)

    # Two independent database sessions racing on one cookie/key/payload bind exactly one attempt.
    first, second = await asyncio.gather(
        claim(app, token, "key-1", "a" * 64), claim(app, token, "key-1", "a" * 64)
    )
    assert first.id == second.id
    rows = await attempts(app)
    assert len(rows) == 1 and rows[0].idempotency_hash and rows[0].payload_digest == "a" * 64

    for key, digest in (("key-2", "a" * 64), ("key-1", "b" * 64)):
        with pytest.raises(DomainError) as conflict:
            await claim(app, token, key, digest)
        assert conflict.value.status == 409 and conflict.value.code == "IDEMPOTENCY_CONFLICT"
    assert len(await attempts(app)) == 1

    # A key alone (no matching cookie) can never recover or bind anything.
    with pytest.raises(DomainError) as unknown:
        await claim(app, "not-a-real-token", "key-1", "a" * 64)
    assert unknown.value.status == 422 and unknown.value.code == "GUEST_INTENT_INVALID"

    async def make(state=None, expired=False):
        async with app.state.database.sessions.begin() as db:
            value = await create_guest_intent_row(db)
            row = await db.scalar(
                select(GuestProvisioningAttempt).where(
                    GuestProvisioningAttempt.intent_hash == hash_token(value)
                )
            )
            if state:
                row.state = state
            if expired:
                row.intent_expires_at = await db_now(app) - timedelta(seconds=1)
        return value

    with pytest.raises(DomainError) as expired:
        await claim(app, await make(expired=True), "key-9", "c" * 64)
    assert expired.value.status == 422 and expired.value.code == "GUEST_INTENT_INVALID"
    with pytest.raises(DomainError) as ended:
        await claim(app, await make(state="rejected"), "key-1", "a" * 64)
    assert ended.value.status == 409 and ended.value.code == "GUEST_INTENT_TERMINAL"


def test_default_admission_limits_match_the_approved_design():
    from app.modules.guests import limits

    assert limits.INTENT_PER_IP == (10, 600)
    assert limits.INTENT_GLOBAL == (100, 60)
    assert limits.CREATION_PER_HOUR == 3 and limits.CREATION_PER_DAY == 10
    assert limits.FAILED_SIGNUP_PER_IP == (10, 600)


async def test_intent_admission_is_durable_and_shared(clients, monkeypatch):
    from app.modules.guests import limits

    app, _ = clients
    enable_guest_entry(app)
    # Ten intents per address per ten minutes; the eleventh is refused before any row exists.
    for _ in range(10):
        response = await public_client(app).post(
            "/api/v1/auth/guest-intents", content=b"{}", headers=INTENT_HEADERS
        )
        assert response.status_code == 204
    refused = await public_client(app).post(
        "/api/v1/auth/guest-intents", content=b"{}", headers=INTENT_HEADERS
    )
    assert refused.status_code == 429 and refused.json()["error"]["code"] == "GUEST_CREATION_LIMIT"
    assert int(refused.headers["retry-after"]) > 0 and "set-cookie" not in refused.headers
    assert len(await attempts(app)) == 10

    # Spoofed forwarding headers neither evade nor change the canonical network key.
    spoofed = await public_client(app).post(
        "/api/v1/auth/guest-intents",
        content=b"{}",
        headers={**INTENT_HEADERS, "X-Forwarded-For": "203.0.113.9", "X-Real-IP": "203.0.113.9"},
    )
    assert spoofed.status_code == 429

    # The global per-minute ceiling is separate from the per-address one.
    monkeypatch.setattr(limits, "INTENT_PER_IP", (1000, 600))
    monkeypatch.setattr(limits, "INTENT_GLOBAL", (10, 60))
    over = await public_client(app).post(
        "/api/v1/auth/guest-intents", content=b"{}", headers=INTENT_HEADERS
    )
    assert over.status_code == 429


async def test_creation_reservation_caps_hour_and_day(clients, monkeypatch):
    from app.core.errors import DomainError
    from app.modules.guests import limits
    from app.modules.guests.models import GuestAbuseBucket

    app, _ = clients
    enable_guest_entry(app)
    request = type("R", (), {"app": app, "client": type("C", (), {"host": "198.51.100.7"})()})()
    for _ in range(3):
        async with app.state.database.sessions.begin() as db:
            await limits.reserve_guest_creation(db, request, uuid4())
    with pytest.raises(DomainError) as hourly:
        async with app.state.database.sessions.begin() as db:
            await limits.reserve_guest_creation(db, request, uuid4())
    assert hourly.value.status == 429 and hourly.value.code == "GUEST_CREATION_LIMIT"
    assert hourly.value.retry_after and hourly.value.retry_after > 0

    # The day cap still holds when the hour cap is lifted (3 used so far, 7 more allowed).
    monkeypatch.setattr(limits, "CREATION_PER_HOUR", 100)
    for _ in range(7):
        async with app.state.database.sessions.begin() as db:
            await limits.reserve_guest_creation(db, request, uuid4())
    with pytest.raises(DomainError) as daily:
        async with app.state.database.sessions.begin() as db:
            await limits.reserve_guest_creation(db, request, uuid4())
    assert daily.value.code == "GUEST_CREATION_LIMIT"
    async with app.state.database.sessions() as db:
        buckets = (await db.scalars(select(GuestAbuseBucket))).all()
    assert {b.scope for b in buckets} >= {"creation_hour", "creation_day"}
    for bucket in buckets:
        assert len(bucket.key_hash) == 64 and "198.51.100.7" not in bucket.key_hash
        assert bucket.expires_at - bucket.window_start <= timedelta(hours=24)


def test_canonical_client_key_is_keyed_normalized_and_scoped():
    from datetime import UTC, datetime

    from pydantic import SecretStr

    from app.core.errors import DomainError
    from app.modules.guests.limits import canonical_client_key

    def request(host, key="k" * 48):
        settings = type("S", (), {"guest_abuse_hmac_key": SecretStr(key)})()
        app = type("A", (), {"state": type("T", (), {"settings": settings})()})()
        return type("R", (), {"app": app, "client": type("C", (), {"host": host})()})()

    window = datetime(2026, 5, 1, 10, tzinfo=UTC)
    plain = canonical_client_key(request("192.0.2.10"), window, "creation_hour")
    assert plain == canonical_client_key(request("::ffff:192.0.2.10"), window, "creation_hour")
    assert plain != canonical_client_key(request("192.0.2.11"), window, "creation_hour")
    assert plain != canonical_client_key(request("192.0.2.10"), window, "creation_day")
    later = canonical_client_key(request("192.0.2.10"), window + timedelta(hours=1), "creation_hour")
    assert plain != later
    assert plain != canonical_client_key(request("192.0.2.10", "z" * 48), window, "creation_hour")
    assert len(plain) == 64 and "192.0.2.10" not in plain
    # An IPv6 client is bucketed by its /64 so rotating host bits cannot dodge a counter.
    assert canonical_client_key(request("2001:db8:1:2::1"), window, "creation_hour") == (
        canonical_client_key(request("2001:db8:1:2:ffff::9"), window, "creation_hour")
    )
    with pytest.raises(DomainError) as unconfigured:
        canonical_client_key(request("192.0.2.10", ""), window, "creation_hour")
    assert unconfigured.value.code == "GUEST_DISABLED"
