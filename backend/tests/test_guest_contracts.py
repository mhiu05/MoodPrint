"""Session, public-experience, input and configuration contracts for the guest trial."""

from datetime import datetime, timedelta

import httpx
import pytest
from pydantic import SecretStr, ValidationError
from sqlalchemy import event, func, select

from tests.guest_helpers import add_guest

ELIGIBILITY = {
    "birthYear": 2000,
    "confirmedMinimumAge": True,
    "confirmedAdultAge": False,
    "policyVersion": "self-declared-age-v2-18plus",
    "expectedVersion": 0,
}


@pytest.mark.postgres
async def test_registered_and_guest_session_contracts(clients):
    from app.infrastructure.database.models import User
    from app.modules.moderation.models import StaffRole

    app, actors = clients
    registered = (await actors[0][0].get("/api/v1/session")).json()
    assert registered["accountKind"] == "registered"
    # Null, not omitted, so the generated client can tell the two kinds apart.
    for field in ("guestStartedAt", "guestExpiresAt", "guestQuota"):
        assert field in registered and registered[field] is None
    assert registered["features"]["feedback"] is False

    guest = await add_guest(
        app, usage={"ai_turns": 3, "voice_clips": 1, "voice_milliseconds": 12_500}
    )
    # A forged staff row must never surface for a guest.
    async with app.state.database.sessions.begin() as db:
        db.add(StaffRole(user_id=guest.user_id, role="admin", granted_by="forged-test"))
    statements: list[str] = []
    engine = app.state.database.engine.sync_engine

    def record(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    event.listen(engine, "before_cursor_execute", record)
    try:
        response = await guest.client.get("/api/v1/session")
    finally:
        event.remove(engine, "before_cursor_execute", record)
    body = response.json()
    assert response.status_code == 200, response.text
    assert body["accountKind"] == "guest"
    assert datetime.fromisoformat(body["guestStartedAt"]) == guest.started_at
    assert datetime.fromisoformat(body["guestExpiresAt"]) == guest.expires_at
    assert guest.expires_at - guest.started_at == timedelta(seconds=7200)
    assert guest.started_at < datetime.fromisoformat(body["serverTime"]) < guest.expires_at
    assert body["guestQuota"] == {
        "aiTurnsRemaining": 47,
        "aiTurnsLimit": 50,
        "voiceClipsRemaining": 19,
        "voiceSecondsRemaining": 587.5,
    }
    assert body["features"]["matching"] is False
    assert body["features"]["ai"] is False and body["features"]["voice"] is False
    assert body["staff"] is None
    # Guest session serialization reads no social, moderation or staff rows.
    joined = " ".join(statements).lower()
    for table in ("staff_roles", "moderation_actions", "connections", "published_profiles", "pairs"):
        assert f"moodprint.{table}" not in joined

    async with app.state.database.sessions() as db:
        stored = await db.scalar(select(User.guest_expires_at).where(User.id == guest.user_id))
    assert stored == guest.expires_at, "reading the session must never renew the deadline"


@pytest.mark.postgres
async def test_public_experience_is_identity_free_and_flag_driven(clients):
    from app.infrastructure.database.models import User
    from app.modules.guests.models import GuestProvisioningAttempt

    app, actors = clients
    anonymous = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")

    async def counts():
        async with app.state.database.sessions() as db:
            return (
                await db.scalar(select(func.count()).select_from(User)),
                await db.scalar(select(func.count()).select_from(GuestProvisioningAttempt)),
            )

    before = await counts()
    response = await anonymous.get("/api/v1/public/experience")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.json() == {
        "guestAvailable": False,
        "guestUnavailableReason": "disabled",
        "feedbackAvailable": False,
        "productTourAvailable": False,
        "captchaSiteKey": None,
    }
    settings = app.state.settings
    settings.guest_auth_enabled = True
    configuration_missing = (await anonymous.get("/api/v1/public/experience")).json()
    assert configuration_missing["guestAvailable"] is False
    assert configuration_missing["guestUnavailableReason"] == "configuration_missing"
    assert configuration_missing["captchaSiteKey"] is None

    settings.supabase_url = "https://example-project.supabase.co"
    settings.supabase_publishable_key = SecretStr("publishable-test")
    settings.guest_captcha_site_key = "public-site-key"
    settings.guest_abuse_hmac_key = SecretStr("h" * 40)
    settings.feedback_enabled = True
    settings.product_tour_enabled = True
    ready = (await anonymous.get("/api/v1/public/experience")).json()
    assert ready == {
        "guestAvailable": True,
        "guestUnavailableReason": None,
        "feedbackAvailable": True,
        "productTourAvailable": True,
        "captchaSiteKey": "public-site-key",
    }
    assert "secret" not in str(ready).lower() and "budget" not in str(ready).lower()
    assert await counts() == before, "a public read must not create any identity or attempt"
    await anonymous.aclose()


def test_guest_input_and_settings_defaults_fail_closed():
    from app.core.config import Settings
    from app.modules.guests.schemas import GuestInput

    valid = {"eligibility": ELIGIBILITY, "captchaToken": "x" * 20, "disclosureVersion": "guest-v2"}
    parsed = GuestInput.model_validate(valid)
    assert "x" * 20 not in repr(parsed), "the CAPTCHA token must never reach a repr or log"
    for broken in (
        {**valid, "disclosureVersion": "guest-v1"},
        {**valid, "captchaToken": ""},
        {**valid, "captchaToken": "y" * 4097},
        {**valid, "eligibility": {**ELIGIBILITY, "expectedVersion": 1}},
        {**valid, "unexpected": True},
    ):
        with pytest.raises(ValidationError):
            GuestInput.model_validate(broken)

    settings = Settings(_env_file=None)
    for flag in (
        "guest_auth_enabled",
        "guest_paid_enabled",
        "guest_semantic_enabled",
        "feedback_enabled",
        "feedback_admin_enabled",
        "product_tour_enabled",
    ):
        assert getattr(settings, flag) is False, flag
    assert settings.guest_daily_budget_usd is None and settings.guest_pricing_json == {}
    assert (
        settings.guest_ai_turns,
        settings.guest_ai_per_minute,
        settings.guest_ai_concurrency,
        settings.guest_ai_global_concurrency,
    ) == (50, 6, 1, 10)
    assert (
        settings.guest_voice_clips,
        settings.guest_voice_seconds,
        settings.guest_voice_per_minute,
        settings.guest_voice_concurrency,
        settings.guest_voice_global_concurrency,
    ) == (20, 600, 2, 1, 3)
    assert "h" * 40 not in repr(Settings(_env_file=None, guest_abuse_hmac_key=SecretStr("h" * 40)))

    with pytest.raises(ValidationError):
        Settings(_env_file=None, guest_abuse_hmac_key=SecretStr("short"))
    # An explicit guest cap above the global cap is a configuration error...
    with pytest.raises(ValidationError):
        Settings(_env_file=None, ai_global_concurrency=5, guest_ai_global_concurrency=6)
    # ...but an existing deployment that only lowers the global cap keeps working: the unset
    # guest default is clamped, never rejected (registered configurations must not break).
    assert Settings(_env_file=None, ai_global_concurrency=2).guest_ai_global_concurrency == 2
    assert Settings(_env_file=None, ai_global_concurrency=50).guest_ai_global_concurrency == 10
    with pytest.raises(ValidationError):
        Settings(_env_file=None, guest_daily_budget_usd="-1")
