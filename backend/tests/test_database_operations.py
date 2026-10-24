import importlib.util
import json
from pathlib import Path

import pytest
from dotenv import dotenv_values
from pydantic import ValidationError
from sqlalchemy.engine import make_url

from app.core.config import Settings


def script(name):
    path = Path(__file__).resolve().parents[2] / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize(
    "target",
    [
        "postgresql://user:SECRET-CANARY@localhost/postgreshttps://wrong.supabase.co",
        "postgresql://user:SECRET-CANARY@localhost:99999/postgres",
        "postgresql://user:SECRET-CANARY@localhost/",
    ],
)
def test_invalid_database_url_is_rejected_without_disclosing_password(target):
    with pytest.raises(ValidationError) as error:
        Settings(_env_file=None, database_url=target)
    assert "SECRET-CANARY" not in str(error.value)


def test_local_password_entry_round_trips_reserved_symbols_and_preserves_other_values(tmp_path):
    path = tmp_path / ".env"
    retained = "OPENAI_API_KEY='untouched-canary'\nOPENAI_MODEL=existing-model\nSESSION_SECRET='existing-secret'\nAI_ENABLED=false\n"
    path.write_text("SUPABASE_URL=https://projectref.supabase.co\n" + retained, encoding="utf-8")
    password = "@:/?#%${reserved} ' +"
    updated = script("configure_database").configure(
        path, "verified.pooler.supabase.com", "postgres.projectref", password, "direct"
    )
    assert retained in path.read_text(encoding="utf-8")
    values = dotenv_values(path)
    for field in ("DATABASE_URL", "DATABASE_MIGRATION_URL"):
        target = make_url(values[field])
        assert target.password == password
        assert target.database == "postgres" and target.query["sslmode"] == "require"
    assert make_url(values["DATABASE_MIGRATION_URL"]).host == "db.projectref.supabase.co"
    before = path.read_bytes()
    with pytest.raises(ValueError):
        script("configure_database").configure(
            path, "verified.pooler.supabase.com", "postgres.other", password, "session"
        )
    assert path.read_bytes() == before
    assert "SECRET" not in json.dumps(updated)


def test_diagnostic_categories_separate_permissions_from_authentication_without_error_text():
    inspect = script("inspect_database")

    class PermissionDenied(Exception):
        sqlstate = "42501"

    details = inspect.error_details(PermissionDenied("private SQL and SECRET-CANARY"))
    assert details["errorCategory"] == "permission"
    assert "SECRET-CANARY" not in json.dumps(details)
    assert (
        inspect.error_details(Exception("password authentication failed: SECRET-CANARY"))[
            "errorCategory"
        ]
        == "authentication"
    )


def test_migration_apply_rejects_changed_sql_before_running_alembic_or_connecting(monkeypatch):
    runner = script("apply_supabase_review")

    def forbidden(*args, **kwargs):
        raise AssertionError("No subprocess/network is allowed after hash mismatch")

    monkeypatch.setattr(runner.subprocess, "run", forbidden)
    monkeypatch.setattr(runner.psycopg, "connect", forbidden)
    with pytest.raises(ValueError, match="Approved SQL hash"):
        runner.review_artifact("0" * 64)


def test_migration_target_rejects_wrong_project_owner_port_and_missing_tls():
    runner = script("apply_supabase_review")
    public = "https://roznanxbiyqybjpvtilq.supabase.co"
    good = "postgresql://postgres.roznanxbiyqybjpvtilq:SECRET-CANARY@aws-0-ap-northeast-1.pooler.supabase.com:5432/postgres?sslmode=require"
    assert make_url(runner.validate_target(good, public)).port == 5432
    for raw in (
        good.replace(":5432", ":6543"),
        good.replace("sslmode=require", "sslmode=prefer"),
        good.replace("postgres.roznanxbiyqybjpvtilq", "postgres.other"),
        good.replace("aws-0-ap-northeast-1.pooler.supabase.com", "untrusted.example"),
    ):
        with pytest.raises(ValueError) as error:
            runner.validate_target(raw, public)
        assert "SECRET-CANARY" not in str(error.value)
