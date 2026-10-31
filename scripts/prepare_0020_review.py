"""Export the approved 0020 retirement semantics OFFLINE; never execute hosted SQL.

The package records pending operational gates. It cannot bypass the local-only
Alembic runner or the existing expand-only hosted executor.
"""

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = "0019_journal"
TARGET = "0020_private_profile_retirement"
PENDING = ROOT / "deploy/supabase/pending-review/0020"


def migration_sql() -> str:
    env = {
        **os.environ,
        "APP_ENV": "test",
        "DATABASE_URL": "",
        "DATABASE_MIGRATION_URL": "postgresql+psycopg://127.0.0.1/offline_test",
        "SUPABASE_URL": "",
        "SUPABASE_PUBLISHABLE_KEY": "",
        "OPENAI_API_KEY": "",
        "VOYAGE_API_KEY": "",
        "AI_ENABLED": "false",
        "STT_ENABLED": "false",
        "SEMANTIC_MEMORY_ENABLED": "false",
    }
    return subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", f"{BASE}:{TARGET}", "--sql"],
        cwd=ROOT / "backend",
        env=env,
        capture_output=True,
        check=True,
        encoding="utf-8",
    ).stdout.replace("\r\n", "\n")


def prepare(output: Path) -> dict:
    output = Path(output).resolve()
    roots = (Path(tempfile.gettempdir()).resolve(), (ROOT / ".tmp").resolve(), PENDING.resolve())
    if output.suffix != ".sql" or not any(output.is_relative_to(root) for root in roots):
        raise ValueError("Use a new .sql inside OS temp, .tmp or the pending 0020 review directory")
    if output.exists() or output.with_suffix(".json").exists():
        raise FileExistsError("Never overwrite an existing SQL package or its metadata")
    sql = migration_sql()
    marker = f"-- Running upgrade {BASE} -> {TARGET}"
    if marker not in sql or sql.count("-- Running upgrade ") != 1:
        raise ValueError("Expected only the real Alembic 0019 to 0020 export")
    content = sql.encode("utf-8")
    metadata = {
        "fromRevision": BASE,
        "toRevision": TARGET,
        "sha256": hashlib.sha256(content).hexdigest(),
        "bytes": len(content),
        "semantics": "OWNER_APPROVED_INTENTIONAL_RETIREMENT",
        "remoteExecuted": False,
        "hostedExecutionAllowed": False,
        "executionMechanism": "Verbatim transactional Alembic offline export; never stamp",
        "requiredGates": {
            "targetProjectAndOwner": "NOT_VERIFIED",
            "hostedBackupRestored": "NOT_VERIFIED",
            "disposableRehearsal": "NOT_VERIFIED",
            "compatibleBackend": "NOT_VERIFIED",
            "oldTrafficDrained": "NOT_VERIFIED",
            "postMigrationChecksPrepared": "NOT_VERIFIED",
        },
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("xb") as stream:
        stream.write(content)
    with output.with_suffix(".json").open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(metadata, stream, indent=2)
        stream.write("\n")
    return metadata


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(prepare(args.output)))
