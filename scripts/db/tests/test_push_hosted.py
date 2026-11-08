"""Exercise deployment orchestration with network/CLI transport replaced only."""

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

DB = Path(__file__).parents[1]
spec = importlib.util.spec_from_file_location("safety", DB / "safety.py")
assert spec and spec.loader
safety = importlib.util.module_from_spec(spec)
sys.modules["safety"] = safety
spec.loader.exec_module(safety)
spec = importlib.util.spec_from_file_location("push_hosted", DB / "push_hosted.py")
assert spec and spec.loader
push = importlib.util.module_from_spec(spec)
spec.loader.exec_module(push)
HEAD = "a" * 40
INTRO = "b" * 40


def setup(tmp_path, monkeypatch, *, old_pending=False):
    files = tmp_path / "supabase/migrations"
    files.mkdir(parents=True)
    names = [
        "20261107100000_f0_base.sql",
        "20261108100000_kb_sources.sql",
        "20261108100001_ag_tools.sql",
    ]
    paths = [files / name for name in names]
    for path in paths:
        path.write_bytes(b"-- checked out CRLF\r\nselect 1;\r\n")
    history = [("20261107100000", "f0_base")]
    if old_pending:
        history.append(("20261108100001", "ag_tools"))
    state = {
        "history": history,
        "cli": [],
        "apply_history": None,
        "cli_exit": 0,
        "history_reads": 0,
        "drift_after_history_read": None,
    }
    monkeypatch.setattr(push, "ROOT", tmp_path)
    monkeypatch.setattr(
        push,
        "load_hosted_env",
        lambda: {
            "SUPABASE_URL": f"https://{safety.PROJECT_REF}.supabase.co",
            "SUPABASE_DB_URL": f"postgresql://postgres:must-not-leak@db.{safety.PROJECT_REF}.supabase.co/postgres",
        },
    )
    monkeypatch.setattr(push, "committed_migrations", lambda: paths)

    class Connection:
        async def fetchval(self, query):
            return True

        async def fetch(self, query):
            state["history_reads"] += 1
            rows = [{"version": version, "name": name} for version, name in state["history"]]
            if state["history_reads"] == state["drift_after_history_read"]:
                state["history"] = [("20261107100000", "f0_base"), ("20261108100000", "kb_sources")]
            return rows

        async def close(self):
            pass

    async def connect(*args, **kwargs):
        return Connection()

    monkeypatch.setattr(push.asyncpg, "connect", connect)

    def transport(command, **kwargs):
        if command[:3] == ["git", "rev-parse", "HEAD"]:
            return subprocess.CompletedProcess(command, 0, HEAD + "\n", "")
        if command[:2] == ["git", "show"]:
            return subprocess.CompletedProcess(command, 0, b"-- committed LF\nselect 1;\n", b"")
        if command[:2] == ["git", "log"]:
            return subprocess.CompletedProcess(command, 0, INTRO + "\n", "")
        state["cli"].append(command)
        if "--dry-run" not in command:
            state["history"] = (
                state["apply_history"]
                if state["apply_history"] is not None
                else [(path.name[:14], path.stem[15:]) for path in paths]
            )
        return subprocess.CompletedProcess(
            command, state["cli_exit"], "secret CLI stdout", "secret CLI stderr"
        )

    monkeypatch.setattr(push.subprocess, "run", transport)
    # Gate content is real; only external transport is replaced.
    local = tmp_path / ".local"
    local.mkdir()
    checks = [
        {"command": ["python", "scripts/verify_phase1.py"], "returncode": 0},
        {"command": ["python", "scripts/e2e_stack.py", "--run"], "returncode": 0},
        {"command": ["python", "scripts/dev/migration_order_check.py"], "returncode": 0},
    ] + [{"command": ["python", "scripts/check.py"], "returncode": 0}] * 9
    (local / "phase23-gate.json").write_text(
        json.dumps({"commit": HEAD, "passed": True, "scope": "local_phase23", "checks": checks})
    )
    return state, paths


@pytest.mark.asyncio
async def test_dryrun_receipt_records_committed_bytes_head_provenance_without_secrets(
    tmp_path, monkeypatch, capsys
):
    import hashlib

    state, paths = setup(tmp_path, monkeypatch)
    await push.run(apply=False)
    receipt_text = (tmp_path / ".local/hosted-migration-dry-run.json").read_text()
    receipt = json.loads(receipt_text)
    assert receipt["project_ref"] == "xhlshihobyxrgfqrdafh"
    assert receipt["head"] == HEAD
    assert receipt["pending"][0]["introducing_commit"] == INTRO
    assert (
        receipt["pending"][0]["sha256"]
        == hashlib.sha256(b"-- committed LF\nselect 1;\n").hexdigest()
    )
    assert receipt["pending"][0]["version"] == "20261108100000"
    assert "must-not-leak" not in receipt_text + capsys.readouterr().out
    assert "secret CLI" not in receipt_text
    assert len(state["cli"]) == 1 and "--dry-run" in state["cli"][0]


