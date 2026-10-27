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
    from app.modules.guests.models import GuestUsage

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
