"""CAPTCHA is forwarded to Supabase without replacing origin, session or CSRF checks."""

from types import SimpleNamespace

import pytest
from fastapi import Request
from pydantic import ValidationError
from sqlalchemy import func, select

from app.core.config import Settings
from app.modules.guests.availability import experience_view
from tests.test_auth_flows import auth_env as auth_env
from tests.test_auth_flows import jwt, login, signup_eligibility

TOKEN = "CAPTCHA-TOKEN-CANARY"
ENDPOINTS = ["login", "signup", "confirmation", "password-recovery"]


def payload(endpoint, **extra):
    body = {"email": "captcha@example.com"}
    if endpoint in ("login", "signup"):
        body["password"] = "correct horse"
    if endpoint == "signup":
        body["eligibility"] = signup_eligibility()
    return {**body, **extra}


@pytest.fixture
def captcha_env(auth_env):
    app, _, _, _ = auth_env
    app.state.settings.auth_captcha_enabled = True
    app.state.settings.guest_captcha_site_key = "public-site-key"
    return auth_env


@pytest.mark.postgres
@pytest.mark.parametrize("endpoint", ENDPOINTS)
@pytest.mark.parametrize("token", [None, "", "   "])
async def test_required_captcha_stops_auth_before_provider(captcha_env, endpoint, token):
    _, fake, client, _ = captcha_env
    response = await client.post(f"/api/v1/auth/{endpoint}", json=payload(endpoint, captchaToken=token))
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "CAPTCHA_REQUIRED"
    assert fake.calls == []


@pytest.mark.postgres
@pytest.mark.parametrize("endpoint,provider_path", [
    ("signup", "/signup"), ("confirmation", "/resend"), ("password-recovery", "/recover"),
])
async def test_email_auth_forwards_captcha_using_gotrue_wire_contract(captcha_env, endpoint, provider_path):
    _, fake, client, _ = captcha_env
    response = await client.post(f"/api/v1/auth/{endpoint}", json=payload(endpoint, captchaToken=TOKEN))
    assert response.status_code == 202, response.text
    _, path, _, sent = fake.calls[-1]
    assert path == provider_path
    assert sent["gotrue_meta_security"] == {"captcha_token": TOKEN}
    assert TOKEN not in response.text


@pytest.mark.postgres
async def test_password_login_and_step_up_forward_fresh_captcha_and_keep_csrf(captcha_env):
    _, fake, client, _ = captcha_env
    uid = fake.add("captcha@example.com", "correct horse")
    fake.users["captcha@example.com"]["session"] = await fake.session_row(uid)
    response = await client.post("/api/v1/auth/login", json=payload("login", captchaToken=TOKEN))
    assert response.status_code == 200, response.text
    assert fake.calls[0][3]["gotrue_meta_security"] == {"captcha_token": TOKEN}
    before = len(fake.calls)
    denied = await client.post("/api/v1/auth/reauthenticate", json=payload("login", captchaToken="fresh"))
    assert denied.status_code == 403
    assert len(fake.calls) == before
    headers = {"X-CSRF-Token": client.cookies.get("moodprint_csrf")}
    missing = await client.post("/api/v1/auth/reauthenticate", json=payload("login"), headers=headers)
    assert missing.status_code == 422 and missing.json()["error"]["code"] == "CAPTCHA_REQUIRED"
    assert len(fake.calls) == before
    checked = await client.post("/api/v1/auth/reauthenticate", json=payload("login", captchaToken="fresh"), headers=headers)
    assert checked.status_code == 200, checked.text
    exchanges = [body for _, path, _, body in fake.calls if path == "/token"]
    assert [body["gotrue_meta_security"]["captcha_token"] for body in exchanges] == [TOKEN, "fresh"]