@pytest.mark.asyncio
async def test_apply_requires_matching_prior_dryrun_before_cli_mutation(tmp_path, monkeypatch):
    state, _ = setup(tmp_path, monkeypatch)
    with pytest.raises(ValueError, match="dry.run"):
        await push.run(apply=True)
    assert state["cli"] == []


@pytest.mark.asyncio
@pytest.mark.parametrize("drift", ["pending", "history", "head", "hash", "project", "malformed"])
async def test_apply_rejects_drift_from_reviewed_dryrun(tmp_path, monkeypatch, drift):
    state, paths = setup(tmp_path, monkeypatch)
    await push.run(apply=False)
    receipt_path = tmp_path / ".local/hosted-migration-dry-run.json"
    receipt = json.loads(receipt_path.read_text())
    if drift == "pending":
        receipt["pending"].pop()
    elif drift == "history":
        receipt["history"] = []
    elif drift == "head":
        receipt["head"] = "c" * 40
    elif drift == "hash":
        receipt["pending"][0]["sha256"] = "0" * 64
    elif drift == "project":
        receipt["project_ref"] = "wrong"
    else:
        receipt = []
    receipt_path.write_text(json.dumps(receipt))
    with pytest.raises(ValueError, match="dry.run"):
        await push.run(apply=True)
    assert len(state["cli"]) == 1


@pytest.mark.asyncio
async def test_apply_rechecks_exact_history_after_cli_success(tmp_path, monkeypatch):
    state, _ = setup(tmp_path, monkeypatch)
    await push.run(apply=False)
    state["apply_history"] = [("20261107100000", "f0_base")]
    with pytest.raises(ValueError, match="history"):
        await push.run(apply=True)


@pytest.mark.asyncio
async def test_backfill_audit_requires_explicit_include_all_for_apply(tmp_path, monkeypatch):
    state, _ = setup(tmp_path, monkeypatch, old_pending=True)
    await push.run(apply=False)
    assert (
        json.loads((tmp_path / ".local/hosted-migration-dry-run.json").read_text())["cli_dry_run"]
        is False
    )
    with pytest.raises(ValueError, match="include-all"):
        await push.run(apply=True)
    assert state["cli"] == []
    await push.run(apply=True, include_all=True)
    assert len(state["cli"]) == 1 and "--include-all" in state["cli"][0]


@pytest.mark.asyncio
async def test_include_all_dryrun_is_rejected_before_environment_or_connection(monkeypatch):
    monkeypatch.setattr(
        push, "load_hosted_env", lambda: pytest.fail("must reject before env/network")
    )
    with pytest.raises(ValueError, match="apply"):
        await push.run(apply=False, include_all=True)


@pytest.mark.asyncio
async def test_matching_plan_applies_and_verifies_the_complete_history(tmp_path, monkeypatch):
    state, _ = setup(tmp_path, monkeypatch)
    await push.run(apply=False)
    await push.run(apply=True)
    assert state["history"] == [
        ("20261107100000", "f0_base"),
        ("20261108100000", "kb_sources"),
        ("20261108100001", "ag_tools"),
    ]


@pytest.mark.asyncio
async def test_failed_new_dryrun_invalidates_old_receipt_without_leaking_cli_output(
    tmp_path, monkeypatch, capsys
):
    state, _ = setup(tmp_path, monkeypatch)
    await push.run(apply=False)
    state["cli_exit"] = 1
    with pytest.raises(RuntimeError) as caught:
        await push.run(apply=False)
    assert not (tmp_path / ".local/hosted-migration-dry-run.json").exists()
    assert "secret CLI" not in str(caught.value) + capsys.readouterr().out


@pytest.mark.asyncio
async def test_remote_history_drift_after_review_rejects_apply(tmp_path, monkeypatch):
    state, _ = setup(tmp_path, monkeypatch)
    await push.run(apply=False)
    state["history"].append(("20261108100000", "kb_sources"))
    with pytest.raises(ValueError, match="dry.run"):
        await push.run(apply=True)
    assert len(state["cli"]) == 1


@pytest.mark.asyncio
async def test_history_drift_during_apply_preflight_is_rejected_before_cli(tmp_path, monkeypatch):
    state, _ = setup(tmp_path, monkeypatch)
    await push.run(apply=False)
    state["drift_after_history_read"] = 2
    with pytest.raises(ValueError, match="dry.run"):
        await push.run(apply=True)
    assert len(state["cli"]) == 1
