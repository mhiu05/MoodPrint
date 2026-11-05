"""Offline recovery evidence must fail closed without printing private filenames."""

import hashlib
import importlib
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts/verify_recovery.py"
NOW = "2026-11-05T12:00:00+00:00"


def bundle(tmp_path):
    components = {}
    for domain in ("database", "storage", "configuration", "secrets", "infrastructure"):
        content = f"synthetic-{domain}".encode()
        name = f"private-{domain}.bin"
        (tmp_path / name).write_bytes(content)
        components[domain] = {
            "captured_at": "2026-11-04T12:00:00+00:00",
            "artifacts": [{"path": name, "size_bytes": len(content),
                           "sha256": hashlib.sha256(content).hexdigest()}],
        }
    components["storage"]["expected_objects"] = 1
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"schema_version": 1, "components": components}))
    return manifest, components


def run(manifest):
    return subprocess.run([sys.executable, str(SCRIPT), "--manifest", str(manifest),
                           "--now", NOW], capture_output=True, text=True, check=False)


def write(manifest, components):
    manifest.write_text(json.dumps({"schema_version": 1, "components": components}))


def test_verifies_complete_bundle_at_rpo_boundary_without_claiming_restore(tmp_path):
    manifest, _ = bundle(tmp_path)
    result = run(manifest)
    assert result.returncode == 0, result.stdout
    report = json.loads(result.stdout)
    assert report["status"] == "ARTIFACT_INTEGRITY_PASS"
    assert report["restore_proven"] is False
    assert report["source_completeness"] == "NOT_PROVEN"
    assert report["oldest_capture_age_hours"] == 24
    assert "private-" not in result.stdout + result.stderr


@pytest.mark.parametrize("domain", ["database", "storage", "configuration", "secrets", "infrastructure"])
def test_requires_every_recovery_domain(tmp_path, domain):
    manifest, components = bundle(tmp_path)
    del components[domain]
    write(manifest, components)
    result = run(manifest)
    assert result.returncode == 1
    assert json.loads(result.stdout)["error_code"] == "missing_component"


@pytest.mark.parametrize("mutation,code", [
    ("corrupt", "artifact_digest_mismatch"), ("missing", "artifact_unavailable"),
    ("stale", "capture_outside_rpo"), ("future", "capture_in_future"),
    ("naive", "invalid_capture_time"), ("escape", "unsafe_artifact_path"),
    ("absolute", "unsafe_artifact_path"), ("duplicate", "duplicate_artifact_path"),
    ("storage_count", "storage_inventory_mismatch"), ("empty", "empty_component"),
    ("size", "artifact_size_mismatch"),
])
def test_rejects_invalid_evidence_without_disclosing_paths(tmp_path, mutation, code):
    manifest, components = bundle(tmp_path)
    database = components["database"]
    if mutation == "corrupt":
        (tmp_path / "private-database.bin").write_bytes(b"X" * 18)
    elif mutation == "missing":
        (tmp_path / "private-database.bin").unlink()
    elif mutation == "stale":
        database["captured_at"] = "2026-11-04T11:59:59+00:00"
    elif mutation == "future":
        database["captured_at"] = "2026-11-05T12:00:01+00:00"
    elif mutation == "naive":
        database["captured_at"] = "2026-11-05T12:00:00"
    elif mutation == "escape":
        database["artifacts"][0]["path"] = "../private-outside.bin"
    elif mutation == "absolute":
        database["artifacts"][0]["path"] = str(tmp_path / "private-database.bin")
    elif mutation == "duplicate":
        components["secrets"]["artifacts"] = database["artifacts"]
    elif mutation == "storage_count":
        components["storage"]["expected_objects"] = 2
    elif mutation == "empty":
        database["artifacts"] = []
    elif mutation == "size":
        database["artifacts"][0]["size_bytes"] = 1
    write(manifest, components)
    result = run(manifest)
    assert result.returncode == 1, result.stdout
    assert json.loads(result.stdout)["error_code"] == code
    assert "private-" not in result.stdout + result.stderr


def test_malformed_manifest_emits_only_safe_error(tmp_path):
    manifest = tmp_path / "private-manifest.json"
    manifest.write_text("secret malformed contents")
    result = run(manifest)
    assert result.returncode == 1
    assert json.loads(result.stdout)["error_code"] == "invalid_manifest"
    assert "secret" not in result.stdout + result.stderr


def test_empty_storage_inventory_is_explicitly_allowed(tmp_path):
    manifest, components = bundle(tmp_path)
    components["storage"]["expected_objects"] = 0
    components["storage"]["artifacts"] = []
    write(manifest, components)
    result = run(manifest)
    assert result.returncode == 0
    assert datetime.fromisoformat(NOW).tzinfo == UTC


