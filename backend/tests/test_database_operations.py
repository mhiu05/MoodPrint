import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

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


@pytest.mark.parametrize(
    ("entries", "code"),
    [
        (["", ""], "EMPTY_PASSWORD"),
        (["SECRET-CANARY", "different"], "PASSWORD_MISMATCH"),
        (["SECRET-CANARY\n", "SECRET-CANARY\n"], "INVALID_PASSWORD_CHARACTERS"),
    ],
)
def test_password_entry_reports_local_failure_without_disclosing_input_or_writing(
    monkeypatch, tmp_path, capsys, entries, code
):
    module = script("configure_database")
    path = tmp_path / "backend/.env"
    path.parent.mkdir()
    path.write_text("SUPABASE_URL=https://projectref.supabase.co\n", encoding="utf-8")
    before = path.read_bytes()
    monkeypatch.setattr(module, "ROOT", tmp_path)
    monkeypatch.setattr(module.sys, "stdin", SimpleNamespace(isatty=lambda: True))
    monkeypatch.setattr(
        module.sys,
        "argv",
        ["configure_database", "--host", "verified.pooler.supabase.com", "--username", "postgres.projectref"],
    )
    responses = iter(entries)
    monkeypatch.setattr(module.getpass, "getpass", lambda prompt: next(responses))
    assert module.main() == 1
    output = capsys.readouterr()
    report = json.loads(output.out)
    assert report["errorCode"] == code
    assert report["networkAccessPerformed"] is False
    assert "SECRET-CANARY" not in output.out + output.err
    assert path.read_bytes() == before


def test_password_entry_sanitizes_filesystem_error(monkeypatch, tmp_path, capsys):
    module = script("configure_database")
    path = tmp_path / "backend/.env"
    path.parent.mkdir()
    path.write_text("SUPABASE_URL=https://projectref.supabase.co\n", encoding="utf-8")
    before = path.read_bytes()
    monkeypatch.setattr(module, "ROOT", tmp_path)
    monkeypatch.setattr(module.sys, "stdin", SimpleNamespace(isatty=lambda: True))
    monkeypatch.setattr(
        module.sys,
        "argv",
        ["configure_database", "--host", "verified.pooler.supabase.com", "--username", "postgres.projectref"],
    )
    monkeypatch.setattr(module.getpass, "getpass", lambda prompt: "SECRET-CANARY")

    def denied(*args, **kwargs):
        raise PermissionError("private file content SECRET-CANARY")

    monkeypatch.setattr(Path, "write_text", denied)
    assert module.main() == 1
    output = capsys.readouterr()
    assert json.loads(output.out)["errorCode"] == "FILE_PERMISSION_DENIED"
    assert "SECRET-CANARY" not in output.out + output.err
    assert path.read_bytes() == before


def test_password_entry_refuses_terminal_echo_fallback(monkeypatch, tmp_path, capsys):
    module = script("configure_database")
    monkeypatch.setattr(module, "ROOT", tmp_path)
    monkeypatch.setattr(module.sys, "stdin", SimpleNamespace(isatty=lambda: True))
    monkeypatch.setattr(
        module.sys,
        "argv",
        ["configure_database", "--host", "verified.pooler.supabase.com", "--username", "postgres.projectref"],
    )

    def unsafe(prompt):
        import warnings

        warnings.warn("cannot disable echo", module.getpass.GetPassWarning, stacklevel=2)
        pytest.fail("Echo fallback must not be reached")

    monkeypatch.setattr(module.getpass, "getpass", unsafe)
    assert module.main() == 1
    assert json.loads(capsys.readouterr().out)["errorCode"] == "HIDDEN_INPUT_UNAVAILABLE"
    assert not (tmp_path / "backend/.env").exists()


