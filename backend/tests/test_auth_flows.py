"""Supabase-backed auth flows against a fake provider transport and real PostgreSQL."""

import base64
import json
import time
from datetime import timedelta
from uuid import uuid4

import httpx
import pytest
from pydantic import SecretStr, ValidationError
from sqlalchemy import select, text, update

ORIGIN = "http://127.0.0.1:5173"
SUPABASE = "https://example-project.supabase.co"


def jwt(sub, session_id, exp=None, anonymous=False):
    def part(value):
        return base64.urlsafe_b64encode(json.dumps(value).encode()).rstrip(b"=").decode()

    claims = {
        "sub": str(sub),
        "session_id": str(session_id),
        "iss": SUPABASE + "/auth/v1",
        "aud": "authenticated",
        "exp": exp or int(time.time()) + 3600,
        "is_anonymous": anonymous,
    }
    return f"{part({'alg': 'none'})}.{part(claims)}.signature"


class FakeSupabase:
    def __init__(self, database):
        self.database = database
        self.users = {}
        self.calls = []
        self.next_error = None

    def add(self, email, password, confirmed=True):
        self.users[email] = {"id": uuid4(), "password": password, "confirmed": confirmed}
        return self.users[email]["id"]

    async def session_row(self, uid):
        sid = uuid4()
        async with self.database.begin() as db:
            await db.execute(
                text("insert into auth.sessions(id,user_id) values (:id,:uid)"),
                {"id": sid, "uid": uid},
            )
        return sid

    def handler(self, request: httpx.Request):
        path = request.url.path.removeprefix("/auth/v1")
        body = json.loads(request.content) if request.content else {}
        self.calls.append((request.method, path, dict(request.url.params), body))
        if self.next_error:
            status, payload = self.next_error
            self.next_error = None
            return httpx.Response(status, json=payload)
        if path == "/token":
            user = self.users.get(body["email"])
            if not user or user["password"] != body["password"]:
                return httpx.Response(400, json={"error_code": "invalid_credentials"})
            if not user["confirmed"]:
                return httpx.Response(400, json={"error_code": "email_not_confirmed"})
            return httpx.Response(200, json={"access_token": jwt(user["id"], user["session"])})
        if path == "/user" and request.method == "GET":
            token = request.headers["Authorization"].removeprefix("Bearer ")
            claims = json.loads(base64.urlsafe_b64decode(token.split(".")[1] + "=="))
            return httpx.Response(
                200, json={"id": claims["sub"], "is_anonymous": claims["is_anonymous"]}
            )
        if path == "/user" and request.method == "PUT":
            if len(body["password"]) < 10:
                return httpx.Response(422, json={"error_code": "weak_password"})
            return httpx.Response(200, json={})
        if path == "/signup":
            if body["email"] in self.users:
                return httpx.Response(422, json={"error_code": "user_already_exists"})
            self.add(body["email"], body["password"], confirmed=False)
            return httpx.Response(200, json={"id": str(uuid4())})
        if path in ("/recover", "/resend", "/logout"):
            return httpx.Response(200 if path != "/logout" else 204, json={})
        return httpx.Response(404, json={})


@pytest.fixture
async def auth_env(clients, database):
    from app.modules.auth import routes

    for limiter in (routes.LOGIN_LIMIT, routes.IP_LIMIT, routes.EMAIL_LIMIT):
        limiter.attempts.clear()
    app, actors = clients
    app.state.settings.supabase_url = SUPABASE
    app.state.settings.supabase_publishable_key = SecretStr("publishable-test")
    fake = FakeSupabase(database)
    app.state.auth_transport = httpx.MockTransport(fake.handler)
    client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")
    yield app, fake, client, actors
    await client.aclose()


async def login(fake, client, email="user@example.com", password="correct horse"):
    if email not in fake.users:
        uid = fake.add(email, password)
        fake.users[email]["session"] = await fake.session_row(uid)
    return await client.post(
        "/api/v1/auth/login", json={"email": email, "password": password}, headers={"Origin": ORIGIN}
    )


@pytest.mark.postgres
async def test_login_sets_sliding_session_and_absolute_cookie(auth_env):
    from app.infrastructure.database.models import AuthSession, now

    app, fake, client, _ = auth_env
    response = await login(fake, client)
    assert response.status_code == 200, response.text
    cookie = response.headers.get_list("set-cookie")[0]
    assert "HttpOnly" in cookie and "SameSite=strict" in cookie
    assert f"Max-Age={7 * 24 * 3600}" in cookie
    async with app.state.database.sessions() as db:
        session = (await db.scalars(select(AuthSession).order_by(AuthSession.expires_at.desc()))).first()
        remaining = session.expires_at - now()
    assert timedelta(hours=11) < remaining <= timedelta(hours=12)