@pytest.mark.postgres
@pytest.mark.parametrize("endpoint", ENDPOINTS)
async def test_provider_captcha_rejection_is_safe_and_never_creates_a_session(captcha_env, endpoint, caplog):
    from app.infrastructure.database.models import AuthSession

    app, fake, client, _ = captcha_env
    async with app.state.database.sessions() as db:
        before = await db.scalar(select(func.count()).select_from(AuthSession))
    fake.next_error = (400, {"error_code": "captcha_failed", "msg": TOKEN + " expired"})
    response = await client.post(f"/api/v1/auth/{endpoint}", json=payload(endpoint, captchaToken=TOKEN))
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "CAPTCHA_FAILED"
    assert TOKEN not in response.text + caplog.text
    async with app.state.database.sessions() as db:
        assert await db.scalar(select(func.count()).select_from(AuthSession)) == before


@pytest.mark.postgres
async def test_captcha_enabled_does_not_bypass_origin_or_attempt_limits(captcha_env):
    _, fake, client, _ = captcha_env
    bad_origin = await client.post("/api/v1/auth/login", json=payload("login", captchaToken=TOKEN),
                                   headers={"Origin": "https://evil.example"})
    assert bad_origin.status_code == 403 and fake.calls == []
    for _ in range(10):
        fake.next_error = (400, {"error_code": "captcha_failed"})
        response = await client.post("/api/v1/auth/login", json=payload("login", captchaToken=TOKEN))
        assert response.status_code == 422
    count = len(fake.calls)
    limited = await client.post("/api/v1/auth/login", json=payload("login", captchaToken=TOKEN))
    assert limited.status_code == 429 and len(fake.calls) == count


def test_public_auth_captcha_does_not_depend_on_guest_availability():
    settings = Settings(_env_file=None, guest_captcha_site_key="public-site-key")
    settings.auth_captcha_enabled = True
    request = Request({"type": "http", "app": SimpleNamespace(state=SimpleNamespace(
        settings=settings, database=SimpleNamespace(sessions=None)))})
    view = experience_view(request).model_dump(by_alias=True)
    assert view["guestAvailable"] is False
    assert view["authCaptchaRequired"] is True
    assert view["captchaSiteKey"] == "public-site-key"


def test_production_captcha_requires_a_public_site_key():
    with pytest.raises(ValidationError, match="GUEST_CAPTCHA_SITE_KEY"):
        Settings(_env_file=None, app_env="production", auth_captcha_enabled=True,
                 frontend_origin="https://moodprint.example", supabase_url="https://example.supabase.co",
                 supabase_publishable_key="synthetic", database_url="postgresql://u:p@db.example/postgres")


def test_optional_captcha_tokens_are_hidden_from_input_reprs():
    from app.contracts import EmailInput, LoginInput, SignupInput

    for model, endpoint in [(EmailInput, "confirmation"), (LoginInput, "login"), (SignupInput, "signup")]:
        value = model.model_validate(payload(endpoint, captchaToken=TOKEN))
        assert TOKEN not in repr(value)
        assert model.model_validate(payload(endpoint)).captcha_token is None
        with pytest.raises(ValidationError):
            model.model_validate(payload(endpoint, captchaToken="x" * 4097))


@pytest.mark.postgres
async def test_recovery_bearer_password_update_does_not_require_another_captcha(auth_env):
    from uuid import uuid4

    app, fake, client, _ = auth_env
    assert (await login(fake, client)).status_code == 200
    app.state.settings.auth_captcha_enabled = True
    user = fake.users["user@example.com"]
    response = await client.post("/api/v1/auth/password-reset", json={
        "accessToken": jwt(user["id"], uuid4()), "password": "a much better pass",
    })
    assert response.status_code == 200, response.text
    updates = [body for method, path, _, body in fake.calls if method == "PUT" and path == "/user"]
    assert updates == [{"password": "a much better pass"}]


@pytest.mark.postgres
async def test_invalid_input_never_echoes_a_captcha_token(captcha_env, caplog):
    _, fake, client, _ = captcha_env
    response = await client.post("/api/v1/auth/signup", json=payload("signup", captchaToken=TOKEN * 300))
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert fake.calls == []
    assert TOKEN not in response.text + caplog.text
