"""Generate pending guest SQL OFFLINE, outside all historically approved artifacts."""

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = "0015_context_privacy"


def migration_sql(revision_range=f"{BASE}:head") -> str:
    env = {**os.environ, "DATABASE_URL": "", "DATABASE_MIGRATION_URL": "postgresql+psycopg://127.0.0.1/offline_test",
           "APP_ENV": "test", "AI_ENABLED": "false", "STT_ENABLED": "false",
           "SUPABASE_URL": "", "SUPABASE_PUBLISHABLE_KEY": "", "OPENAI_API_KEY": "", "VOYAGE_API_KEY": ""}
    result = subprocess.run([sys.executable, "-m", "alembic", "upgrade", revision_range, "--sql"],
                            cwd=ROOT / "backend", env=env, capture_output=True, check=True, encoding="utf-8")
    return result.stdout.replace("\r\n", "\n")


def prepare(output: Path, from_revision=BASE) -> dict:
    output = Path(output).resolve()
    roots = (Path(tempfile.gettempdir()).resolve(), (ROOT / "deploy/supabase/reports").resolve())
    if not any(output.is_relative_to(root) for root in roots) or output.suffix != ".sql":
        raise ValueError("Pending SQL must be a new .sql in the OS temp directory or deploy/supabase/reports")
    if from_revision != BASE:
        raise ValueError("Only the inspected 0015 base is supported")
    if output.exists() or output.with_suffix(".json").exists():
        raise FileExistsError("Review output already exists; never overwrite it")
    sql = migration_sql()
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("xb") as stream:
        stream.write(sql.encode("utf-8"))
    metadata = {"fromRevision": BASE, "toRevision": "0018_app_feedback", "sha256": hashlib.sha256(sql.encode()).hexdigest(),
                "remoteExecuted": False, "approval": "PENDING", "bytes": len(sql.encode())}
    with output.with_suffix(".json").open("x", encoding="utf-8") as stream:
        json.dump(metadata, stream, indent=2)
    return metadata


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--from-revision", default=BASE)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(prepare(args.output, args.from_revision)))