@pytest.mark.parametrize("mode", ["session", "direct"])
def test_password_entry_round_trips_punctuation_unicode_and_backslashes(tmp_path, mode):
    path = tmp_path / ".env"
    retained = "SUPABASE_URL=https://projectref.supabase.co\nOPENAI_API_KEY='retained'\n"
    path.write_text(retained, encoding="utf-8")
    password = "@:/?#%${reserved} '\\\" !&=+é測"
    script("configure_database").configure(
        path, "verified.pooler.supabase.com", "postgres.projectref", password, mode
    )
    for field in ("DATABASE_URL", "DATABASE_MIGRATION_URL"):
        assert make_url(dotenv_values(path)[field]).password == password
    assert retained in path.read_text(encoding="utf-8")


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


def test_reviewed_upgrade_sql_executes_verbatim_with_supabase_roles(tmp_path):
    """The hosted path runs Alembic's offline SQL as-is, so it must be valid SQL itself."""
    import os
    import subprocess
    import sys

    import psycopg

    from tests.database_target import require_local_test_database

    url = os.getenv("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL must identify a disposable real PostgreSQL database")
    target = require_local_test_database(url)
    runner = script("apply_supabase_review")
    plans = [runner.UPGRADES[key] for key in sorted(runner.UPGRADES)]
    exports = []
    for index, plan in enumerate(plans):
        if index and plans[index - 1].to_revision != plan.from_revision:
            # Revisions without their own hosted plan still have to chain into the next one.
            exports.append(runner.alembic_export(f"{plans[index - 1].to_revision}:{plan.from_revision}"))
        exports.append(runner.alembic_export(f"{plan.from_revision}:{plan.to_revision}"))
    assert all("%%" not in sql for sql in exports)
    name = f"{target.database.removesuffix('_test')}_offline_test"
    admin = target.set(drivername="postgresql", database="postgres").render_as_string(
        hide_password=False
    )
    scratch = target.set(database=name)
    with psycopg.connect(admin, autocommit=True) as db:
        db.execute(f'drop database if exists "{name}"')
        db.execute(f'create database "{name}"')
    try:
        env = {
            **os.environ,
            "DATABASE_URL": "",
            "DATABASE_MIGRATION_URL": scratch.render_as_string(hide_password=False),
        }
        subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", plans[0].from_revision],
            cwd=Path(__file__).resolve().parents[1],
            env=env,
            capture_output=True,
            check=True,
        )
        raw = scratch.set(drivername="postgresql").render_as_string(hide_password=False)
        with psycopg.connect(raw) as db:
            # Roles are cluster-wide; creating them inside this transaction rolls them back.
            db.execute("""DO $r$ BEGIN
              IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='moodprint_runtime') THEN
                CREATE ROLE moodprint_runtime NOLOGIN; END IF;
              IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='anon') THEN
                CREATE ROLE anon NOLOGIN; CREATE ROLE authenticated NOLOGIN;
                CREATE ROLE service_role NOLOGIN; END IF;
            END $r$""")
            for sql in exports:
                body = sql.replace("BEGIN;\n", "", 1).replace("COMMIT;\n", "")
                db.execute(body, prepare=False)
            assert db.execute("select version_num from moodprint.alembic_version").fetchone()[
                0
            ] == plans[-1].to_revision
            tables = [table for plan in plans for table in plan.tables]
            assert (
                db.execute(
                    "select count(*) from pg_policies where schemaname='moodprint' "
                    "and policyname='backend_access' and tablename = any(%s)",
                    (tables,),
                ).fetchone()[0]
                == len(tables)
            )
            assert not db.execute(
                "select has_table_privilege('anon','moodprint.ai_messages','SELECT')"
            ).fetchone()[0]
            identity = "moodprint.delete_provider_identity(uuid)"
            assert not db.execute(
                "select has_function_privilege('anon', %s, 'EXECUTE')", (identity,)
            ).fetchone()[0]
            assert db.execute(
                "select has_function_privilege('moodprint_runtime', %s, 'EXECUTE')", (identity,)
            ).fetchone()[0]
            db.rollback()
    finally:
        with psycopg.connect(admin, autocommit=True) as db:
            db.execute(f'drop database if exists "{name}" with (force)')
