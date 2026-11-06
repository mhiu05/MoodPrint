"""School safety profile clamps legacy capabilities without moving default settings."""

import pytest
from pydantic import ValidationError

from app.core.config import FEATURE_FLAGS, Settings
from app.core.profile import FORCED_OFF, LEGACY_DENYLIST, is_school_safety

REVIEWED_FORCED_OFF = (
    "ai_three_agent_experience_enabled",
    "ai_smart_orchestration_enabled",
    "ai_group_chat_enabled",
    "ai_collaboration_enabled",
    "ai_collaboration_defaults_enabled",
    "proactive_enabled",
    "proactive_worker_enabled",
    "ai_web_search_enabled",
    "ai_maps_search_enabled",
    "maps_search_worker_enabled",
    "ai_agent_skills_enabled",
    "activities_enabled",
    "semantic_memory_enabled",
    "journal_semantic_enabled",
    "journal_auto_memory_enabled",
    "product_tour_enabled",
)

REVIEWED_DENYLIST = (
    "/activities",
    "/admin",
    "/ai/groups",
    "/ai/inbox",
    "/ai/maps-searches",
    "/ai/proactive",
    "/ai/prompt-capabilities",
    "/ai/sharing",
    "/blocks",
    "/connection-requests",
    "/connections",
    "/feedback",
    "/journal",
    "/matching",
    "/memories",
    "/moods",
    "/profiles",
    "/proposals",
    "/reports",
    "/reveal-grants",
    "/reveal-requests",
    "/social",
    "/taxonomy",
)


@pytest.fixture
def pure_defaults(monkeypatch):
    for name in (*FEATURE_FLAGS, "APP_PROFILE", "TERMS_VERSION_CURRENT"):
        monkeypatch.delenv(name.upper() if name.islower() else name, raising=False)
    for name in (
        "OPENAI_API_KEY", "OPENAI_MODEL", "STT_MODEL", "VOYAGE_API_KEY",
        "SUPABASE_URL", "SUPABASE_PUBLISHABLE_KEY", "DATABASE_URL",
        "DATABASE_MIGRATION_URL", "APIFY_API_TOKEN", "AI_DAILY_BUDGET_USD",
        "GUEST_ABUSE_HMAC_KEY", "GUEST_CAPTCHA_SITE_KEY",
    ):
        monkeypatch.delenv(name, raising=False)


def test_profile_constants_match_the_reviewed_lists():
    assert FORCED_OFF == REVIEWED_FORCED_OFF
    assert LEGACY_DENYLIST == REVIEWED_DENYLIST
    assert set(FORCED_OFF) <= set(FEATURE_FLAGS)


def test_default_profile_keeps_the_existing_snapshot(pure_defaults):
    settings = Settings(_env_file=None)
    assert settings.app_profile == "default"
    assert settings.terms_version_current == "school-terms-v1"
    assert is_school_safety(settings) is False
    assert [name for name in FEATURE_FLAGS if getattr(settings, name) is not True] == []
    assert [name for name in FORCED_OFF if getattr(settings, name) is not True] == []
    assert "school_safety_profile" not in {reason for _name, reason in settings.degraded_features()}


def test_school_profile_forces_explicit_flags_off(pure_defaults):
    explicit = {name: True for name in FORCED_OFF}
    settings = Settings(_env_file=None, app_profile="school_safety", **explicit)
    assert is_school_safety(settings) is True
    assert [name for name in FORCED_OFF if getattr(settings, name) is not False] == []
    forced = [name for name, reason in settings.degraded_features() if reason == "school_safety_profile"]
    assert forced == list(FORCED_OFF)


PROD = dict(
    _env_file=None,
    app_env="production",
    frontend_origin="https://moodprint.example",
    supabase_url="https://project.supabase.co",
    supabase_publishable_key="synthetic-publishable",
    database_url="postgresql://synthetic:synthetic@db.example/moodprint",
    ai_daily_budget_usd=20,
)


def test_school_profile_accepts_explicit_proactive_worker_without_raising(pure_defaults):
    settings = Settings(
        **PROD,
        app_profile="school_safety",
        proactive_enabled=True,
        proactive_worker_enabled=True,
    )
    assert settings.proactive_enabled is False
    assert settings.proactive_worker_enabled is False
    assert ("proactive_worker_enabled", "school_safety_profile") in settings.degraded_features()


def test_unknown_profile_is_rejected(pure_defaults):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, app_profile="demo")
