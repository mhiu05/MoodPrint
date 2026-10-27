"""Absolute 7200s authorization: pure predicate, real SQL helper, no refresh, cookie clearing."""

import asyncio
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import select, text

from tests.guest_helpers import add_guest, db_now

LIFETIME = timedelta(seconds=7200)
T0 = datetime(2026, 3, 1, 9, 0, tzinfo=UTC)


def fake_user(kind="guest"):
    guest = kind == "guest"
    return SimpleNamespace(
        account_kind=kind,
        guest_started_at=T0 if guest else None,
        guest_expires_at=T0 + LIFETIME if guest else None,
    )


def test_deadline_boundary():
    from app.modules.guests.policy import lifetime_allows

    guest, deadline = fake_user(), T0 + LIFETIME
    assert lifetime_allows(guest, deadline - timedelta(milliseconds=1)) is True
    assert lifetime_allows(guest, deadline) is False
    assert lifetime_allows(guest, deadline + timedelta(milliseconds=1)) is False
    # Registered accounts keep their own sliding policy; this predicate never ends them.
    assert lifetime_allows(fake_user("registered"), deadline + timedelta(days=400)) is True


def test_registered_and_guest_gates():
    from app.core.errors import DomainError
    from app.modules.guests.policy import require_registered_user

    require_registered_user(fake_user("registered"))
    with pytest.raises(DomainError) as denied:
        require_registered_user(fake_user("guest"))
    assert denied.value.status == 403 and denied.value.code == "REGISTERED_REQUIRED"


@pytest.mark.postgres
async def test_real_sql_helper_flips_at_the_deadline(clients):
    """One short real-time boundary: the helper reads the database clock, never a cached time."""
    app, _ = clients
    guest = await add_guest(app, started_ago=LIFETIME - timedelta(seconds=2))
    helper = text("select moodprint.is_provider_session_active(:sid,:uid)")
    args = {"sid": guest.session_id, "uid": guest.user_id}
    async with app.state.database.sessions() as db:
        assert await db.scalar(helper, args) is True
        assert (await guest.client.get("/api/v1/session")).status_code == 200
    # No cleanup worker exists; denial must come from the predicate alone.
    remaining = (guest.expires_at - await db_now(app)).total_seconds()
    await asyncio.sleep(max(0.0, remaining) + 0.2)
    assert await db_now(app) >= guest.expires_at
    async with app.state.database.sessions() as db:
        assert await db.scalar(helper, args) is False
    response = await guest.client.get("/api/v1/session")
    assert response.status_code == 401 and response.json()["error"]["code"] == "GUEST_EXPIRED"
    cleared = " ".join(response.headers.get_list("set-cookie"))
    assert "moodprint_session=" in cleared and "moodprint_csrf=" in cleared
    assert "Max-Age=0" in cleared or "max-age=0" in cleared.lower()