@pytest.mark.postgres
async def test_active_session_slides_but_never_resurrects_revoked(auth_env):
    from app.infrastructure.database.models import AuthSession, now

    app, _, _, actors = auth_env
    client, uid = actors[0]
    async with app.state.database.sessions.begin() as db:
        await db.execute(
            update(AuthSession)
            .where(AuthSession.user_id == uid)
            .values(expires_at=now() + timedelta(minutes=5))
        )
    assert (await client.get("/api/v1/session")).status_code == 200
    async with app.state.database.sessions() as db:
        session = await db.scalar(select(AuthSession).where(AuthSession.user_id == uid))
    assert session.expires_at - now() > timedelta(hours=11)
    async with app.state.database.sessions.begin() as db:
        await db.execute(update(AuthSession).where(AuthSession.user_id == uid).values(revoked=True))
    assert (await client.get("/api/v1/session")).status_code == 401


@pytest.mark.postgres
async def test_unconfirmed_email_and_provider_rate_limit_are_distinct(auth_env):
    _, fake, client, _ = auth_env
    fake.add("new@example.com", "correct horse", confirmed=False)
    response = await client.post(
        "/api/v1/auth/login", json={"email": "new@example.com", "password": "correct horse"}
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "EMAIL_NOT_CONFIRMED"
    fake.next_error = (429, {"error_code": "over_request_rate_limit"})
    response = await client.post(
        "/api/v1/auth/login", json={"email": "new@example.com", "password": "x"}
    )
    assert response.status_code == 429
    assert response.json()["error"]["code"] == "AUTH_RATE_LIMITED"


@pytest.mark.postgres
async def test_repeated_failed_logins_are_throttled_before_the_provider(auth_env):
    _, fake, client, _ = auth_env
    for _ in range(10):
        response = await client.post(
            "/api/v1/auth/login", json={"email": "victim@example.com", "password": "guess"}
        )
        assert response.status_code == 401
    before = len(fake.calls)
    response = await client.post(
        "/api/v1/auth/login", json={"email": "Victim@Example.com", "password": "guess"}
    )
    assert response.status_code == 429
    assert len(fake.calls) == before


@pytest.mark.postgres
async def test_signup_is_enumeration_safe_and_never_echoes_password(auth_env):
    _, fake, client, _ = auth_env
    first = await client.post(
        "/api/v1/auth/signup",
        json={"email": "fresh@example.com", "password": "PASSWORD-CANARY-1", "eligibility": signup_eligibility()},
        headers={"Origin": ORIGIN},
    )
    assert first.status_code == 202 and first.json() == {"status": "sent"}
    method, path, params, _ = fake.calls[-1]
    assert (method, path) == ("POST", "/signup")
    assert params["redirect_to"] == ORIGIN + "/auth/callback"
    again = await client.post(
        "/api/v1/auth/signup", json={"email": "fresh@example.com", "password": "PASSWORD-CANARY-2", "eligibility": signup_eligibility()}
    )
    assert again.status_code == 202 and again.json() == first.json()
    short = await client.post(
        "/api/v1/auth/signup", json={"email": "x@example.com", "password": "PASSWORD-CANARY-3"[:5]}
    )
    assert short.status_code == 422 and "CANARY" not in short.text
    foreign = await client.post(
        "/api/v1/auth/signup",
        json={"email": "y@example.com", "password": "long enough", "eligibility": signup_eligibility()},
        headers={"Origin": "https://evil.example"},
    )
    assert foreign.status_code == 403


@pytest.mark.postgres
async def test_recovery_request_is_uniform_and_rate_limited_per_email(auth_env):
    _, _, client, _ = auth_env
    for _ in range(3):
        response = await client.post(
            "/api/v1/auth/password-recovery", json={"email": "unknown@example.com"}
        )
        assert response.status_code == 202
    response = await client.post(
        "/api/v1/auth/password-recovery", json={"email": "unknown@example.com"}
    )
    assert response.status_code == 429


@pytest.mark.postgres
async def test_password_reset_updates_provider_and_ends_existing_sessions(auth_env):
    _, fake, client, _ = auth_env
    assert (await login(fake, client)).status_code == 200
    assert (await client.get("/api/v1/session")).status_code == 200
    user = fake.users["user@example.com"]
    recovery = jwt(user["id"], uuid4())
    weak = await client.post(
        "/api/v1/auth/password-reset", json={"accessToken": recovery, "password": "short123"}
    )
    assert weak.status_code == 422 and weak.json()["error"]["code"] == "WEAK_PASSWORD"
    done = await client.post(
        "/api/v1/auth/password-reset",
        json={"accessToken": recovery, "password": "a much better pass"},
    )
    assert done.status_code == 200 and done.json() == {"status": "updated"}
    assert ("POST", "/logout") in [(m, p) for m, p, _, _ in fake.calls]
    assert (await client.get("/api/v1/session")).status_code == 401


@pytest.mark.postgres
async def test_anonymous_token_cannot_use_the_permanent_recovery_path(auth_env):
    _, fake, client, _ = auth_env
    anonymous = jwt(uuid4(), uuid4(), anonymous=True)
    response = await client.post(
        "/api/v1/auth/password-reset",
        json={"accessToken": anonymous, "password": "a much better pass"},
    )
    assert response.status_code == 403 and response.json()["error"]["code"] == "REGISTERED_REQUIRED"
    # No conversion: the provider never receives PUT /user and no session is revoked or logged out.
    assert [(m, p) for m, p, _, _ in fake.calls if m == "PUT"] == []
    assert ("POST", "/logout") not in [(m, p) for m, p, _, _ in fake.calls]


@pytest.mark.postgres
async def test_step_up_reauthentication_unlocks_export_for_the_same_account_only(auth_env):
    _, fake, client, _ = auth_env
    assert (await login(fake, client)).status_code == 200
    csrf = client.cookies.get("moodprint_csrf")
    headers = {"X-CSRF-Token": csrf, "Idempotency-Key": str(uuid4())}
    from app.infrastructure.database.models import AuthSession, User

    app = auth_env[0]
    async with app.state.database.sessions.begin() as db:
        await db.execute(update(User).values(age_band="adult"))
        await db.execute(
            update(AuthSession).values(
                reauthenticated_at=AuthSession.expires_at - timedelta(days=1)
            )
        )
    stale = await client.post("/api/v1/exports", json={"scopes": ["moods"]}, headers=headers)
    assert stale.status_code == 401 and stale.json()["error"]["code"] == "REAUTH_REQUIRED"
    other = fake.add("other@example.com", "other pass")
    fake.users["other@example.com"]["session"] = await fake.session_row(other)
    mismatch = await client.post(
        "/api/v1/auth/reauthenticate",
        json={"email": "other@example.com", "password": "other pass"},
        headers={"X-CSRF-Token": csrf},
    )
    assert mismatch.status_code == 403
    ok = await client.post(
        "/api/v1/auth/reauthenticate",
        json={"email": "user@example.com", "password": "correct horse"},
        headers={"X-CSRF-Token": csrf},
    )
    assert ok.status_code == 200, ok.text
    headers["Idempotency-Key"] = str(uuid4())
    exported = await client.post("/api/v1/exports", json={"scopes": ["moods"]}, headers=headers)
    assert exported.status_code in (200, 201, 202), exported.text


def test_production_settings_fail_closed_on_insecure_origin():
    from app.core.config import Settings

    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            app_env="production",
            frontend_origin="http://moodprint.example",
            supabase_url=SUPABASE,
            database_url="postgresql://u:p@db.example/postgres",
        )
    Settings(
        _env_file=None,
        app_env="production",
        frontend_origin="https://moodprint.example",
        supabase_url=SUPABASE,
        supabase_publishable_key="synthetic-publishable-key",
        database_url="postgresql://u:p@db.example/postgres",
    )


