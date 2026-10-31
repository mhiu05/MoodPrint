"""Pending SQL is reviewable without any remote mutation or historical approval change."""

import hashlib
import importlib
import os
import sys
from pathlib import Path

import psycopg
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))


def test_pending_review_never_executes_remote_or_overwrites_approval(tmp_path, monkeypatch):
    prepare = importlib.import_module("prepare_guest_migration_review")
    verify = importlib.import_module("verify_guest_migration_review")
    approved = ROOT / "deploy/supabase/reviewed-sql"
    before = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in approved.iterdir() if p.is_file()}
    for url in ("postgresql+psycopg://hosted.invalid/example_test", "postgresql+psycopg://127.0.0.1/production", "sqlite:///local_test"):
        with pytest.raises(ValueError):
            verify.require_target(url)
    called = []
    monkeypatch.setattr(prepare, "migration_sql", lambda *args: called.append(args) or "BEGIN;\nCOMMIT;\n")
    for path in (approved / "pending.sql", approved / "MANIFEST.json", ROOT / ".gitignore"):
        with pytest.raises(ValueError):
            prepare.prepare(path)
    assert called == []
    output = tmp_path / "pending.sql"
    result = prepare.prepare(output)
    assert result["remoteExecuted"] is False
    assert result["sha256"] == hashlib.sha256(output.read_bytes()).hexdigest()
    with pytest.raises(FileExistsError):
        prepare.prepare(output)
    after = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in approved.iterdir() if p.is_file()}
    assert before == after


def test_verifier_rejects_modified_sql_before_connecting(tmp_path, monkeypatch):
    verify = importlib.import_module("verify_guest_migration_review")
    monkeypatch.setattr(verify, "migration_sql", lambda *args: "BEGIN;\nSELECT 1;\nCOMMIT;\n")
    output = tmp_path / "altered.sql"
    output.write_text("COMMIT; DROP SCHEMA moodprint CASCADE;", encoding="utf-8")
    with pytest.raises(ValueError, match="match"):
        verify.verify(output, "postgresql+psycopg://127.0.0.1/review_test")


@pytest.mark.postgres
def test_verifier_refuses_nonempty_public_schema(tmp_path):
    verify = importlib.import_module("verify_guest_migration_review")
    raw = os.environ.get("TEST_DATABASE_URL")
    if not raw:
        pytest.skip("Explicit disposable local DB required")
    from tests.database_target import owned_scratch_database

    with owned_scratch_database(raw) as scratch:
        with psycopg.connect(scratch.set(drivername="postgresql").render_as_string(hide_password=False), autocommit=True) as db:
            db.execute("create table public.synthetic_existing_data(value integer); insert into public.synthetic_existing_data values (42)")
        pending = tmp_path / "pending.sql"
        pending.write_bytes(verify.migration_sql().encode())
        with pytest.raises(ValueError, match="empty"):
            verify.verify(pending, scratch.render_as_string(hide_password=False))
        with psycopg.connect(scratch.set(drivername="postgresql").render_as_string(hide_password=False)) as db:
            assert db.execute("select value from public.synthetic_existing_data").fetchone() == (42,)