@pytest.mark.postgres
async def test_provider_helper_checks_current_time_and_kind(clients):
    app, actors = clients
    soon = await add_guest(app, started_ago=LIFETIME - timedelta(seconds=2))
    # Within ONE statement (frozen statement_timestamp) the helper must still see time pass.
    async with app.state.database.sessions() as db:
        row = (
            await db.execute(
                text(
                    "select moodprint.is_provider_session_active(:sid,:uid) as first,"
                    " pg_sleep(2.4) as slept,"
                    " moodprint.is_provider_session_active(:sid,:uid) as second"
                ),
                {"sid": soon.session_id, "uid": soon.user_id},
            )
        ).one()
    assert row.first is True and row.second is False

    guest = await add_guest(app)
    registered_uid = actors[0][1]
    async with app.state.database.sessions.begin() as db:
        reg_session = await db.scalar(
            text("select id from moodprint.auth_sessions where user_id=:u"), {"u": registered_uid}
        )

    async def active(session_id, user_id):
        async with app.state.database.sessions() as db:
            return await db.scalar(
                text("select moodprint.is_provider_session_active(:s,:u)"),
                {"s": session_id, "u": user_id},
            )

    assert await active(guest.session_id, guest.user_id) is True
    assert await active(reg_session, registered_uid) is True

    async def provider_flag(user_id, anonymous):
        async with app.state.database.sessions.begin() as db:
            await db.execute(
                text("update auth.users set is_anonymous=:a where id=:u"),
                {"a": anonymous, "u": user_id},
            )

    # The verified provider classification must agree with the server-owned kind.
    await provider_flag(guest.user_id, False)
    assert await active(guest.session_id, guest.user_id) is False
    await provider_flag(guest.user_id, True)
    await provider_flag(registered_uid, True)
    assert await active(reg_session, registered_uid) is False
    await provider_flag(registered_uid, False)
    assert await active(guest.session_id, guest.user_id) is True
    assert await active(reg_session, registered_uid) is True

    # Missing provider session / revoked app session / version mismatch / ended user all deny.
    async with app.state.database.sessions.begin() as db:
        await db.execute(text("delete from auth.sessions where id=:s"), {"s": guest.provider_session_id})
    assert await active(guest.session_id, guest.user_id) is False
    other = await add_guest(app)
    async with app.state.database.sessions.begin() as db:
        await db.execute(
            text("update moodprint.auth_sessions set revoked=true where id=:s"), {"s": other.session_id}
        )
    assert await active(other.session_id, other.user_id) is False
    third = await add_guest(app)
    async with app.state.database.sessions.begin() as db:
        await db.execute(
            text("update moodprint.users set auth_version=auth_version+1 where id=:u"),
            {"u": third.user_id},
        )
    assert await active(third.session_id, third.user_id) is False
    fourth = await add_guest(app)
    async with app.state.database.sessions.begin() as db:
        await db.execute(
            text("update moodprint.users set status='deleting' where id=:u"), {"u": fourth.user_id}
        )
    assert await active(fourth.session_id, fourth.user_id) is False


@pytest.mark.postgres
async def test_refresh_never_extends_guest(clients):
    from app.infrastructure.database.models import AuthSession, User

    app, _ = clients
    guest = await add_guest(app)

    async def snapshot():
        async with app.state.database.sessions() as db:
            user = await db.scalar(select(User).where(User.id == guest.user_id))
            session = await db.scalar(select(AuthSession).where(AuthSession.user_id == guest.user_id))
            return user.guest_started_at, user.guest_expires_at, session.expires_at

    before = await snapshot()
    for _ in range(3):
        assert (await guest.client.get("/api/v1/session")).status_code == 200
        assert (await guest.client.get("/api/v1/bots")).status_code == 200
    assert await snapshot() == before == (guest.started_at, guest.expires_at, guest.expires_at)


@pytest.mark.postgres
async def test_registered_sliding_unchanged(clients):
    from app.infrastructure.database.models import AuthSession, now

    app, actors = clients
    client, uid = actors[0]
    async with app.state.database.sessions.begin() as db:
        await db.execute(
            text(
                "update moodprint.auth_sessions set expires_at=:e where user_id=:u"
            ),
            {"e": now() + timedelta(minutes=5), "u": uid},
        )
    assert (await client.get("/api/v1/session")).status_code == 200
    async with app.state.database.sessions() as db:
        session = await db.scalar(select(AuthSession).where(AuthSession.user_id == uid))
    assert session.expires_at - now() > timedelta(hours=11)


@pytest.mark.postgres
async def test_missing_clock_or_database_fails_closed(clients, monkeypatch):
    """If the database clock cannot be read the guest is denied, never granted from cached state."""
    from app.modules.guests import policy

    app, _ = clients
    guest = await add_guest(app)

    async def broken(db):
        raise RuntimeError("clock unavailable")

    monkeypatch.setattr(policy, "database_time", broken)
    response = await guest.client.get("/api/v1/session")
    assert response.status_code >= 400
    assert "guestExpiresAt" not in response.text
    assert uuid4() != guest.user_id
