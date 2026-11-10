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


@pytest.mark.parametrize("offset", [0, 100, 200, 300])
def test_worktree_ports_and_output_are_isolated(offset):
    child = stack.build_environment(values(), {}, name=f"probe-{offset}", offset=offset)
    assert child["E2E_BASE_URL"] == f"http://127.0.0.1:{5178 + offset}"
    assert child["E2E_API_URL"] == f"http://127.0.0.1:{8008 + offset}"
    assert child["E2E_MAIL_URL"] == f"http://127.0.0.1:{54324 + offset}"
    assert child["MOODPRINT_STACK_NAME"] == f"probe-{offset}"
    assert child["MOODPRINT_PORT_OFFSET"] == str(offset)
    assert stack.output_directory(child).name == f"probe-{offset}-{offset}"


@pytest.mark.parametrize("name,offset", [("../owner", 100), ("kb", -1), ("ag", 9001)])
def test_bad_stack_identity_is_rejected(name, offset):
    with pytest.raises(ValueError):
        stack.build_environment(values(), {}, name=name, offset=offset)


def test_explicit_test_url_cannot_select_remote_target():
    with pytest.raises(ValueError, match="loopback"):
        stack.build_environment(values(), {}, frontend_url="https://hosted.example")


def test_optional_hook_skips_only_exit_two(monkeypatch, tmp_path):
    import subprocess

    hook = [{"name": "future-seed", "cmd": ["python", "seed"], "optional": True}]
    monkeypatch.setattr(
        stack.subprocess, "run", lambda *a, **k: subprocess.CompletedProcess(a[0], 2)
    )
    stack.run_hooks(hook, {}, tmp_path)
    monkeypatch.setattr(
        stack.subprocess, "run", lambda *a, **k: subprocess.CompletedProcess(a[0], 1)
    )
    with pytest.raises(RuntimeError, match="future-seed"):
        stack.run_hooks(hook, {}, tmp_path)


def test_lite_stack_and_redirects_are_worktree_specific(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location(
        "supabase_worktree_probe", ROOT / "scripts/dev/supabase_worktree.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    source = tmp_path / "supabase"
    source.mkdir()
    (source / "config.toml").write_text((ROOT / "supabase/config.toml").read_text())
    (source / "seed.sql").write_text("")
    (source / "migrations").mkdir()
    (source / "tests").mkdir()
    monkeypatch.setattr(module, "ROOT", tmp_path)
    path = module.prepare("kb", 100, lite=True)
    import tomllib

    config = tomllib.loads((path / "supabase/config.toml").read_text())
    assert config["project_id"] == "moodprint-kb"
    assert config["db"]["port"] == 54422
    assert config["studio"]["enabled"] is False
    assert config["auth"]["site_url"] == "http://127.0.0.1:5278"
    assert "http://127.0.0.1:5278" in config["auth"]["additional_redirect_urls"]


def test_prepare_keeps_lite_and_replaces_removed_stack_files(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location(
        "supabase_worktree_sync", ROOT / "scripts/dev/supabase_worktree.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    source = tmp_path / "supabase"
    source.mkdir()
    (source / "config.toml").write_text((ROOT / "supabase/config.toml").read_text())
    (source / "seed.sql").write_text("")
    (source / "migrations").mkdir()
    (source / "tests").mkdir()
    (source / "migrations" / "old.sql").write_text("select 1;")
    (source / "tests" / "old.sql").write_text("select 1;")
    monkeypatch.setattr(module, "ROOT", tmp_path)
    module.prepare("kb", 100, lite=True)
    (source / "migrations" / "old.sql").unlink()
    (source / "tests" / "old.sql").unlink()
    (source / "migrations" / "new.sql").write_text("select 2;")
    path = module.prepare("kb", 100)
    import tomllib

    config = tomllib.loads((path / "supabase/config.toml").read_text())
    assert config["studio"]["enabled"] is False
    assert {item.name for item in (path / "supabase/migrations").iterdir()} == {"new.sql"}
    assert list((path / "supabase/tests").iterdir()) == []
    import os
    import subprocess

    original = (source / "config.toml").read_text()
    link = tmp_path / ".local/stacks/ag"
    link.parent.mkdir(parents=True, exist_ok=True)
    if os.name == "nt":
        subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(link), str(source)],
            check=True,
            capture_output=True,
        )
    else:
        link.symlink_to(source, target_is_directory=True)
    with pytest.raises(ValueError, match="symlink|escapes"):
        module.prepare("ag", 200, lite=True)
    assert (source / "config.toml").read_text() == original