def test_empty_private_storage_object_is_valid(tmp_path):
    manifest, components = bundle(tmp_path)
    (tmp_path / "private-storage.bin").write_bytes(b"")
    components["storage"]["artifacts"][0].update({
        "size_bytes": 0,
        "sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    })
    write(manifest, components)
    assert run(manifest).returncode == 0


def test_rehearsal_requires_explicit_local_run_without_contacting_docker():
    script = SCRIPT.with_name("rehearse_recovery.py")
    result = subprocess.run([sys.executable, str(script)], capture_output=True, text=True,
                            check=False)
    assert result.returncode == 2
    assert "--run-synthetic" in result.stderr


def test_rehearsal_refuses_overwriting_evidence(tmp_path):
    script = SCRIPT.with_name("rehearse_recovery.py")
    output = tmp_path / "evidence.json"
    output.write_text("keep")
    result = subprocess.run([sys.executable, str(script), "--run-synthetic", "--output", str(output)],
                            capture_output=True, text=True, check=False)
    assert result.returncode == 1
    assert json.loads(result.stdout)["error_code"] == "output_already_exists"
    assert output.read_text() == "keep"


@pytest.fixture
def failed_container_launch(monkeypatch):
    """Model the daemon create side effect even when its CLI fails to return success."""
    monkeypatch.syspath_prepend(str(SCRIPT.parent))
    module = importlib.import_module("rehearse_recovery")
    run_id = "9123456789abcdef0123456789abcdef"
    name = f"moodprint-recovery-{run_id}"
    container_id = "a" * 64
    monkeypatch.setattr(module, "uuid4", lambda: UUID(run_id))

    def scenario(launch_failure, inspection="owned"):
        calls = []
        container = {
            "Id": container_id, "Name": f"/{name}",
            "Config": {"Labels": {"moodprint.recovery.run": run_id}},
            "HostConfig": {"NetworkMode": "none", "PortBindings": {},
                           "Tmpfs": {"/var/lib/postgresql/data": "rw"}},
        }
        if inspection == "wrong_label":
            container["Config"]["Labels"]["moodprint.recovery.run"] = "another-run"
        elif inspection == "wrong_name":
            container["Name"] = "/someone-elses-container"
        elif inspection == "networked":
            container["HostConfig"]["NetworkMode"] = "bridge"
        elif inspection == "persistent":
            container["HostConfig"]["Tmpfs"] = {}
        elif inspection == "published":
            container["HostConfig"]["PortBindings"] = {"5432/tcp": [{"HostPort": "5432"}]}

        def docker(args, **kwargs):
            calls.append(args)
            if args[:2] == ["docker", "run"]:
                # Creation has happened in the daemon; only the CLI result is lost.
                if launch_failure == "timeout":
                    raise subprocess.TimeoutExpired(args, 90)
                return subprocess.CompletedProcess(args, 1, b"", b"start failed after create")
            if args[:2] == ["docker", "inspect"]:
                assert args[-1] == name
                if inspection == "not_found":
                    return subprocess.CompletedProcess(args, 1, b"[]", f"Error: No such object: {name}\n".encode())
                if inspection == "daemon_error":
                    return subprocess.CompletedProcess(args, 1, b"", b"daemon unavailable")
                return subprocess.CompletedProcess(args, 0, json.dumps([container]).encode(), b"")
            if args[:2] == ["docker", "rm"]:
                assert args == ["docker", "rm", "--force", container_id]
                return subprocess.CompletedProcess(args, 0, b"", b"")
            if args[:2] == ["docker", "ps"]:
                assert f"label=moodprint.recovery.run={run_id}" in args
                return subprocess.CompletedProcess(args, 0, b"", b"")
            raise AssertionError(f"Unexpected command during failed launch: {args[:2]}")

        monkeypatch.setattr(module.subprocess, "run", docker)
        return module, calls

    return scenario


@pytest.mark.parametrize("failure", ["timeout", "nonzero"])
def test_launch_failure_after_daemon_create_still_removes_only_owned_container(
    failed_container_launch, failure,
):
    module, calls = failed_container_launch(failure)
    expected = subprocess.TimeoutExpired if failure == "timeout" else RuntimeError
    with pytest.raises(expected):
        module.rehearse()
    assert [args[1] for args in calls] == ["run", "inspect", "rm", "ps"]


@pytest.mark.parametrize("inspection", ["wrong_label", "wrong_name", "networked", "persistent", "published"])
def test_failed_launch_cleanup_never_removes_mismatched_resource(
    failed_container_launch, inspection,
):
    module, calls = failed_container_launch("nonzero", inspection)
    with pytest.raises(RuntimeError, match="cleanup_ownership_mismatch"):
        module.rehearse()
    assert [args[1] for args in calls] == ["run", "inspect"]


def test_failed_launch_with_no_created_container_preserves_launch_error(failed_container_launch):
    module, calls = failed_container_launch("nonzero", "not_found")
    with pytest.raises(RuntimeError, match="local_command_failed"):
        module.rehearse()
    assert [args[1] for args in calls] == ["run", "inspect"]


def test_cleanup_does_not_treat_daemon_failure_as_container_absence(failed_container_launch):
    module, calls = failed_container_launch("nonzero", "daemon_error")
    with pytest.raises(RuntimeError, match="cleanup_inspect_failed"):
        module.rehearse()
    assert [args[1] for args in calls] == ["run", "inspect"]
