"""Atomic guest grant, lost-response recovery, ambiguous/failed provisioning (GE-04.2)."""

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import func, select, text

from tests.guest_helpers import (
    FakeGuestProvider,
    db_now,
    enable_guest_entry,
    guest_body,
    open_intent,
    post_guest,
    public_client,
)

pytestmark = pytest.mark.postgres


async def trial(app, provider=None, key=None, body=None):
    """One browser: intent cookie, then the explicit guest request."""
    browser = public_client(app)
    await open_intent(browser)
    return browser, await post_guest(browser, key or str(uuid4()), body)


async def only_attempt(app):
    from app.modules.guests.models import GuestProvisioningAttempt

    async with app.state.database.sessions() as db:
        return (await db.scalars(select(GuestProvisioningAttempt))).one()


async def count(app, model):
    async with app.state.database.sessions() as db:
        return await db.scalar(select(func.count()).select_from(model))


async def setup(clients, mode="ok"):
    app, actors = clients
    enable_guest_entry(app)
    return app, actors, FakeGuestProvider(app, mode)


async def test_guest_grant_has_one_database_deadline(clients):
    from app.infrastructure.database.models import AgeDeclaration, AuthSession, Consent, User
    from app.modules.guests.models import GuestCleanupJob, GuestUsage

    app, _, provider = await setup(clients)
    before = await db_now(app)
    browser, response = await trial(app)
    after = await db_now(app)
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["accountKind"] == "guest" and body["features"]["matching"] is False

    attempt = await only_attempt(app)
    async with app.state.database.sessions() as db:
        user = await db.get(User, attempt.user_id)
        sessions = (await db.scalars(select(AuthSession).where(AuthSession.user_id == user.id))).all()
        consents = (await db.scalars(select(Consent).where(Consent.user_id == user.id))).all()
        declaration = await db.get(AgeDeclaration, user.id)
        job = await db.get(GuestCleanupJob, user.id)
        usage = await db.get(GuestUsage, user.id)
    # One database deadline: exactly 7200s after a clock sampled inside the grant.
    assert user.guest_expires_at - user.guest_started_at == timedelta(seconds=7200)
    assert before <= user.guest_started_at <= after
    assert datetime.fromisoformat(body["guestExpiresAt"]) == user.guest_expires_at
    assert user.auth_subject != user.id and user.auth_subject == attempt.provider_subject
    assert [s.expires_at for s in sessions] == [user.guest_expires_at]
    assert sessions[0].reauthenticated_at == datetime(1970, 1, 1, tzinfo=UTC)
    assert len(consents) == 4
    assert {c.purpose for c in consents if c.enabled} == {"AI", "MEM", "VOICE"}
    assert not any(c.enabled for c in consents if c.purpose == "MATCH")
    assert declaration.birth_year == 2000 and user.age_band in ("teen", "adult")
    assert job.due_at == user.guest_expires_at and job.state == "pending"
    assert (usage.ai_turns, usage.voice_clips, usage.voice_milliseconds) == (0, 0, 0)
    assert attempt.state == "granted" and attempt.lease_token is None
    assert attempt.provider_session_id == sessions[0].provider_session_id

    # One signup, carrying the server-owned correlation and the one-shot CAPTCHA only.
    assert len(provider.signups) == 1
    assert provider.signups[0]["data"] == {"moodprint_guest_attempt": attempt.provider_correlation}
    assert "email" not in provider.signups[0] and "password" not in provider.signups[0]
    cookies = " ".join(response.headers.get_list("set-cookie"))
    assert "moodprint_session=" in cookies and "moodprint_csrf=" in cookies
    session_cookie = [c for c in response.headers.get_list("set-cookie") if c.startswith("moodprint_session")][0]
    assert "httponly" in session_cookie.lower() and "samesite=strict" in session_cookie.lower()
    max_age = int(session_cookie.lower().split("max-age=")[1].split(";")[0])
    assert 7190 <= max_age <= 7200
    csrf_cookie = [c for c in response.headers.get_list("set-cookie") if c.startswith("moodprint_csrf")][0]
    assert "httponly" not in csrf_cookie.lower()

    # Provider credentials are used once: no access token, refresh token or correlation in storage.
    token = next(iter(provider.tokens))
    async with app.state.database.sessions() as db:
        tables = (await db.scalars(text("select tablename from pg_tables where schemaname='moodprint'"))).all()
        for table in tables:
            for needle in (token, "never-stored"):
                hits = await db.scalar(
                    text(f"select count(*) from moodprint.{table} t where t::text like :n"),
                    {"n": f"%{needle}%"},
                )
                assert hits == 0, f"{table} stores a provider credential"

    # The new browser is authenticated and a second trial is an independent identity.
    assert (await browser.get("/api/v1/session")).json()["userId"] == str(user.id)
    second_browser, second = await trial(app)
    assert second.status_code == 201 and second.json()["userId"] != str(user.id)


