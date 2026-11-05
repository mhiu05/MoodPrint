"""Rehearse synthetic recovery in one NEW network-isolated PostgreSQL container.

No hosted URLs, credentials, existing container IDs or data are accepted.
Requires locally available postgres:17.11; never pulls or creates paid resources.
"""

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from verify_recovery import verify_manifest


def command(args: list[str], data: bytes | None = None) -> bytes:
    result = subprocess.run(args, input=data, capture_output=True, check=False, timeout=90)
    if result.returncode:
        # Docker/Postgres error text may contain input; emit only a fixed category.
        raise RuntimeError("local_command_failed")
    return result.stdout


def cleanup_owned_container(name: str, run_id: str) -> None:
    """Inspect after every launch attempt, including an ambiguous CLI failure."""
    try:
        inspected = subprocess.run(["docker", "inspect", "--type=container", name],
                                   capture_output=True, check=False, timeout=15)
    except (OSError, subprocess.TimeoutExpired):
        raise RuntimeError("cleanup_inspect_failed") from None
    if inspected.returncode:
        # A daemon/access failure is not evidence that the container is absent.
        error = inspected.stderr.decode(errors="replace").strip()
        absent = {f"Error: No such object: {name}", f"Error: No such container: {name}",
                  f"Error response from daemon: No such container: {name}"}
        if inspected.stdout.strip() in (b"", b"[]") and error in absent:
            return
        raise RuntimeError("cleanup_inspect_failed")
    try:
        containers = json.loads(inspected.stdout)
        if not isinstance(containers, list) or len(containers) != 1:
            raise ValueError
        inspection = containers[0]
        config = inspection["Config"]
        host = inspection["HostConfig"]
        labels = config.get("Labels") or {}
        container_id = inspection["Id"]
        if (inspection["Name"] != f"/{name}"
                or labels.get("moodprint.recovery.run") != run_id
                or host["NetworkMode"] != "none" or host.get("PortBindings")
                or "/var/lib/postgresql/data" not in (host.get("Tmpfs") or {})
                or not isinstance(container_id, str)
                or not re.fullmatch(r"[0-9a-f]{64}", container_id)):
            raise RuntimeError("cleanup_ownership_mismatch")
    except (KeyError, TypeError, ValueError, AttributeError):
        raise RuntimeError("cleanup_inspect_failed") from None
    # Delete the immutable inspected identity, so a concurrent name swap cannot
    # make removal target an uninspected container.
    command(["docker", "rm", "--force", container_id])
    remaining = command(["docker", "ps", "-a", "--filter",
                         f"label=moodprint.recovery.run={run_id}", "--format", "{{.ID}}"])
    if remaining.strip():
        raise RuntimeError("cleanup_failed")


