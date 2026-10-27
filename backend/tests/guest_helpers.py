"""Synthetic guest seeding shared by the guest test modules (never imported by the application)."""

import hashlib
from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import UUID, uuid4

import httpx
from sqlalchemy import func, select, text

LIFETIME = timedelta(seconds=7200)


@dataclass(frozen=True)
class SeededGuest:
    client: httpx.AsyncClient
    user_id: UUID
    session_id: UUID
    provider_session_id: UUID
    started_at: datetime
    expires_at: datetime


async def db_now(app) -> datetime:
    async with app.state.database.sessions() as db:
        return await db.scalar(select(func.clock_timestamp()))


async def add_guest(
    app,
    *,
    started_ago: timedelta = timedelta(minutes=5),
    age_band: str = "adult",
    usage: dict | None = None,
    consents: bool = False,
) -> SeededGuest:
    """Seed one guest whose deadline is exactly ``start + 7200s`` with a capped opaque session."""
    from app.infrastructure.database.models import AuthSession, Consent, User
    from app.modules.guests.models import GuestCleanupJob, GuestUsage

    uid, sid, provider_sid = uuid4(), uuid4(), uuid4()
    token, csrf = f"guest-session-{uuid4()}", f"csrf-{uuid4()}"
    async with app.state.database.sessions.begin() as db:
        started = await db.scalar(select(func.clock_timestamp())) - started_ago
        expires = started + LIFETIME
        db.add(
            User(
                id=uid,
                auth_subject=uid,
                alias="Khách",
                age_band=age_band,
                account_kind="guest",
                guest_started_at=started,
                guest_expires_at=expires,
            )
        )
        await db.flush()
        db.add(
            AuthSession(
                id=sid,
                user_id=uid,
                token_hash=hashlib.sha256(token.encode()).hexdigest(),
                csrf_hash=hashlib.sha256(csrf.encode()).hexdigest(),
                provider_session_id=provider_sid,
                expires_at=expires,
            )
        )
        for purpose in ("AI", "MEM", "MATCH", "VOICE"):
            db.add(Consent(user_id=uid, purpose=purpose, enabled=consents, version=1))
        db.add(GuestUsage(user_id=uid, **(usage or {})))
        db.add(GuestCleanupJob(user_id=uid, due_at=expires))
        # The verified provider classification of a guest is anonymous; a permanent flag would deny.
        await db.execute(
            text("insert into auth.users(id,is_anonymous) values (:uid,true)"), {"uid": uid}
        )
        await db.execute(
            text("insert into auth.sessions(id,user_id) values (:id,:uid)"),
            {"id": provider_sid, "uid": uid},
        )
    client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")
    client.cookies.set("moodprint_session", token)
    client.headers["X-CSRF-Token"] = csrf
    if hasattr(app.state, "test_clients"):
        app.state.test_clients.append(client)
    return SeededGuest(client, uid, sid, provider_sid, started, expires)


def enable_guest_entry(app) -> None:
    """Turn the default-off guest entry on for one synthetic app (all required config present)."""
    from pydantic import SecretStr

    settings = app.state.settings
    settings.guest_auth_enabled = True
    settings.supabase_url = "https://example-project.supabase.co"
    settings.supabase_publishable_key = SecretStr("publishable-test")
    settings.guest_captcha_site_key = "public-site-key"
    settings.guest_abuse_hmac_key = SecretStr("k" * 48)


def public_client(app, **headers) -> httpx.AsyncClient:
    """A cookie-less browser: no session, no CSRF, only what a first visit sends."""
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test", headers=headers
    )


SUPABASE = "https://example-project.supabase.co"
ORIGIN = "http://127.0.0.1:5173"
INTENT_HEADERS = {"Origin": ORIGIN, "X-Guest-Intent": "1"}
ELIGIBILITY = {
    "birthYear": 2000,
    "confirmedMinimumAge": True,
    "confirmedAdultAge": False,
    "policyVersion": "self-declared-age-v1",
    "expectedVersion": 0,
}


def guest_body(**eligibility) -> dict:
    return {
        "eligibility": {**ELIGIBILITY, **eligibility},
        "captchaToken": "synthetic-captcha-token",
        "disclosureVersion": "guest-v1",
    }


