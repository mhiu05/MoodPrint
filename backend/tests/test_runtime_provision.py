import hashlib
import secrets

import psycopg
import pytest
from dotenv import dotenv_values
from sqlalchemy.engine import make_url

from tests.test_database_operations import script


def test_runtime_configuration_preserves_owner_and_other_secrets(tmp_path):
    module = script("provision_supabase_runtime")
    path = tmp_path / ".env"
    owner = "postgresql://postgres.roznanxbiyqybjpvtilq:owner-canary@aws-0-ap-northeast-1.pooler.supabase.com:5432/postgres?sslmode=require"
    original = (
        "SUPABASE_URL=https://roznanxbiyqybjpvtilq.supabase.co\n"
        f"DATABASE_URL='{owner}'\nDATABASE_MIGRATION_URL='{owner}'\n"
        "OPENAI_API_KEY='retain-canary'\nOPENAI_MODEL=retain-model\n"
        "SESSION_SECRET='retain-session'\nDATABASE_POOL_MODE=session\n"
    )
    path.write_text(original, encoding="utf-8")
    password = "runtime@'\\é+%canary"
    content = module.runtime_configuration(path, password)
    path.write_text(content, encoding="utf-8")
    after = dotenv_values(path)
    runtime = make_url(after["DATABASE_URL"])
    assert runtime.username == "moodprint_backend.roznanxbiyqybjpvtilq"
    assert runtime.password == password and runtime.query["sslmode"] == "require"
    assert after["DATABASE_MIGRATION_URL"] == owner
    assert after["OPENAI_API_KEY"] == "retain-canary"
    assert after["OPENAI_MODEL"] == "retain-model" and after["SESSION_SECRET"] == "retain-session"


def test_runtime_review_requires_exact_hash_before_any_database_access(monkeypatch):
    module = script("provision_supabase_runtime")

    def forbidden(*args, **kwargs):
        raise AssertionError("No connection allowed for a rejected approval")

    monkeypatch.setattr(module.psycopg, "connect", forbidden)
    with pytest.raises(ValueError, match="hash"):
        module.review("0" * 64)
    approved = hashlib.sha256(module.REVIEW.read_bytes()).hexdigest()
    digest, sql = module.review(approved)
    assert digest == approved and sql.count("PASSWORD {runtime_password}") == 1


def test_runtime_configuration_rejects_foreign_target_without_writing(tmp_path):
    module = script("provision_supabase_runtime")
    path = tmp_path / ".env"
    original = "SUPABASE_URL=https://other.supabase.co\nDATABASE_MIGRATION_URL=postgresql://localhost/other\n"
    path.write_text(original, encoding="utf-8")
    with pytest.raises(ValueError):
        module.runtime_configuration(path, "runtime-canary")
    assert path.read_text(encoding="utf-8") == original


@pytest.mark.postgres
async def test_runtime_role_sql_uses_scram_inherits_groups_and_cannot_create_tables(database):
    from psycopg import sql

    from tests.database_target import require_local_test_database

    module = script("provision_supabase_runtime")
    require_local_test_database(database.url.render_as_string(hide_password=False))
    raw = database.url.set(drivername="postgresql").render_as_string(hide_password=False)
    _, template = module.review()
    with psycopg.connect(raw, autocommit=True) as db:
        db.execute("BEGIN")
        try:
            db.execute("CREATE ROLE moodprint_runtime NOLOGIN NOSUPERUSER NOBYPASSRLS")
            db.execute("CREATE ROLE moodprint_app NOLOGIN NOSUPERUSER NOBYPASSRLS")
            db.execute("GRANT moodprint_runtime TO moodprint_app")
            db.execute("GRANT USAGE ON SCHEMA moodprint TO moodprint_runtime")
            db.execute("GRANT SELECT ON moodprint.users TO moodprint_runtime")
            db.execute("GRANT EXECUTE ON FUNCTION moodprint.is_provider_session_active(uuid,uuid) TO moodprint_runtime")
            password = secrets.token_urlsafe(32)
            verifier = db.pgconn.encrypt_password(password.encode(), module.ROLE.encode(), b"scram-sha-256").decode()
            # Keep the exact reviewed statements inside the test's outer rollback.
            body = template.replace("BEGIN;", "").replace("COMMIT;", "")
            db.execute(sql.SQL(body).format(runtime_password=sql.Literal(verifier)), prepare=False)
            role = db.execute("""select rolcanlogin,not rolsuper and not rolbypassrls
                and not rolcreaterole and not rolcreatedb,rolconnlimit
                from pg_roles where rolname='moodprint_backend'""").fetchone()
            assert role == (True, True, 10)
            assert db.execute("select pg_has_role('moodprint_backend','moodprint_runtime','USAGE')").fetchone()[0]
            db.execute("SET LOCAL ROLE moodprint_backend")
            assert db.execute("select count(*) from moodprint.users").fetchone()[0] == 0
            assert not db.execute("select has_schema_privilege(current_user,'moodprint','CREATE')").fetchone()[0]
            assert not db.execute("select has_schema_privilege(current_user,'auth','USAGE')").fetchone()[0]
            checks = module.runtime_checks(db)
            assert checks["roleMatches"] and checks["leastPrivilege"]
            assert checks["rawAuthDenied"] and checks["privateHelperRejectsUnknownSession"]
        finally:
            db.execute("ROLLBACK")
        assert not db.execute("select exists(select 1 from pg_roles where rolname='moodprint_backend')").fetchone()[0]
