"""The destructive retirement package is reviewable without enabling hosted execution."""

import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def generator():
    path = ROOT / "scripts/prepare_0020_review.py"
    spec = importlib.util.spec_from_file_location("prepare_0020_review", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_real_package_exports_exact_0019_to_0020_and_keeps_hosted_execution_closed(tmp_path):
    module = generator()
    output = tmp_path / "retirement.sql"
    result = module.prepare(output)
    sql = output.read_bytes()
    assert b"DROP TABLE moodprint.private_items" in sql
    assert b"DELETE FROM moodprint.memory_proposals WHERE purpose = 'private_item'" in sql
    assert b"SET status = 'expired', text = '', version = version + 1" in sql
    assert b"DROP COLUMN source_id" in sql
    assert b"UPDATE moodprint.alembic_version SET version_num='0020_private_profile_retirement'" in sql
    assert result["fromRevision"] == "0019_journal"
    assert result["toRevision"] == "0020_private_profile_retirement"
    assert result["sha256"] == hashlib.sha256(sql).hexdigest()
    assert result["bytes"] == len(sql)
    assert result["remoteExecuted"] is False
    assert result["hostedExecutionAllowed"] is False
    assert result["requiredGates"]["compatibleBackend"] == "NOT_VERIFIED"
    assert result["requiredGates"]["hostedBackupRestored"] == "NOT_VERIFIED"
    assert json.loads(output.with_suffix(".json").read_text()) == result


@pytest.mark.parametrize("name", [".gitignore", "deploy/supabase/reviewed-sql/0020-review.sql"])
def test_rejects_protected_outputs_before_export(name, monkeypatch):
    module = generator()
    monkeypatch.setattr(module, "migration_sql", lambda: pytest.fail("No export permitted"))
    with pytest.raises(ValueError):
        module.prepare(ROOT / name)


def test_never_overwrites_a_package_or_its_metadata(tmp_path, monkeypatch):
    module = generator()
    sql = module.migration_sql()
    monkeypatch.setattr(module, "migration_sql", lambda: sql)
    output = tmp_path / "retirement.sql"
    module.prepare(output)
    before = output.read_bytes(), output.with_suffix(".json").read_bytes()
    with pytest.raises(FileExistsError):
        module.prepare(output)
    assert before == (output.read_bytes(), output.with_suffix(".json").read_bytes())


def test_rejects_incorrect_range_without_writing_package(tmp_path, monkeypatch):
    module = generator()
    monkeypatch.setattr(module, "migration_sql", lambda: "BEGIN;\nSELECT 1;\nCOMMIT;\n")
    output = tmp_path / "retirement.sql"
    with pytest.raises(ValueError, match="0019.*0020"):
        module.prepare(output)
    assert not output.exists()
    assert not output.with_suffix(".json").exists()


def test_offline_export_does_not_inherit_hosted_database_or_provider_configuration(monkeypatch):
    module = generator()
    monkeypatch.setenv("DATABASE_URL", "hosted-secret-canary")
    monkeypatch.setenv("DATABASE_MIGRATION_URL", "hosted-secret-canary")
    monkeypatch.setenv("SUPABASE_URL", "https://hosted-secret-canary.invalid")
    monkeypatch.setenv("OPENAI_API_KEY", "hosted-secret-canary")
    real_run = module.subprocess.run
    captured = []

    def inspect(args, **kwargs):
        captured.append(kwargs["env"])
        assert args[-1] == "--sql"
        assert args[-2] == "0019_journal:0020_private_profile_retirement"
        return real_run(args, **kwargs)

    monkeypatch.setattr(module.subprocess, "run", inspect)
    assert "DROP TABLE moodprint.private_items" in module.migration_sql()
    assert captured
    for key in ("DATABASE_URL", "DATABASE_MIGRATION_URL", "SUPABASE_URL", "OPENAI_API_KEY"):
        assert "hosted-secret-canary" not in captured[0][key]


def test_tracked_pending_package_is_exact_export_with_matching_hash():
    module = generator()
    path = module.PENDING / "0020-review.sql"
    content = path.read_bytes()
    metadata = json.loads(path.with_suffix(".json").read_text())
    assert content == module.migration_sql().encode("utf-8")
    assert metadata["sha256"] == hashlib.sha256(content).hexdigest()
    assert metadata["bytes"] == len(content)
    assert metadata["hostedExecutionAllowed"] is False