class FakeGuestProvider:
    """Synthetic Supabase Auth for anonymous trials; records every call and can fail on demand.

    ``mode``: ok | timeout (identity created, response lost) | server_error (created, 500) |
    captcha (explicit 400, nothing created).
    """

    def __init__(self, app, mode: str = "ok"):
        self.app, self.mode = app, mode
        self.signups: list[dict] = []
        self.tokens: dict[str, UUID] = {}
        self.created: list[UUID] = []
        app.state.auth_transport = httpx.MockTransport(self.handle)

    def _jwt(self, uid: UUID, sid: UUID) -> str:
        import base64
        import json
        import time

        def part(value):
            return base64.urlsafe_b64encode(json.dumps(value).encode()).rstrip(b"=").decode()

        claims = {
            "sub": str(uid),
            "session_id": str(sid),
            "iss": SUPABASE + "/auth/v1",
            "aud": "authenticated",
            "exp": int(time.time()) + 3600,
            "is_anonymous": True,
        }
        return f"{part({'alg': 'none'})}.{part(claims)}.synthetic"

    async def handle(self, request: httpx.Request) -> httpx.Response:
        import json

        path = request.url.path.removeprefix("/auth/v1")
        if path == "/signup":
            body = json.loads(request.content)
            self.signups.append(body)
            if self.mode == "captcha":
                return httpx.Response(400, json={"error_code": "captcha_failed"})
            uid, sid = uuid4(), uuid4()
            async with self.app.state.database.sessions.begin() as db:
                await db.execute(
                    text(
                        "insert into auth.users(id,is_anonymous,raw_user_meta_data)"
                        " values (:id,true,cast(:meta as jsonb))"
                    ),
                    {"id": uid, "meta": json.dumps(body["data"])},
                )
                await db.execute(
                    text("insert into auth.sessions(id,user_id) values (:s,:u)"),
                    {"s": sid, "u": uid},
                )
            self.created.append(uid)
            token = self._jwt(uid, sid)
            self.tokens[token] = uid
            if self.mode == "timeout":
                raise httpx.ReadTimeout("response lost")
            if self.mode == "server_error":
                return httpx.Response(500, json={"msg": "boom"})
            return httpx.Response(
                200, json={"access_token": token, "refresh_token": "never-stored", "user": {}}
            )
        if path == "/user":
            token = request.headers.get("Authorization", "").removeprefix("Bearer ")
            uid = self.tokens.get(token)
            if uid is None:
                return httpx.Response(401, json={})
            return httpx.Response(200, json={"id": str(uid), "is_anonymous": True})
        return httpx.Response(404, json={})


async def open_intent(browser) -> None:
    created = await browser.post(
        "/api/v1/auth/guest-intents",
        content=b"{}",
        headers={**INTENT_HEADERS, "Content-Type": "application/json"},
    )
    assert created.status_code == 204, created.text


async def post_guest(browser, key: str, body: dict | None = None):
    return await browser.post(
        "/api/v1/auth/guest",
        json=body or guest_body(),
        headers={**INTENT_HEADERS, "Idempotency-Key": key},
    )


PAID_PRICING = {
    "ai": {
        "pricing_version": "synthetic-v1",
        "input_nano_per_token": 2,
        "cached_nano_per_token": 1,
        "output_nano_per_token": 5,
        "max_input_tokens": 100,
    },
    "voice": {"pricing_version": "synthetic-v1", "nano_per_second": 7, "quantum_seconds": 15},
    "embed": {"pricing_version": "synthetic-v1", "nano_per_request": 11},
}


def enable_paid_fixture(app, *, budget: str = "0.01") -> None:
    """Synthetic fixture prices/budget (never an approved production figure) with rates relaxed."""
    from decimal import Decimal

    settings = app.state.settings
    settings.guest_paid_enabled = True
    settings.guest_daily_budget_usd = Decimal(budget)
    settings.guest_pricing_json = PAID_PRICING
    settings.guest_ai_per_minute = settings.guest_voice_per_minute = 1000
