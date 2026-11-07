"""Security regressions for the local harness (run with pytest explicitly)."""

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("e2e_stack", ROOT / "scripts/e2e_stack.py")
assert SPEC and SPEC.loader
stack = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(stack)


def values():
    return {
        "APP_ENV": "test",
        "SUPABASE_URL": "http://127.0.0.1:54321",
        "SUPABASE_PUBLISHABLE_KEY": "sb_publishable_synthetic",
        "SUPABASE_SECRET_KEY": "synthetic-local-secret",
        "DATABASE_URL": "postgresql+asyncpg://moodprint_api:synthetic@127.0.0.1:54322/postgres",
        "TEST_DATABASE_URL": "postgresql+asyncpg://moodprint_api:synthetic@127.0.0.1:54322/postgres",
        "TEST_ADMIN_DATABASE_URL": "postgresql+asyncpg://postgres:synthetic@127.0.0.1:54322/postgres",
    }


def test_child_environment_drops_inherited_secrets_and_sets_every_public_endpoint():
    original = {
        "PATH": "synthetic-path",
        "OPENAI_API_KEY": "must-not-copy",
        "VITE_PUBLIC_LEAK": "must-not-copy",
        "DATABASE_URL": "postgresql://hosted/db",
    }
    child = stack.build_environment(values(), original)
    assert child["APP_ENV"] == "test"
    assert child["VITE_PUBLIC_SUPABASE_URL"] == "http://127.0.0.1:54321"
    assert child["VITE_PUBLIC_API_BASE_URL"] == "http://127.0.0.1:8008"
    assert child["VITE_PUBLIC_SUPABASE_PUBLISHABLE_KEY"] == "sb_publishable_synthetic"
    assert "OPENAI_API_KEY" not in child and "VITE_PUBLIC_LEAK" not in child
    assert original["DATABASE_URL"] == "postgresql://hosted/db"


@pytest.mark.parametrize(
    "field", ["SUPABASE_URL", "DATABASE_URL", "TEST_DATABASE_URL", "TEST_ADMIN_DATABASE_URL"]
)
def test_hosted_endpoints_are_rejected_without_echoing_values(field):
    env = values()
    env[field] = "https://do-not-echo-secret@hosted.example/private"
    with pytest.raises(ValueError) as result:
        stack.build_environment(env, {})
    assert field in str(result.value)
    assert "do-not-echo" not in str(result.value)
    assert "hosted.example" not in str(result.value)


def test_frontend_checks_clear_real_public_env_without_mutating_e2e_env():
    child = stack.build_environment(values(), {"PATH": "synthetic-path"})
    isolated = stack.environment_for_frontend_checks(child)
    assert isolated["VITE_PUBLIC_SUPABASE_URL"] == ""
    assert isolated["VITE_PUBLIC_SUPABASE_PUBLISHABLE_KEY"] == ""
    assert isolated["VITE_PUBLIC_API_BASE_URL"] == ""
    assert child["VITE_PUBLIC_SUPABASE_URL"] == "http://127.0.0.1:54321"
    assert isolated["APP_ENV"] == "test"


def test_owner_dotenv_cannot_be_selected():
    with pytest.raises(ValueError, match=".local"):
        stack.read_local_environment(ROOT / ".env")


def test_database_query_cannot_override_the_validated_loopback_host():
    env = values()
    env["DATABASE_URL"] += "?host=hosted.example"
    with pytest.raises(ValueError, match="DATABASE_URL"):
        stack.build_environment(env, {})


def test_missing_local_values_do_not_fall_back_to_process_environment():
    env = values()
    del env["SUPABASE_SECRET_KEY"]
    with pytest.raises(ValueError, match="SUPABASE_SECRET_KEY"):
        stack.build_environment(env, {"SUPABASE_SECRET_KEY": "hosted-owner-key"})
