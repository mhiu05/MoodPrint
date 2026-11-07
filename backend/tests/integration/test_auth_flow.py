"""Real local Auth tokens cross the API/JWKS/RLS boundary; no root dotenv."""

import importlib.util
import secrets
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit
from uuid import UUID, uuid4

import httpx
import pytest
from app.main import create_app
from moodprint_shared.env import EnvSettings

from backend.tests.integration.conftest import local_value

_script_path = Path(__file__).resolve().parents[3] / "scripts/check_hosted_auth_settings.py"
_script_spec = importlib.util.spec_from_file_location("hosted_auth_checker", _script_path)
assert _script_spec and _script_spec.loader
_checker = importlib.util.module_from_spec(_script_spec)
_script_spec.loader.exec_module(_checker)


def checked(response: httpx.Response, allowed: set[int], action: str) -> None:
    assert response.status_code in allowed, f"{action}: HTTP {response.status_code}"


@pytest.fixture
def local_settings():
    url = local_value("SUPABASE_URL").rstrip("/")
    if urlsplit(url).hostname not in {"localhost", "127.0.0.1", "::1"}:
        pytest.fail("Auth/Storage integration requires loopback SUPABASE_URL")
    return EnvSettings(
        app_env="test",
        supabase_url=url,
        supabase_publishable_key=local_value("SUPABASE_PUBLISHABLE_KEY"),
        supabase_secret_key=local_value("SUPABASE_SECRET_KEY"),
        database_url=local_value("TEST_DATABASE_URL"),
    )


@dataclass(frozen=True)
class LocalAuthUser:
    user_id: UUID
    token: str = field(repr=False)
    nickname: str


@pytest.fixture
async def auth_users(local_settings):
    secret = local_settings.supabase_secret_key.get_secret_value()
    admin_headers = {"apikey": secret, "Authorization": f"Bearer {secret}"}
    created: list[UUID] = []
    users: list[LocalAuthUser] = []
    async with httpx.AsyncClient(base_url=local_settings.supabase_url, timeout=30) as client:
        try:
            for nickname in ("Synthetic An", "Synthetic Mai"):
                email = f"integration+{uuid4()}@example.test"
                password = secrets.token_urlsafe(32)
                response = await client.post(
                    "/auth/v1/admin/users",
                    headers=admin_headers,
                    json={
                        "email": email,
                        "password": password,
                        "email_confirm": True,
                        "user_metadata": {"nickname": nickname, "age_band": "11-13"},
                    },
                )
                checked(response, {200, 201}, "create synthetic Auth user")
                user_id = UUID(response.json()["id"])
                created.append(user_id)
                response = await client.post(
                    "/auth/v1/token?grant_type=password",
                    headers={"apikey": local_settings.supabase_publishable_key},
                    json={"email": email, "password": password},
                )
                checked(response, {200}, "sign in synthetic Auth user")
                users.append(LocalAuthUser(user_id, response.json()["access_token"], nickname))
            yield users
        finally:
            for user_id in created:
                response = await client.delete(
                    f"/auth/v1/admin/users/{user_id}", headers=admin_headers
                )
                checked(response, {200, 204}, "delete synthetic Auth user")


@pytest.mark.integration
async def test_real_auth_token_creates_profile_and_patch_persists(local_settings, auth_users):
    app = create_app(local_settings)
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            user = auth_users[0]
            headers = {"Authorization": f"Bearer {user.token}"}
            response = await client.get("/v1/me", headers=headers)
            checked(response, {200}, "read profile with real Auth JWT")
            assert response.json()["userId"] == str(user.user_id)
            assert response.json()["nickname"] == user.nickname
            assert response.json()["ageBand"] == "11-13"
            response = await client.patch(
                "/v1/me",
                headers=headers,
                json={"nickname": "Synthetic Updated", "ageBand": "14-17", "reducedMotion": True},
            )
            checked(response, {200}, "patch profile with real Auth JWT")
            response = await client.get("/v1/me", headers=headers)
            assert response.json()["nickname"] == "Synthetic Updated"
            assert response.json()["ageBand"] == "14-17"
            assert response.json()["reducedMotion"] is True


@pytest.mark.integration
async def test_real_auth_users_have_separate_api_profiles(local_settings, auth_users):
    app = create_app(local_settings)
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            a, b = auth_users
            response = await client.get("/v1/me", headers={"Authorization": f"Bearer {a.token}"})
            checked(response, {200}, "read user A")
            response = await client.get("/v1/me", headers={"Authorization": f"Bearer {b.token}"})
            checked(response, {200}, "read user B")
            assert response.json()["userId"] == str(b.user_id)
            assert response.json()["nickname"] == b.nickname
            response = await client.get("/v1/me")
            assert response.status_code == 401


def test_hosted_auth_target_rejects_foreign_project():
    with pytest.raises(ValueError):
        _checker.validate_target("https://foreign.example")


def test_hosted_auth_flags_fail_closed_for_missing_fields():
    assert not all(_checker.assess_settings({}).values())


def test_hosted_auth_flags_accept_confirmed_configuration():
    result = _checker.assess_settings(
        {
            "disable_signup": False,
            "mailer_autoconfirm": False,
            "external": {"anonymous_users": False},
        }
    )
    assert all(result.values())


@pytest.mark.parametrize("external", [None, [], {"anonymous_users": True}, {}])
def test_hosted_auth_flags_reject_ambiguous_or_enabled_anonymous_users(external):
    result = _checker.assess_settings(
        {"disable_signup": False, "mailer_autoconfirm": False, "external": external}
    )
    assert result["anonymous_signins_disabled"] is False
