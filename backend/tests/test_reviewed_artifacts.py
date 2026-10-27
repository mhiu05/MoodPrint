"""The hash-pinned SQL approvals the hosted-database scripts consume must stay present and unaltered.

CI runs scripts/check_reviewed_artifacts.py from a clean checkout; these tests pin its behavior
against both the real tree and small synthetic trees. Nothing here connects to a database.
"""

import hashlib
import json
import shutil
from pathlib import Path

import pytest

from tests.test_database_operations import script

ROOT = Path(__file__).resolve().parents[2]
DIRECTORY = "deploy/supabase/reviewed-sql"
SCRIPTS = (
    "apply_supabase_review.py",
    "provision_supabase_runtime.py",
    "verify_migration_review.py",
    "prepare_supabase_migration.py",
)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.fixture
def tree(tmp_path):
    """A copy of only what the checker is allowed to read: the pinned directory and its consumers."""
    shutil.copytree(ROOT / DIRECTORY, tmp_path / DIRECTORY)
    (tmp_path / "scripts").mkdir()
    for name in SCRIPTS:
        shutil.copy(ROOT / "scripts" / name, tmp_path / "scripts" / name)
    helper = Path("backend/app/infrastructure/database/provider_session.sql")
    (tmp_path / helper).parent.mkdir(parents=True)
    shutil.copy(ROOT / helper, tmp_path / helper)
    return tmp_path


def run(root: Path) -> dict:
    return script("check_reviewed_artifacts").check(root)


def manifest(root: Path) -> dict:
    return json.loads((root / DIRECTORY / "MANIFEST.json").read_text(encoding="utf-8"))


def test_tracked_tree_passes_and_checks_a_real_set():
    report = run(ROOT)
    assert report["errors"] == []
    assert report["status"] == "PASS"
    # Non-vacuous: every approval some script consumes is present, not an empty set.
    assert report["artifactCount"] >= 9
    assert report["referencedCount"] == report["artifactCount"]


def test_manifest_hashes_match_the_files_on_disk():
    entries = manifest(ROOT)["artifacts"]
    assert entries
    for entry in entries:
        assert sha(ROOT / DIRECTORY / entry["path"]) == entry["sha256"]


def test_scripts_resolve_their_approvals_inside_the_pinned_directory():
    apply = script("apply_supabase_review")
    runtime = script("provision_supabase_runtime")
    pinned = (ROOT / DIRECTORY).resolve()
    paths = [apply.REVIEW, apply.AUTH_REVIEW, runtime.REVIEW] + [plan.review for plan in apply.UPGRADES.values()]
    for path in paths:
        assert path.is_file(), path
        assert path.resolve().parent == pinned


def test_every_upgrade_approval_matches_the_current_alembic_offline_export():
    # Offline: Alembic renders SQL without connecting. A drifted migration or SQL file fails here.
    apply = script("apply_supabase_review")
    for key, plan in sorted(apply.UPGRADES.items()):
        digest, sql = apply.review_upgrade_artifact(plan, sha(plan.review))
        assert digest == sha(plan.review), key
        assert sql


def test_initialization_approvals_match_the_alembic_0001_0005_export():
    apply = script("apply_supabase_review")
    for path in (apply.REVIEW, apply.AUTH_REVIEW):
        digest, _ = apply.review_artifact(sha(path), path)
        assert digest == sha(path)


def test_missing_manifest_fails(tree):
    (tree / DIRECTORY / "MANIFEST.json").unlink()
    assert any("manifest" in error.lower() for error in run(tree)["errors"])


def test_empty_manifest_fails_instead_of_passing_vacuously(tree):
    path = tree / DIRECTORY / "MANIFEST.json"
    path.write_text(json.dumps({"version": 1, "artifacts": []}), encoding="utf-8")
    report = run(tree)
    assert report["status"] == "FAIL"
    assert any("empty" in error.lower() for error in report["errors"])


