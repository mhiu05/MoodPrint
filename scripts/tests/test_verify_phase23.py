"""Gate receipts must represent a complete, unchanged, local-only execution."""

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))


def module():
    path = ROOT / "scripts/verify_phase23.py"
    assert path.exists(), "The complete Phase 2/3 gate runner is missing"
    spec = importlib.util.spec_from_file_location("verify_phase23", path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


@pytest.fixture
def repository(tmp_path, monkeypatch):
    import e2e_stack

    monkeypatch.setattr(e2e_stack, "ROOT", tmp_path)
    for args in (
        ["init", "-q"],
        ["config", "user.name", "Synthetic Test"],
        ["config", "user.email", "synthetic@example.invalid"],
    ):
        subprocess.run(["git", *args], cwd=tmp_path, check=True, capture_output=True)
    (tmp_path / ".git/info/exclude").write_text(".local/\n")
    (tmp_path / "source.py").write_text("value = 1\n")
    subprocess.run(["git", "add", "source.py"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-qm", "fixture"], cwd=tmp_path, check=True)
    return tmp_path


def transport(root, *, failure=None, drift=False):
    count = 0

    def run(command, cwd, environment, log):
        nonlocal count
        count += 1
        assert environment["APP_ENV"] == "test"
        assert "OPENAI_API_KEY" not in environment
        assert "SUPABASE_ACCESS_TOKEN" not in environment
        assert "SUPABASE_DB_URL" not in environment
        log.write_text("synthetic command boundary\n")
        if "scripts/dev/bootstrap_local_db.py" in command:
            path = root / ".local/stacks/fixture/test.env"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                'APP_ENV="test"\nSUPABASE_URL="http://127.0.0.1:54721"\n'
                'SUPABASE_PUBLISHABLE_KEY="synthetic"\nSUPABASE_SECRET_KEY="synthetic"\n'
                + "".join(
                    f'{name}="postgresql+asyncpg://safevoice_api:synthetic@127.0.0.1:54722/postgres"\n'
                    for name in ("DATABASE_URL", "TEST_DATABASE_URL", "TEST_ADMIN_DATABASE_URL")
                )
            )
        if drift and count == 4:
            (root / "source.py").write_text("value = 2\n")
        return 7 if count == failure else 0

    return run


def test_complete_gate_receipt_is_consumable_and_has_real_command_provenance(
    repository, monkeypatch
):
    gate = module()
    monkeypatch.setenv("OPENAI_API_KEY", "must-not-inherit")
    monkeypatch.setenv("SUPABASE_DB_URL", "must-not-inherit")
    monkeypatch.setattr(gate, "run_command", transport(repository))
    assert gate.verify(repository, "fixture", 400) == 0
    receipt = json.loads((repository / ".local/phase23-gate.json").read_text())
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repository, text=True).strip()
    assert receipt["commit"] == head
    assert len(receipt["checks"]) >= 12
    assert all(check["returncode"] == 0 and check["log_sha256"] for check in receipt["checks"])
    status = json.loads(
        (repository / ".local/verification/phase23-fixture-400/status.json").read_text()
    )
    assert status["passed"] is True
    from db.safety import require_local_gate

    require_local_gate(repository, head, phase=23)


def test_failed_command_revokes_stale_receipt_and_stops(repository, monkeypatch):
    gate = module()
    local = repository / ".local"
    local.mkdir()
    receipt = local / "phase23-gate.json"
    receipt.write_text('{"passed":true}')
    monkeypatch.setattr(gate, "run_command", transport(repository, failure=4))
    assert gate.verify(repository, "fixture", 400) == 7
    assert not receipt.exists()
    status = json.loads((local / "verification/phase23-fixture-400/status.json").read_text())
    assert status["passed"] is False
    assert len(status["checks"]) == 4


def test_dirty_source_during_checks_cannot_issue_receipt(repository, monkeypatch):
    gate = module()
    monkeypatch.setattr(gate, "run_command", transport(repository, drift=True))
    with pytest.raises(ValueError, match="changed|clean"):
        gate.verify(repository, "fixture", 400)
    assert not (repository / ".local/phase23-gate.json").exists()


@pytest.mark.parametrize("name,offset", [("foundation", 0), ("../escape", 400)])
def test_gate_requires_isolated_stack_before_any_command(repository, monkeypatch, name, offset):
    gate = module()

    def forbidden(*args):
        pytest.fail("An invalid stack must fail before running commands")

    monkeypatch.setattr(gate, "run_command", forbidden)
    with pytest.raises(ValueError, match="isolated"):
        gate.verify(repository, name, offset)
