"""Provision one uniquely owned, loopback-only PostgreSQL 17 test container.

Run with backend/.venv/Scripts/python.exe. Credentials go only to an ignored .env
file under .tmp; this script never touches an existing database or container.
"""

import argparse
import json
import os
import secrets
import socket
import subprocess
import time
from pathlib import Path
from uuid import UUID, uuid4

import psycopg
from psycopg import sql


def provision(port: int) -> None:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", port))
    run_id = uuid4().hex
    name = f"moodprint-disposable-{run_id}"
    owner = f"moodprint_test_{run_id}"
    database = f"moodprint_{run_id}_test"
    password = secrets.token_hex(32)
    output = Path(__file__).resolve().parents[1] / ".tmp" / name
    output.mkdir(parents=True, exist_ok=False)
    env = {**os.environ, "POSTGRES_PASSWORD": password}
    result = subprocess.run(
        [
            "docker",
            "run",
            "--detach",
            "--name",
            name,
            "--label",
            f"moodprint.disposable.run={run_id}",
            "--publish",
            f"127.0.0.1:{port}:5432",
            "--tmpfs",
            "/var/lib/postgresql/data:rw",
            "--env",
            "POSTGRES_PASSWORD",
            "--env",
            f"POSTGRES_USER={owner}",
            "--env",
            f"POSTGRES_DB={database}",
            "pgvector/pgvector:0.8.2-pg17",
        ],
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode:
        raise RuntimeError(f"Docker could not create the dedicated container: {result.stderr}")
    raw = f"postgresql+psycopg://{owner}:{password}@127.0.0.1:{port}/{database}"
    # Record credentials early so a failed readiness check remains diagnosable.
    (output / ".env").write_text(
        f"TEST_DATABASE_URL={raw}\nMOODPRINT_TEST_RUN_ID={run_id}\n", encoding="utf-8"
    )
    deadline = time.monotonic() + 60
    while True:
        try:
            with psycopg.connect(
                raw.replace("postgresql+psycopg://", "postgresql://", 1),
                hostaddr="127.0.0.1",
                connect_timeout=2,
            ) as conn:
                conn.execute(
                    sql.SQL("COMMENT ON DATABASE {} IS {}").format(
                        sql.Identifier(database), sql.Literal(f"moodprint-disposable-test:{run_id}")
                    )
                )
                conn.execute("CREATE SCHEMA IF NOT EXISTS extensions")
                conn.execute("CREATE EXTENSION IF NOT EXISTS vector WITH SCHEMA extensions")
                version, vector = conn.execute(
                    "SELECT current_setting('server_version'), extversion "
                    "FROM pg_extension WHERE extname = 'vector'"
                ).fetchone()
            break
        except psycopg.OperationalError:
            if time.monotonic() >= deadline:
                raise RuntimeError(f"Dedicated container {name} did not become ready") from None
            time.sleep(1)
    metadata = {
        "run_id": run_id,
        "container": name,
        "port": port,
        "database": database,
        "owner": owner,
        "postgres": version,
        "pgvector": vector,
    }
    (output / "metadata.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({**metadata, "environment_file": str(output / ".env")}))


def remove(run_id: str) -> None:
    """Remove only an exact UUID container with this script's ownership label."""
    if UUID(run_id).hex != run_id:
        raise ValueError("Cleanup requires the exact lowercase 32-character run ID")
    name = f"moodprint-disposable-{run_id}"
    result = subprocess.run(["docker", "inspect", name], text=True, capture_output=True, check=True)
    container = json.loads(result.stdout)[0]
    if (
        container["Config"]["Labels"].get("moodprint.disposable.run") != run_id
        or "/var/lib/postgresql/data" not in container["HostConfig"]["Tmpfs"]
    ):
        raise RuntimeError("Refusing cleanup: container ownership or disposable storage mismatch")
    subprocess.run(["docker", "rm", "--force", name], check=True, capture_output=True)
    credentials = Path(__file__).resolve().parents[1] / ".tmp" / name / ".env"
    credentials.unlink(missing_ok=True)
    print(f"Removed owned disposable container {name} and its local credentials")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=55439)
    parser.add_argument("--remove", metavar="RUN_ID", help="Remove only a labelled owned container")
    args = parser.parse_args()
    if args.remove:
        remove(args.remove)
    else:
        provision(args.port)