def test_missing_approved_file_fails(tree):
    (tree / DIRECTORY / "0011-review.sql").unlink()
    errors = run(tree)["errors"]
    assert any("0011-review.sql" in error and "missing" in error.lower() for error in errors)


def test_altered_approved_file_fails_even_by_one_byte(tree):
    target = tree / DIRECTORY / "supabase-runtime-login-review.sql"
    target.write_bytes(target.read_bytes() + b"\n")
    errors = run(tree)["errors"]
    assert any("supabase-runtime-login-review.sql" in error and "sha256" in error.lower() for error in errors)


def test_crlf_conversion_is_detected_as_alteration(tree):
    target = tree / DIRECTORY / "0012-review.sql"
    target.write_bytes(target.read_bytes().replace(b"\n", b"\r\n"))
    assert any("0012-review.sql" in error for error in run(tree)["errors"])


def test_unlisted_sql_in_the_pinned_directory_fails(tree):
    (tree / DIRECTORY / "new-unreviewed.sql").write_text("select 1;\n", encoding="utf-8")
    assert any("new-unreviewed.sql" in error and "not in the manifest" in error for error in run(tree)["errors"])


def test_manifest_entry_cannot_escape_the_directory(tree):
    path = tree / DIRECTORY / "MANIFEST.json"
    data = manifest(tree)
    data["artifacts"][0]["path"] = "../../../scripts/apply_supabase_review.py"
    path.write_text(json.dumps(data), encoding="utf-8")
    assert any("invalid" in error.lower() for error in run(tree)["errors"])


def test_duplicate_manifest_entries_fail(tree):
    path = tree / DIRECTORY / "MANIFEST.json"
    data = manifest(tree)
    data["artifacts"].append(dict(data["artifacts"][0]))
    path.write_text(json.dumps(data), encoding="utf-8")
    assert any("duplicate" in error.lower() for error in run(tree)["errors"])


def test_script_reference_to_an_unlisted_sql_file_fails(tree):
    target = tree / "scripts" / "provision_supabase_runtime.py"
    target.write_text(target.read_text(encoding="utf-8") + '\nEXTRA = "unlisted-review.sql"\n', encoding="utf-8")
    assert any("unlisted-review.sql" in error for error in run(tree)["errors"])


def test_script_reference_to_retired_docs_sql_fails(tree):
    target = tree / "scripts" / "apply_supabase_review.py"
    target.write_text(target.read_text(encoding="utf-8") + '\nOLD = "docs/plans/validation-artifacts/x.sql"\n', encoding="utf-8")
    assert any("retired" in error.lower() for error in run(tree)["errors"])


def test_orphan_approval_nobody_consumes_fails(tree):
    for name in SCRIPTS:
        target = tree / "scripts" / name
        target.write_text(target.read_text(encoding="utf-8").replace("0014-review.sql", "0014-renamed.sql"), encoding="utf-8")
    errors = run(tree)["errors"]
    assert any("0014-review.sql" in error and "no script" in error.lower() for error in errors)


def test_missing_application_source_a_script_cross_checks_fails(tree):
    (tree / "backend/app/infrastructure/database/provider_session.sql").unlink()
    assert any("provider_session.sql" in error and "does not exist" in error for error in run(tree)["errors"])


def test_missing_consumer_script_fails(tree):
    (tree / "scripts" / "provision_supabase_runtime.py").unlink()
    assert any("provision_supabase_runtime.py" in error and "missing" in error.lower() for error in run(tree)["errors"])


def test_command_line_exit_status_reflects_the_result(tree, capsys):
    module = script("check_reviewed_artifacts")
    assert module.main(["--root", str(ROOT)]) == 0
    (tree / DIRECTORY / "0013-review.sql").unlink()
    assert module.main(["--root", str(tree)]) == 1
    assert "0013-review.sql" in capsys.readouterr().out
