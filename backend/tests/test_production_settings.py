"""Production configuration must fail before accepting traffic."""

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


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"supabase_publishable_key": ""}, "SUPABASE_PUBLISHABLE_KEY"),
        ({"ai_enabled": True}, "OPENAI_API_KEY and OPENAI_MODEL"),
        ({"stt_enabled": True}, "OPENAI_API_KEY and STT_MODEL"),
        ({"semantic_memory_enabled": True}, "VOYAGE_API_KEY"),
    ],
)
def test_production_requires_enabled_provider_configuration(changes, message):
    with pytest.raises(ValidationError, match=message):
        Settings(_env_file=None, **(BASE | changes))


def test_production_with_disabled_providers_needs_no_paid_keys():
    settings = Settings(_env_file=None, **BASE)
    assert not settings.ai_enabled
    assert not settings.stt_enabled
    assert not settings.semantic_memory_enabled