async def test_last_seen_is_written_only_with_the_sliding_session_refresh(clients):
    from sqlalchemy import select

    from app.infrastructure.database.models import User

    app, actors = clients
    client, uid = actors[0]

    async def last_seen():
        async with app.state.database.sessions() as db:
            return await db.scalar(select(User.last_seen_at).where(User.id == uid))

    assert await last_seen() is None
    assert (await client.get("/api/v1/session")).status_code == 200
    first = await last_seen()
    assert first is not None
    assert (await client.get("/api/v1/session")).status_code == 200
    assert await last_seen() == first  # no extra write inside the 15-minute window


def signup_eligibility(**changes):
    return {"birthYear": 2000, "confirmedMinimumAge": True, "confirmedAdultAge": False,
            "expectedVersion": 0, "policyVersion": "self-declared-age-v2-18plus", **changes}


@pytest.mark.postgres
@pytest.mark.parametrize("years,confirmed,want", [(16,False,403),(17,False,403),(18,False,403),(18,True,202),(19,False,202)])
async def test_signup_requires_adult_declaration_before_provider(auth_env, years, confirmed, want):
    from datetime import datetime
    from zoneinfo import ZoneInfo
    _, fake, client, _ = auth_env
    year = datetime.now(ZoneInfo("Asia/Bangkok")).year
    response = await client.post("/api/v1/auth/signup", json={
        "email":"adult-policy@example.invalid", "password":"synthetic-password",
        "eligibility":signup_eligibility(birthYear=year-years,confirmedAdultAge=confirmed)})
    assert response.status_code == want, response.text
    if want == 403:
        assert fake.calls == []


@pytest.mark.postgres
async def test_signup_rejects_old_or_missing_age_policy_without_provider_call(auth_env):
    _, fake, client, _ = auth_env
    payload={"email":"adult-policy@example.invalid","password":"synthetic-password"}
    for body in (payload,{**payload,"eligibility":signup_eligibility(policyVersion="self-declared-age-v1")},
                 {**payload,"eligibility":signup_eligibility(expectedVersion=1)}):
        response=await client.post("/api/v1/auth/signup",json=body)
        assert response.status_code==422,response.text
    assert fake.calls==[]