async def test_lost_grant_response_recovers_same_user_and_deadline(clients):
    app, _, provider = await setup(clients)
    first = public_client(app)
    await open_intent(first)
    key = str(uuid4())
    granted = await post_guest(first, key)
    assert granted.status_code == 201
    old_cookie = first.cookies.get("moodprint_session")
    original = granted.json()

    # The response was lost: another browser context holding only the intent cookie retries.
    retry = public_client(app)
    retry.cookies.set(
        "moodprint_guest_intent", first.cookies.get("moodprint_guest_intent", path="/api/v1/auth"),
        path="/api/v1/auth",
    )
    recovered = await post_guest(retry, key)
    assert recovered.status_code == 200, recovered.text
    assert recovered.json()["userId"] == original["userId"]
    assert recovered.json()["guestExpiresAt"] == original["guestExpiresAt"]
    assert len(provider.signups) == 1, "recovery must never send another signup"
    new_cookie = retry.cookies.get("moodprint_session")
    assert new_cookie and new_cookie != old_cookie
    assert (await retry.get("/api/v1/session")).status_code == 200
    # The superseded credential is revoked; the lifecycle (one user, one deadline) is unchanged.
    stale = public_client(app)
    stale.cookies.set("moodprint_session", old_cookie)
    assert (await stale.get("/api/v1/session")).status_code == 401
    from app.infrastructure.database.models import User

    assert await count(app, User) == 3  # two seeded registered actors + exactly one guest


async def test_concurrent_recoveries_leave_one_valid_credential(clients):
    from app.infrastructure.database.models import AuthSession

    app, _, _ = await setup(clients)
    first = public_client(app)
    await open_intent(first)
    key = str(uuid4())
    assert (await post_guest(first, key)).status_code == 201
    intent = first.cookies.get("moodprint_guest_intent", path="/api/v1/auth")

    async def recover():
        browser = public_client(app)
        browser.cookies.set("moodprint_guest_intent", intent, path="/api/v1/auth")
        return await post_guest(browser, key)

    results = await asyncio.gather(recover(), recover())
    # Recoveries serialize: each is either served or, when a concurrent one superseded its
    # credential before it could be used, told to retry. None is a stale 401 or a second signup.
    assert sorted(r.status_code for r in results) in ([200, 200], [200, 409])
    for result in results:
        if result.status_code == 409:
            assert result.json()["error"]["code"] == "GUEST_ATTEMPT_PENDING"
    async with app.state.database.sessions() as db:
        live = (
            await db.scalars(select(AuthSession).where(AuthSession.revoked.is_(False)).where(
                AuthSession.user_id == (await only_attempt(app)).user_id))
        ).all()
    assert len(live) == 1, "only the latest valid credential remains"


async def test_ambiguous_signup_never_retries_upstream(clients):
    from app.infrastructure.database.models import User

    app, _, provider = await setup(clients, mode="timeout")
    users_before = await count(app, User)
    browser = public_client(app)
    await open_intent(browser)
    key = str(uuid4())
    for _ in range(5):
        response = await post_guest(browser, key)
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "GUEST_ATTEMPT_PENDING"
        assert response.headers["retry-after"] == "2" and "set-cookie" not in response.headers
    assert len(provider.signups) == 1, "an unknown outcome must never reissue a signup"
    attempt = await only_attempt(app)
    assert attempt.state == "ambiguous" and attempt.user_id is None
    assert await count(app, User) == users_before, "an unresolved attempt is never granted"
    # A changed key does not smuggle in a second signup either.
    other = await post_guest(browser, str(uuid4()))
    assert other.status_code == 409 and other.json()["error"]["code"] == "IDEMPOTENCY_CONFLICT"
    assert len(provider.signups) == 1


