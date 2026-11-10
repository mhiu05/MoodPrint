import re
from dataclasses import fields
from pathlib import Path

import pytest
from pydantic import ValidationError


@pytest.fixture(autouse=True)
def clean_environment(monkeypatch):
    names = (
        "APP_ENV",
        "DATABASE_URL",
        "SUPABASE_URL",
        "SUPABASE_PUBLISHABLE_KEY",
        "SUPABASE_SECRET_KEY",
        "OPENAI_API_KEY",
        "SUPABASE_DB_URL",
    )
    for name in names:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("APP_ENV", "test")


def settings(**overrides):
    from moodprint_shared.env import EnvSettings

    data = dict(
        supabase_url="http://127.0.0.1:54321",
        supabase_publishable_key="test-publishable",
        supabase_secret_key="synthetic-secret",
        database_url="postgresql://u:p@localhost/db",
    )
    data.update(overrides)
    return EnvSettings(**data)


def test_every_model_setting_is_gpt_6_luna():
    from moodprint_shared.config import AppConfig

    cfg = AppConfig()
    for entry in fields(cfg.agent):
        if "model" in entry.name:
            assert getattr(cfg.agent, entry.name) == "gpt-6-luna"
    assert cfg.openai_model == "gpt-6-luna"


def test_no_other_model_literal_in_source():
    root = Path(__file__).resolve().parents[2]
    for directory in ("shared/src", "agent/src", "backend/app"):
        for path in (root / directory).rglob("*.py"):
            literals = re.findall(
                r"[\"']((?:gpt-[\w.-]+|o\d[\w.-]*))[\"']", path.read_text(encoding="utf-8")
            )
            assert set(literals) <= {"gpt-6-luna"}, path


def test_missing_required_var_names_the_var_without_value():
    from moodprint_shared.env import EnvSettings

    with pytest.raises(ValidationError) as caught:
        EnvSettings(supabase_url="http://127.0.0.1", supabase_secret_key="private-sentinel")
    assert "DATABASE_URL" in str(caught.value)
    assert "private-sentinel" not in str(caught.value)


def test_secret_not_in_repr():
    value = settings(
        database_url="postgresql://u:private-sentinel@localhost/db",
        supabase_secret_key="private-sentinel",
        openai_api_key="private-sentinel",
    )
    assert "private-sentinel" not in repr(value)


@pytest.mark.parametrize("host", ["remote.example", "127.0.0.1.evil.test", "", "0.0.0.0"])
def test_test_env_rejects_remote_database(host):
    from moodprint_shared.env import UnsafeTestEnvironment

    with pytest.raises(UnsafeTestEnvironment):
        settings(database_url=f"postgresql://u:private-sentinel@{host}/db")


def test_test_env_does_not_read_dotenv(tmp_path):
    dotenv = tmp_path / ".env"
    dotenv.write_text(
        "SUPABASE_URL=https://remote.example\nDATABASE_URL=postgresql://u:p@remote.example/db\n"
        "OPENAI_API_KEY=dotenv-must-not-be-read\n"
    )
    value = settings(_env_file=dotenv)
    assert value.supabase_url == "http://127.0.0.1:54321"
    assert value.openai_api_key is None


@pytest.mark.parametrize(
    "field", ["database_url", "supabase_secret_key", "supabase_publishable_key", "supabase_url"]
)
def test_empty_required_values_are_rejected(field):
    with pytest.raises(ValidationError):
        settings(**{field: ""})


def test_cors_rejects_wildcard():
    with pytest.raises(ValidationError):
        settings(cors_allowed_origins=["*"])


def test_cors_accepts_process_comma_list(monkeypatch):
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "http://localhost:5173, http://127.0.0.1:5178")
    assert settings().cors_allowed_origins == ["http://localhost:5173", "http://127.0.0.1:5178"]


def test_settings_cache_can_be_cleared(monkeypatch):
    from moodprint_shared.env import get_settings

    monkeypatch.setenv("SUPABASE_URL", "http://127.0.0.1:54321")
    monkeypatch.setenv("SUPABASE_PUBLISHABLE_KEY", "synthetic")
    monkeypatch.setenv("SUPABASE_SECRET_KEY", "synthetic")
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@localhost/db")
    get_settings.cache_clear()
    assert get_settings() is get_settings()
    get_settings.cache_clear()


def test_env_example_lists_every_field():
    from moodprint_shared.env import EnvSettings

    content = (Path(__file__).resolve().parents[2] / ".env.example").read_text()
    names = set(re.findall(r"^([A-Z_]+)=", content, re.MULTILINE))
    assert {
        name.upper() for name in EnvSettings.model_fields if name != "auth_test_jwt_secret"
    } <= names


def test_env_example_has_no_values_for_secrets():
    from moodprint_shared.env import EnvSettings
    from pydantic import SecretStr

    content = (Path(__file__).resolve().parents[2] / ".env.example").read_text()
    values = dict(re.findall(r"^([A-Z_]+)=(.*)$", content, re.MULTILINE))
    for name, field in EnvSettings.model_fields.items():
        if name != "auth_test_jwt_secret" and (
            field.annotation is SecretStr or "SecretStr" in str(field.annotation)
        ):
            value = values[name.upper()].strip()
            assert value in ("", '""', "''") or re.search(r"<[^>]+>", value), name
