"""Production requires Auth configuration while optional providers degrade safely."""

import pytest
from pydantic import ValidationError

from app.core.config import Settings

BASE = {
    "app_env": "production",
    "frontend_origin": "https://staging.example.org",
    "supabase_url": "https://example.supabase.co",
    "supabase_publishable_key": "synthetic-publishable-key",
    "database_url": "postgresql+psycopg://app:synthetic@db.example.org/moodprint",
}


def test_production_requires_auth_configuration():
    with pytest.raises(ValidationError, match="SUPABASE_PUBLISHABLE_KEY"):
        Settings(_env_file=None, **(BASE | {"supabase_publishable_key": ""}))


@pytest.mark.parametrize(
    ("flag", "reason"),
    [
        ("ai_enabled", "openai_configuration_missing"),
        ("stt_enabled", "stt_configuration_missing"),
        ("semantic_memory_enabled", "voyage_key_missing"),
    ],
)
def test_production_missing_optional_provider_degrades(flag, reason):
    settings = Settings(_env_file=None, **(BASE | {flag: True}))
    assert (flag, reason) in settings.degraded_features()


def test_production_with_disabled_providers_on_legacy_baseline_needs_no_paid_keys():
    settings = Settings(_env_file=None, **BASE)
    assert not settings.ai_enabled
    assert not settings.stt_enabled
    assert not settings.semantic_memory_enabled
