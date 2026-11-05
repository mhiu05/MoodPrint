"""Configured defaults are distinct from effective, prerequisite-gated capabilities."""

import pytest
from pydantic import ValidationError

from app.core.config import FEATURE_FLAGS, SAFETY_SWITCHES, Settings


@pytest.fixture
def pure_defaults(monkeypatch):
    for name in (*FEATURE_FLAGS, *SAFETY_SWITCHES):
        monkeypatch.delenv(name.upper(), raising=False)
    for name in (
        'OPENAI_API_KEY', 'OPENAI_MODEL', 'STT_MODEL', 'VOYAGE_API_KEY',
        'SUPABASE_URL', 'SUPABASE_PUBLISHABLE_KEY', 'DATABASE_URL',
        'DATABASE_MIGRATION_URL', 'APIFY_API_TOKEN', 'AI_DAILY_BUDGET_USD',
        'GUEST_ABUSE_HMAC_KEY', 'GUEST_CAPTCHA_SITE_KEY',
    ):
        monkeypatch.delenv(name, raising=False)


def test_every_feature_flag_defaults_true(pure_defaults):
    settings = Settings(_env_file=None)
    assert len(FEATURE_FLAGS) == 28
    assert [name for name in FEATURE_FLAGS if getattr(settings, name) is not True] == []


def test_safety_switches_stay_false_and_are_not_features(pure_defaults):
    settings = Settings(_env_file=None)
    assert set(SAFETY_SWITCHES) == {
        'auth_nat_policy_enabled', 'ai_bounded_reservations_enabled', 'ai_dispatch_gate_enabled',
        'database_pool_metrics_enabled', 'database_transaction_timeouts_enabled',
        'auth_captcha_enabled', 'cookie_secure', 'provider_force_ipv4',
        'ai_web_search_token_bound_verified', 'apify_maps_charge_bound_verified',
    }
    assert not set(SAFETY_SWITCHES) & set(FEATURE_FLAGS)
    assert all(getattr(settings, name) is False for name in SAFETY_SWITCHES)


def test_every_bool_field_is_classified():
    bools = {name for name, field in Settings.model_fields.items() if field.annotation is bool}
    assert bools == set(FEATURE_FLAGS) | set(SAFETY_SWITCHES)


def test_env_can_still_disable_each_flag(monkeypatch, pure_defaults):
    for name in FEATURE_FLAGS:
        monkeypatch.setenv(name.upper(), 'false')
    settings = Settings(_env_file=None)
    assert [name for name in FEATURE_FLAGS if getattr(settings, name) is not False] == []


PROD = dict(
    _env_file=None, app_env="production", frontend_origin="https://moodprint.example",
    supabase_url="https://project.supabase.co", supabase_publishable_key="synthetic-publishable",
    database_url="postgresql://synthetic:synthetic@db.example/moodprint",
)


def test_production_defaults_boot_without_optional_secrets(pure_defaults):
    settings = Settings(**PROD)
    reasons = dict(settings.degraded_features())
    assert reasons["ai_enabled"] == "openai_configuration_missing"
    assert reasons["stt_enabled"] == "stt_configuration_missing"
    assert reasons["semantic_memory_enabled"] == "voyage_key_missing"
    assert reasons["journal_semantic_enabled"] == "voyage_key_missing"
    assert settings.proactive_worker_enabled is False
    assert reasons["proactive_worker_enabled"] == "proactive_prerequisites_missing"


def test_explicit_contradiction_still_fails_fast(pure_defaults):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, ai_collaboration_enabled=True, ai_multi_message_enabled=False)


def test_default_dependents_clamp_when_prerequisite_is_disabled(pure_defaults):
    settings = Settings(_env_file=None, ai_multi_message_enabled=False)
    assert not (
        settings.ai_collaboration_enabled or settings.ai_smart_orchestration_enabled
        or settings.ai_group_chat_enabled
    )
    reasons = dict(settings.degraded_features())
    assert reasons["ai_collaboration_enabled"] == "multi_message_disabled"
    assert reasons["ai_smart_orchestration_enabled"] == "multi_message_disabled"
    assert reasons["ai_group_chat_enabled"] == "multi_message_disabled"


async def test_app_with_pure_defaults_serves_health_and_reports_unavailable(clients_defaults):
    from sqlalchemy import text

    from app.core.revisions import READY_REVISIONS

    app, actors = clients_defaults
    async with app.state.database.sessions.begin() as db:
        await db.execute(text("create table if not exists moodprint.alembic_version (version_num varchar(32) primary key)"))
        await db.execute(text("delete from moodprint.alembic_version"))
        await db.execute(text("insert into moodprint.alembic_version values (:v)"), {"v": READY_REVISIONS[0]})
    async with app.router.lifespan_context(app):
        client = actors[0][0]
        assert (await client.get("/api/v1/health/live")).status_code == 200
        assert (await client.get("/api/v1/health/ready")).status_code == 200
        features = (await client.get("/api/v1/session")).json()["features"]
        assert features["ai"] is False
        assert features["aiStatus"] == "configuration_missing"
        assert features["webSearch"] is False
        assert features["mapsSearch"] is False


async def test_admin_routes_need_a_staff_role_not_a_flag(clients_defaults):
    _app, actors = clients_defaults
    client = actors[0][0]
    for path in ("/api/v1/admin/reports", "/api/v1/admin/feedback"):
        assert (await client.get(path)).status_code == 403
