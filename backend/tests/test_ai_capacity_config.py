import json

from app.core.config import Settings


def test_capacity_fingerprint_never_contains_secrets():
    from app.core.capacity import ai_capacity_fingerprint

    settings = Settings(_env_file=None, openai_api_key="secret-canary", openai_model="gpt-6-luna",
                        supabase_publishable_key="secret-canary", ai_daily_budget_usd=50)
    fingerprint = ai_capacity_fingerprint(settings)
    encoded = json.dumps(fingerprint)
    assert "secret-canary" not in encoded
    assert fingerprint["ai_daily_budget_usd"] == 50
    assert fingerprint["openai_model"] == "gpt-6-luna"
    assert fingerprint["supported_api_processes"] == 1


def test_duplicate_capacity_key_is_reported_without_values():
    from app.core.capacity import duplicate_capacity_keys

    report = duplicate_capacity_keys("AI_GLOBAL_CONCURRENCY=50\nOPENAI_API_KEY=secret-canary\nai_global_concurrency=10\n")
    assert report == {"AI_GLOBAL_CONCURRENCY": [1, 3]}
    assert "secret-canary" not in json.dumps(report)


def test_all_process_connection_budget_includes_maps_and_overlap():
    from app.infrastructure.database.budget import deployment_budget

    steady = deployment_budget(api_pool=4, api_overflow=1, generations=1)
    overlap = deployment_budget(api_pool=4, api_overflow=1, generations=2)
    assert steady["application"] == 8 and steady["required"] == 12
    assert overlap["application"] == 16 and overlap["required"] == 20
    assert overlap["fits"] is True
    assert deployment_budget(api_pool=4, api_overflow=1, role_limit=10)["fits"] is False
    assert deployment_budget(api_pool=4, api_overflow=1, api_replicas=2)["fits"] is False


def test_budget_schema_rejects_nonfinite_and_over_approved_target():
    import pytest
    from pydantic import ValidationError

    for value in (float("inf"), float("nan"), 50.01):
        with pytest.raises(ValidationError):
            Settings(_env_file=None, ai_daily_budget_usd=value)


def test_budget_guard_uses_approved_fifty_ceiling_consistently():
    from app.ai.accounting import global_budget_nano

    assert global_budget_nano(50) == 50_000_000_000
    assert global_budget_nano(20) == 20_000_000_000
    # Defensive clamp if callers mutate settings after validation.
    assert global_budget_nano(100) == 50_000_000_000