async def test_provider_success_database_failure(clients, monkeypatch):
    from app.infrastructure.database.models import User
    from app.modules.guests import service

    app, _, provider = await setup(clients)
    canary = uuid4()
    async with app.state.database.sessions.begin() as db:
        await db.execute(text("insert into auth.users(id,is_anonymous) values (:id,false)"), {"id": canary})
    users_before = await count(app, User)

    async def explode(*args, **kwargs):
        raise RuntimeError("database failure during grant")

    monkeypatch.setattr(service, "record_age", explode)
    browser = public_client(app)
    await open_intent(browser)
    key = str(uuid4())
    response = await post_guest(browser, key)
    assert response.status_code == 503 and response.json()["error"]["code"] == "AUTH_UNAVAILABLE"
    assert "moodprint_session" not in " ".join(response.headers.get_list("set-cookie"))
    attempt = await only_attempt(app)
    assert attempt.state == "orphan_pending" and attempt.user_id is None
    assert attempt.provider_subject == provider.created[0]
    assert await count(app, User) == users_before, "no application grant on a failed grant"
    async with app.state.database.sessions() as db:
        assert await db.scalar(text("select count(*) from auth.users where id=:id"), {"id": canary}) == 1
    # The orphan is terminal for this intent: retries never sign up again.
    again = await post_guest(browser, key)
    assert again.status_code == 409 and again.json()["error"]["code"] == "GUEST_INTENT_TERMINAL"
    assert len(provider.signups) == 1


async def test_captcha_rejection_is_terminal_refunds_creation_and_counts_failure(clients):
    from app.modules.guests.models import GuestAbuseBucket

    app, _, provider = await setup(clients, mode="captcha")
    browser, response = await trial(app, key="key-captcha")
    assert response.status_code == 422 and response.json()["error"]["code"] == "CAPTCHA_FAILED"
    attempt = await only_attempt(app)
    assert attempt.state == "rejected" and attempt.last_error == "CAPTCHA_FAILED"
    async with app.state.database.sessions() as db:
        buckets = {b.scope: b.count for b in (await db.scalars(select(GuestAbuseBucket))).all()}
    assert buckets["creation_hour"] == 0 and buckets["creation_day"] == 0
    assert buckets["failed_signup"] == 1
    again = await post_guest(browser, "key-captcha")
    assert again.status_code == 409 and again.json()["error"]["code"] == "GUEST_INTENT_TERMINAL"
    assert len(provider.signups) == 1


async def test_under_16_or_unconfirmed_never_reaches_the_provider(clients):
    app, _, provider = await setup(clients)
    child_year = datetime.now(UTC).year - 12
    for eligibility in ({"birthYear": child_year}, {"confirmedMinimumAge": False}):
        browser = public_client(app)
        await open_intent(browser)
        response = await post_guest(browser, str(uuid4()), guest_body(**eligibility))
        assert response.status_code == 422, eligibility
        assert response.json()["error"]["code"] == "GUEST_INELIGIBLE"
    assert provider.signups == []
    from app.modules.guests.models import GuestProvisioningAttempt

    async with app.state.database.sessions() as db:
        states = {a.state for a in (await db.scalars(select(GuestProvisioningAttempt))).all()}
    assert states == {"intent"}


async def test_registered_cookie_is_never_overwritten(clients):
    app, actors, provider = await setup(clients)
    registered, _ = actors[0]
    await open_intent(registered)
    response = await post_guest(registered, str(uuid4()))
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "REGISTERED_SESSION_PRESENT"
    assert "set-cookie" not in response.headers and provider.signups == []
    assert (await registered.get("/api/v1/session")).json()["accountKind"] == "registered"


async def test_live_guest_cookie_returns_the_same_trial_without_another_grant(clients):
    app, _, provider = await setup(clients)
    browser, granted = await trial(app)
    assert granted.status_code == 201
    again = await post_guest(browser, str(uuid4()))
    assert again.status_code == 200
    assert again.json()["userId"] == granted.json()["userId"]
    assert again.json()["guestExpiresAt"] == granted.json()["guestExpiresAt"]
    assert len(provider.signups) == 1 and await count_guests(app) == 1


async def count_guests(app):
    from app.infrastructure.database.models import User

    async with app.state.database.sessions() as db:
        return await db.scalar(
            select(func.count()).select_from(User).where(User.account_kind == "guest")
        )


