"""Configured defaults are distinct from effective, prerequisite-gated capabilities."""

import pytest

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