def rehearse() -> dict:
    started = time.monotonic()
    run_id = uuid4().hex
    name = f"moodprint-recovery-{run_id}"
    result = {"scope": "SYNTHETIC_LOCAL_ONLY", "run_id": run_id,
              "production_restore_proven": False, "rpo_achieved": False,
              "rto_achieved": False, "cleanup_verified": False}
    try:
        command(["docker", "run", "--detach", "--pull=never", "--name", name,
                 "--label", f"moodprint.recovery.run={run_id}", "--network", "none",
                 "--cpus", "1", "--memory", "512m", "--tmpfs", "/var/lib/postgresql/data:rw",
                 "--env", "POSTGRES_HOST_AUTH_METHOD=trust", "postgres:17.11"])
        deadline = time.monotonic() + 60
        while True:
            ready = subprocess.run(["docker", "exec", name, "pg_isready", "-U", "postgres"],
                                   capture_output=True, timeout=10, check=False)
            if ready.returncode == 0:
                break
            if time.monotonic() > deadline:
                raise RuntimeError("local_postgres_not_ready")
            time.sleep(0.25)
        command(["docker", "exec", name, "createdb", "-U", "postgres", "recovery_source"])
        command(["docker", "exec", name, "createdb", "-U", "postgres", "recovery_target"])
        fixture = b"""
CREATE SCHEMA moodprint;
CREATE ROLE fixture_reader NOLOGIN;
GRANT USAGE ON SCHEMA moodprint TO fixture_reader;
CREATE TABLE moodprint.entries (id integer PRIMARY KEY, owner_id integer NOT NULL, body text NOT NULL);
INSERT INTO moodprint.entries VALUES (1,1,'synthetic-owner-one'),(2,2,'synthetic-owner-two');
ALTER TABLE moodprint.entries ENABLE ROW LEVEL SECURITY;
CREATE POLICY own_entries ON moodprint.entries TO fixture_reader
  USING (owner_id = current_setting('fixture.owner_id')::integer);
GRANT SELECT ON moodprint.entries TO fixture_reader;
CREATE TABLE moodprint.financial_holds (id integer PRIMARY KEY, state text NOT NULL, liability_micros integer NOT NULL);
INSERT INTO moodprint.financial_holds VALUES (1,'uncertain',120000);
"""
        command(["docker", "exec", "-i", name, "psql", "-U", "postgres", "-d",
                 "recovery_source", "-v", "ON_ERROR_STOP=1"], fixture)
        archive = command(["docker", "exec", name, "pg_dump", "-U", "postgres", "-Fc",
                           "--dbname=recovery_source"])
        with tempfile.TemporaryDirectory(prefix="moodprint-recovery-") as directory:
            root = Path(directory)
            contents = {
                "database": [archive],
                "storage": [b"synthetic-private-object-one", b"synthetic-private-object-two"],
                "configuration": [b'{"synthetic":true,"api_replicas":1}'],
                "secrets": [b"SYNTHETIC_ONLY_NOT_A_REAL_SECRET"],
                "infrastructure": [b'{"synthetic":true,"real_snapshot_exists":false}'],
            }
            components = {}
            for domain, blobs in contents.items():
                artifacts = []
                for index, blob in enumerate(blobs):
                    file = root / f"{domain}-{index}.bin"
                    file.write_bytes(blob)
                    artifacts.append({"path": file.name, "size_bytes": len(blob),
                                      "sha256": hashlib.sha256(blob).hexdigest()})
                components[domain] = {"captured_at": datetime.now(UTC).isoformat(),
                                      "artifacts": artifacts}
            components["storage"]["expected_objects"] = 2
            manifest = root / "manifest.json"
            manifest.write_text(json.dumps({"schema_version": 1, "components": components}))
            result["artifact_verification"] = verify_manifest(manifest, datetime.now(UTC))
            command(["docker", "exec", "-i", name, "pg_restore", "-U", "postgres",
                     "--dbname=recovery_target", "--exit-on-error", "--single-transaction"],
                    (root / "database-0.bin").read_bytes())
            restored = root / "restored"
            restored.mkdir()
            for domain in ("storage", "configuration", "secrets"):
                for index, original in enumerate(contents[domain]):
                    target = restored / f"{domain}-{index}.bin"
                    shutil.copyfile(root / target.name, target)
                    if target.read_bytes() != original:
                        raise RuntimeError("synthetic_byte_restore_mismatch")
            result["synthetic_object_bytes_match"] = True
            result["synthetic_config_and_secret_bytes_match"] = True
        query = b"""
SELECT count(*) FROM moodprint.entries;
SELECT state || ':' || liability_micros FROM moodprint.financial_holds;
SELECT relrowsecurity FROM pg_class WHERE oid='moodprint.entries'::regclass;
SET ROLE fixture_reader;
SET fixture.owner_id='1';
SELECT string_agg(id::text, ',' ORDER BY id) FROM moodprint.entries;
"""
        checks = command(["docker", "exec", "-i", name, "psql", "-U", "postgres", "-d",
                          "recovery_target", "-qAt", "-v", "ON_ERROR_STOP=1"], query)
        if checks.decode().splitlines() != ["2", "uncertain:120000", "t", "1"]:
            raise RuntimeError("synthetic_database_restore_mismatch")
        result.update({"status": "SYNTHETIC_LOCAL_RESTORE_PASS", "postgres": "17.11",
                       "entries_restored": 2, "rls_cross_owner_denied": True,
                       "uncertain_liability_preserved_micros": 120000,
                       "network": "none", "published_ports": 0})
    finally:
        cleanup_owned_container(name, run_id)
        result["cleanup_verified"] = True
        result["elapsed_seconds"] = round(time.monotonic() - started, 3)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-synthetic", action="store_true", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        print(json.dumps({"status": "FAIL", "error_code": "output_already_exists"}))
        return 1
    try:
        report = rehearse()
    except (RuntimeError, OSError, ValueError, subprocess.TimeoutExpired) as exc:
        code = str(exc) if isinstance(exc, RuntimeError) else "local_rehearsal_failed"
        print(json.dumps({"status": "FAIL", "error_code": code}))
        return 1
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