async def test_entry_flag_off_blocks_new_signup_but_not_recovery(clients):
    app, _, provider = await setup(clients)
    first = public_client(app)
    await open_intent(first)
    key = str(uuid4())
    assert (await post_guest(first, key)).status_code == 201
    intent = first.cookies.get("moodprint_guest_intent", path="/api/v1/auth")

    waiting = public_client(app)
    await open_intent(waiting)  # a second visitor already holds an unbound intent
    app.state.settings.guest_auth_enabled = False

    recover = public_client(app)
    recover.cookies.set("moodprint_guest_intent", intent, path="/api/v1/auth")
    recovered = await post_guest(recover, key)
    assert recovered.status_code == 200, "an already committed grant stays recoverable"

    blocked = await post_guest(waiting, str(uuid4()))
    assert blocked.status_code == 503 and blocked.json()["error"]["code"] == "GUEST_DISABLED"
    assert len(provider.signups) == 1


async def test_idempotency_key_and_payload_are_bound(clients):
    app, _, provider = await setup(clients, mode="timeout")
    browser = public_client(app)
    await open_intent(browser)
    key = str(uuid4())
    assert (await post_guest(browser, key)).status_code == 409
    changed = await post_guest(browser, key, guest_body(birthYear=1999))
    assert changed.status_code == 409 and changed.json()["error"]["code"] == "IDEMPOTENCY_CONFLICT"
    missing = await browser.post(
        "/api/v1/auth/guest", json=guest_body(), headers={"Origin": "http://127.0.0.1:5173", "X-Guest-Intent": "1"}
    )
    assert missing.status_code == 422 and missing.json()["error"]["code"] == "IDEMPOTENCY_REQUIRED"
    assert len(provider.signups) == 1


async def test_permanent_login_rejects_anonymous_identities_and_guest_mappings(clients, monkeypatch):
    from app.infrastructure.database.models import User
    from app.modules.auth.provider import ProviderSession, SupabaseAuth

    app, _, _ = await setup(clients)
    _, granted = await trial(app)
    assert granted.status_code == 201
    async with app.state.database.sessions() as db:
        guest = await db.scalar(select(User).where(User.account_kind == "guest"))
    expires = datetime.now(UTC) + timedelta(hours=1)

    def verified(anonymous, subject):
        async def password_session(self, email, password):
            return ProviderSession(subject, uuid4(), "synthetic-token", expires, anonymous)

        return password_session

    login = {"email": "user@example.com", "password": "correct horse"}
    headers = {"Origin": "http://127.0.0.1:5173"}
    # A verified anonymous identity can never become a permanent session...
    monkeypatch.setattr(SupabaseAuth, "password_session", verified(True, uuid4()))
    anonymous = await public_client(app).post("/api/v1/auth/login", json=login, headers=headers)
    assert anonymous.status_code == 403 and anonymous.json()["error"]["code"] == "REGISTERED_REQUIRED"
    # ...and a permanent-looking provider identity cannot capture an existing guest mapping.
    monkeypatch.setattr(SupabaseAuth, "password_session", verified(False, guest.auth_subject))
    mapped = await public_client(app).post("/api/v1/auth/login", json=login, headers=headers)
    assert mapped.status_code == 403 and mapped.json()["error"]["code"] == "ACCOUNT_UNAVAILABLE"
    assert "moodprint_session" not in " ".join(mapped.headers.get_list("set-cookie"))


async def add_registered_session(app, user_id):
    import hashlib

    import httpx

    from app.infrastructure.database.models import AuthSession

    token, csrf, provider_sid = f"reg-{uuid4()}", f"csrf-{uuid4()}", uuid4()
    async with app.state.database.sessions.begin() as db:
        db.add(
            AuthSession(
                user_id=user_id,
                token_hash=hashlib.sha256(token.encode()).hexdigest(),
                csrf_hash=hashlib.sha256(csrf.encode()).hexdigest(),
                provider_session_id=provider_sid,
                expires_at=datetime.now(UTC) + timedelta(hours=1),
            )
        )
        await db.execute(
            text("insert into auth.sessions(id,user_id) values (:s,:u)"),
            {"s": provider_sid, "u": user_id},
        )
    client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")
    client.cookies.set("moodprint_session", token)
    client.headers["X-CSRF-Token"] = csrf
    app.state.test_clients.append(client)
    return client


