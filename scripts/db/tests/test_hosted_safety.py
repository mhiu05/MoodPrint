"""Catch wrong-project deployment and unintended owner-secret replacement."""

import importlib.util
import sys
from pathlib import Path

import pytest

MODULE_PATH = Path(__file__).parents[1] / "safety.py"
spec = importlib.util.spec_from_file_location("hosted_safety", MODULE_PATH)
assert spec and spec.loader
safety = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = safety
spec.loader.exec_module(safety)


@pytest.mark.parametrize(
    "database_url",
    [
        "postgresql://postgres:secret@db.otherproject.supabase.co:5432/postgres",
        "postgresql://postgres.otherproject:secret@aws-0-ap-southeast-1.pooler.supabase.com:5432/postgres",
        "postgresql://postgres:secret@127.0.0.1:54322/postgres",
    ],
)
def test_wrong_project_database_rejected(database_url: str) -> None:
    with pytest.raises(ValueError, match="target"):
        safety.validate_hosted_target("https://xhlshihobyxrgfqrdafh.supabase.co", database_url)


def test_pooler_project_must_match_url() -> None:
    safety.validate_hosted_target(
        "https://xhlshihobyxrgfqrdafh.supabase.co",
        "postgresql://postgres.xhlshihobyxrgfqrdafh:secret@aws-0-ap-southeast-1.pooler.supabase.com:5432/postgres",
    )


def test_env_write_preserves_owner_values_and_comments(tmp_path: Path) -> None:
    env = tmp_path / ".env"
    env.write_text(
        "# owner values\nSUPABASE_DB_URL='owner-secret'\nOPENAI_API_KEY=owner-key\n",
        encoding="utf-8",
    )
    safety.write_generated_database_url(
        env, "postgresql+asyncpg://moodprint_api:generated@db.host/postgres"
    )
    result = env.read_text(encoding="utf-8")
    assert "SUPABASE_DB_URL='owner-secret'" in result
    assert "OPENAI_API_KEY=owner-key" in result
    assert "# owner values" in result
    assert result.count("DATABASE_URL=") == 1


def test_existing_database_url_is_not_overwritten_without_rotation(tmp_path: Path) -> None:
    env = tmp_path / ".env"
    env.write_text("DATABASE_URL=owner-value\n", encoding="utf-8")
    with pytest.raises(ValueError, match="rotate"):
        safety.write_generated_database_url(env, "generated")
    assert env.read_text(encoding="utf-8") == "DATABASE_URL=owner-value\n"


def test_owner_admin_url_cannot_be_overwritten_even_with_rotation(tmp_path: Path) -> None:
    env = tmp_path / ".env"
    original = "DATABASE_URL=postgresql://postgres:owner-secret@db.project/postgres\n"
    env.write_text(original, encoding="utf-8")
    with pytest.raises(ValueError, match="owner"):
        safety.write_generated_database_url(env, "generated", rotate=True)
    assert env.read_text(encoding="utf-8") == original


def test_similar_role_name_is_not_generated_runtime_credential(tmp_path: Path) -> None:
    env = tmp_path / ".env"
    original = "DATABASE_URL=postgresql://moodprint_api_backup:owner-secret@db.project/postgres\n"
    env.write_text(original, encoding="utf-8")
    with pytest.raises(ValueError, match="owner"):
        safety.write_generated_database_url(env, "generated", rotate=True)
    assert env.read_text(encoding="utf-8") == original


def test_unknown_hosted_migration_is_rejected() -> None:
    with pytest.raises(ValueError, match="history"):
        safety.check_history(
            [Path("20261107000001_f0_profiles.sql")], [("20261106000001", "ad_hoc")]
        )


def test_hosted_migration_name_must_match_committed_filename() -> None:
    with pytest.raises(ValueError, match="history"):
        safety.check_history(
            [Path("20261107000001_f0_profiles.sql")], [("20261107000001", "different")]
        )


def test_owner_admin_database_url_is_in_memory_fallback(tmp_path: Path, monkeypatch) -> None:
    """An existing correctly targeted postgres connection can drive migration scripts."""
    url = (
        "postgresql://postgres:synthetic-password@db.xhlshihobyxrgfqrdafh.supabase.co:5432/postgres"
    )
    content = "SUPABASE_URL=https://xhlshihobyxrgfqrdafh.supabase.co\nDATABASE_URL=" + url + "\n"
    path = tmp_path / ".env"
    path.write_text(content, encoding="utf-8")
    monkeypatch.setattr(safety, "ROOT", tmp_path)
    monkeypatch.delenv("SUPABASE_DB_URL", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    values = safety.load_hosted_env()
    assert values["SUPABASE_DB_URL"] == url
    assert path.read_text(encoding="utf-8") == content


def test_runtime_login_is_not_privileged_database_fallback(tmp_path: Path, monkeypatch) -> None:
    path = tmp_path / ".env"
    path.write_text(
        "SUPABASE_URL=https://xhlshihobyxrgfqrdafh.supabase.co\n"
        "DATABASE_URL=postgresql://moodprint_api:synthetic-password@db.xhlshihobyxrgfqrdafh.supabase.co:5432/postgres\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(safety, "ROOT", tmp_path)
    for name in ("SUPABASE_DB_URL", "DATABASE_URL", "SUPABASE_URL"):
        monkeypatch.delenv(name, raising=False)
    with pytest.raises(ValueError, match="SUPABASE_DB_URL"):
        safety.load_hosted_env()


def test_direct_target_rejects_non_admin_role() -> None:
    with pytest.raises(ValueError, match="privileged"):
        safety.validate_hosted_target(
            "https://xhlshihobyxrgfqrdafh.supabase.co",
            "postgresql://service_role:synthetic-password@db.xhlshihobyxrgfqrdafh.supabase.co:5432/postgres",
        )
