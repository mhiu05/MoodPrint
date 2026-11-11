"""Catch wrong-project deployment and unintended owner-secret replacement."""

import importlib.util
import json
import sys
from pathlib import Path

import pytest

MODULE_PATH = Path(__file__).parents[1] / "safety.py"
spec = importlib.util.spec_from_file_location("hosted_safety", MODULE_PATH)
assert spec and spec.loader
safety = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = safety
spec.loader.exec_module(safety)


def test_phase1_deploy_cannot_use_a_phase0_receipt(tmp_path):
    local = tmp_path / ".local"
    local.mkdir()
    (local / "phase0-gate.json").write_text(
        json.dumps(
            {
                "commit": "verified-head",
                "passed": True,
                "scope": "local",
                "checks": [{"returncode": 0}] * 8,
            }
        )
    )
    with pytest.raises(ValueError, match="Phase 1"):
        safety.require_local_gate(tmp_path, "verified-head", phase=1)


def test_phase1_deploy_requires_e2e_and_foundation_regression(tmp_path):
    local = tmp_path / ".local"
    local.mkdir()
    receipt = {
        "commit": "verified-head",
        "passed": True,
        "scope": "local_phase1",
        "checks": [{"command": ["python", "scripts/check.py"], "returncode": 0}] * 8,
    }
    path = local / "phase1-gate.json"
    path.write_text(json.dumps(receipt))
    with pytest.raises(ValueError, match="E2E"):
        safety.require_local_gate(tmp_path, "verified-head", phase=1)
    receipt["checks"] += [
        {"command": ["python", "scripts/e2e_stack.py", "--run"], "returncode": 0},
        {"command": ["python", "scripts/verify_phase0.py", "--regression"], "returncode": 0},
    ]
    path.write_text(json.dumps(receipt))
    safety.require_local_gate(tmp_path, "verified-head", phase=1)
    receipt["commit"] = "stale-head"
    path.write_text(json.dumps(receipt))
    with pytest.raises(ValueError, match="HEAD"):
        safety.require_local_gate(tmp_path, "verified-head", phase=1)


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
        env, "postgresql+asyncpg://safevoice_api:generated@db.host/postgres"
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
    original = "DATABASE_URL=postgresql://safevoice_api_backup:owner-secret@db.project/postgres\n"
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
        "DATABASE_URL=postgresql://safevoice_api:synthetic-password@db.xhlshihobyxrgfqrdafh.supabase.co:5432/postgres\n",
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


def phase23_receipt(root=None):
    receipt = {
        "commit": "verified-head",
        "passed": True,
        "scope": "local_phase23",
        "checks": [
            {"command": ["python", "scripts/verify_phase1.py"], "returncode": 0},
            {"command": ["python", "scripts/e2e_stack.py", "--run"], "returncode": 0},
            {"command": ["python", "scripts/dev/migration_order_check.py"], "returncode": 0},
        ]
        + [{"command": ["python", "scripts/check.py"], "returncode": 0} for _ in range(9)],
    }
    if root is not None:
        import hashlib

        (root / ".local").mkdir(exist_ok=True)
        for index, check in enumerate(receipt["checks"]):
            log = root / f".local/check-{index}.log"
            log.write_text("Synthetic unit transport result")
            check.update(
                log=log.relative_to(root).as_posix(),
                log_sha256=hashlib.sha256(log.read_bytes()).hexdigest(),
            )
    return receipt


@pytest.mark.parametrize(
    "mutation",
    [
        "head",
        "scope",
        "count",
        "failed",
        "missing_phase1",
        "missing_e2e",
        "missing_order",
        "self_test_order",
        "one_order",
        "fake_path",
        "fake_script_arg",
    ],
)
def test_phase23_receipt_rejects_missing_stale_or_incomplete_checks(tmp_path, mutation):
    receipt = phase23_receipt()
    if mutation == "head":
        receipt["commit"] = "stale"
    elif mutation == "scope":
        receipt["scope"] = "local_phase1"
    elif mutation == "count":
        receipt["checks"].pop()
    elif mutation == "failed":
        receipt["checks"][3]["returncode"] = 1
    elif mutation.startswith("missing_"):
        index = {"missing_phase1": 0, "missing_e2e": 1, "missing_order": 2}[mutation]
        receipt["checks"][index]["command"] = ["python", "scripts/check.py"]
    elif mutation == "self_test_order":
        receipt["checks"][2]["command"].append("--self-test")
    elif mutation == "one_order":
        receipt["checks"][2]["command"] += ["--only-order", "A"]
    elif mutation == "fake_path":
        receipt["checks"][0]["command"] = ["python", "evil-scripts/verify_phase1.py"]
    else:
        receipt["checks"][0]["command"] = ["echo", "scripts/verify_phase1.py"]
    (tmp_path / ".local").mkdir()
    (tmp_path / ".local/phase23-gate.json").write_text(json.dumps(receipt))
    with pytest.raises(ValueError):
        safety.require_local_gate(tmp_path, "verified-head", phase=23)


def test_complete_phase23_gate_is_accepted(tmp_path):
    (tmp_path / ".local").mkdir()
    (tmp_path / ".local/phase23-gate.json").write_text(json.dumps(phase23_receipt(tmp_path)))
    safety.require_local_gate(tmp_path, "verified-head", phase=23)


@pytest.mark.parametrize(
    "receipt",
    [
        None,
        [],
        "text",
        {"checks": None},
        {
            "commit": "verified-head",
            "passed": True,
            "scope": "local_phase23",
            "checks": [None] * 12,
        },
    ],
)
def test_malformed_receipts_fail_as_validation_error(tmp_path, receipt):
    (tmp_path / ".local").mkdir()
    (tmp_path / ".local/phase23-gate.json").write_text(json.dumps(receipt))
    with pytest.raises(ValueError):
        safety.require_local_gate(tmp_path, "verified-head", phase=23)


@pytest.mark.parametrize(
    "check",
    [
        {"returncode": False, "command": ["python", "scripts/check.py"]},
        {"returncode": 0, "command": None},
        {"returncode": 0, "command": []},
        {"returncode": 0, "command": [None]},
    ],
)
def test_phase23_requires_twelve_real_command_results(tmp_path, check):
    receipt = phase23_receipt()
    receipt["checks"][3] = check
    (tmp_path / ".local").mkdir()
    (tmp_path / ".local/phase23-gate.json").write_text(json.dumps(receipt))
    with pytest.raises(ValueError):
        safety.require_local_gate(tmp_path, "verified-head", phase=23)


@pytest.mark.parametrize("mutation", ["missing", "tampered", "outside"])
def test_phase23_receipt_requires_its_recorded_command_logs(tmp_path, mutation):
    import hashlib

    receipt = phase23_receipt()
    local = tmp_path / ".local"
    local.mkdir()
    for index, check in enumerate(receipt["checks"]):
        log = local / f"check-{index}.log"
        log.write_text("Synthetic unit transport result")
        check.update(
            log=log.relative_to(tmp_path).as_posix(),
            log_sha256=hashlib.sha256(log.read_bytes()).hexdigest(),
        )
    first = receipt["checks"][0]
    if mutation == "missing":
        (tmp_path / first["log"]).unlink()
    elif mutation == "tampered":
        (tmp_path / first["log"]).write_text("Changed after the gate")
    else:
        first["log"] = "../outside.log"
    (local / "phase23-gate.json").write_text(json.dumps(receipt))
    with pytest.raises(ValueError, match="log|evidence"):
        safety.require_local_gate(tmp_path, "verified-head", phase=23)