async def test_guest_logout_ends_all_sessions_and_expedites_cleanup(clients):
    import hashlib

    from app.infrastructure.database.models import AuthSession, User
    from app.modules.guests.models import GuestCleanupJob

    app, actors, provider = await setup(clients)
    first = public_client(app)
    await open_intent(first)
    key = str(uuid4())
    granted = await post_guest(first, key)
    assert granted.status_code == 201
    attempt = await only_attempt(app)
    async with app.state.database.sessions() as db:
        user = await db.get(User, attempt.user_id)
        original = (user.guest_started_at, user.guest_expires_at, user.auth_version)
        template = await db.scalar(select(AuthSession).where(AuthSession.user_id == user.id))
    # A second tab holds its own live credential for the same trial.
    other_token, other_csrf = f"tab-{uuid4()}", f"csrf-{uuid4()}"
    async with app.state.database.sessions.begin() as db:
        db.add(
            AuthSession(
                user_id=user.id,
                token_hash=hashlib.sha256(other_token.encode()).hexdigest(),
                csrf_hash=hashlib.sha256(other_csrf.encode()).hexdigest(),
                provider_session_id=template.provider_session_id,
                expires_at=template.expires_at,
                auth_version=template.auth_version,
            )
        )
    tab = public_client(app)
    tab.cookies.set("moodprint_session", other_token)
    tab.headers["X-CSRF-Token"] = other_csrf
    assert (await tab.get("/api/v1/session")).status_code == 200

    intent = first.cookies.get("moodprint_guest_intent", path="/api/v1/auth")
    forged = await first.post(
        "/api/v1/auth/logout", headers={"X-CSRF-Token": "forged", "Idempotency-Key": str(uuid4())}
    )
    assert forged.status_code == 403
    csrf = first.cookies.get("moodprint_csrf")
    ended = await first.post(
        "/api/v1/auth/logout", headers={"X-CSRF-Token": csrf, "Idempotency-Key": str(uuid4())}
    )
    assert ended.status_code == 204
    cleared = " ".join(ended.headers.get_list("set-cookie")).lower()
    for name in ("moodprint_session", "moodprint_csrf", "moodprint_guest_intent"):
        assert name in cleared
    assert "max-age=0" in cleared

    async with app.state.database.sessions() as db:
        user = await db.get(User, attempt.user_id)
        sessions = (await db.scalars(select(AuthSession).where(AuthSession.user_id == user.id))).all()
        job = await db.get(GuestCleanupJob, user.id)
        now = await db_now(app)
    assert user.status == "deleting" and user.auth_version == original[2] + 1
    assert (user.guest_started_at, user.guest_expires_at) == original[:2], "ending never moves T"
    assert sessions and all(row.revoked for row in sessions)
    assert job.due_at <= now and job.next_attempt_at <= now and job.state == "pending"
    # Every credential, including the other tab's, is dead; recovery cannot reopen the trial.
    assert (await tab.get("/api/v1/session")).status_code == 401
    assert (await first.get("/api/v1/session")).status_code == 401
    retry = public_client(app)
    retry.cookies.set("moodprint_guest_intent", intent, path="/api/v1/auth")
    recovery = await post_guest(retry, key)
    assert recovery.status_code == 409 and recovery.json()["error"]["code"] == "GUEST_INTENT_TERMINAL"
    assert len(provider.signups) == 1

    # Registered logout is untouched: it ends only its own session.
    registered, uid = actors[0]
    second = await add_registered_session(app, uid)
    out = await registered.post("/api/v1/auth/logout", headers={"Idempotency-Key": "k"})
    assert out.status_code == 204
    assert (await registered.get("/api/v1/session")).status_code == 401
    assert (await second.get("/api/v1/session")).status_code == 200


async def test_guest_end_endpoint_is_guest_only_idempotent_and_clears_cookies(clients):
    app, actors, _ = await setup(clients)
    registered, _uid = actors[0]
    denied = await registered.post(
        "/api/v1/auth/guest/end", json={}, headers={"Idempotency-Key": "k"}
    )
    assert denied.status_code == 403 and denied.json()["error"]["code"] == "GUEST_REQUIRED"
    assert (await registered.get("/api/v1/session")).status_code == 200

    browser, granted = await trial(app)
    assert granted.status_code == 201
    csrf = browser.cookies.get("moodprint_csrf")
    missing_key = await browser.post(
        "/api/v1/auth/guest/end", json={}, headers={"X-CSRF-Token": csrf}
    )
    assert missing_key.status_code == 422
    headers = {"X-CSRF-Token": csrf, "Idempotency-Key": "end-1"}
    end = await browser.post("/api/v1/auth/guest/end", json={}, headers=headers)
    assert end.status_code == 204
    # A lost response is safe: the repeat finds a dead session and clears the cookies again.
    repeat = await browser.post("/api/v1/auth/guest/end", json={}, headers=headers)
    assert repeat.status_code == 401
    assert "max-age=0" in " ".join(repeat.headers.get_list("set-cookie")).lower()
