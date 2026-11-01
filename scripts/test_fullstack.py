"""Run the local synthetic full stack on Windows/Linux; stop only owned processes."""

import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))


def run(
    arguments=None,
    *,
    server_module="tests.e2e_server",
    playwright_config="playwright.fullstack.config.ts",
    extra_environment=None,
):
    import psycopg

    from tests.database_target import (
        require_local_test_database,
        verify_test_database_sync,
    )

    target = require_local_test_database(os.environ.get("TEST_DATABASE_URL", ""))
    with psycopg.connect(target.set(drivername="postgresql").render_as_string(hide_password=False)) as db:
        verify_test_database_sync(db)
    for port in (8002, 5174):
        with socket.socket() as connection:
            try:
                connection.bind(("127.0.0.1", port))
            except OSError:
                raise RuntimeError(
                    f"Port {port} is occupied; existing processes will not be stopped"
                ) from None
    environment = {
        **os.environ,
        **(extra_environment or {}),
        "MOODPRINT_API_PROXY": "http://127.0.0.1:8002",
    }
    flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    processes = []
    logs = Path(tempfile.mkdtemp(prefix="moodprint-fullstack-"))
    handles = []
    try:
        for name, command, directory in (
            ("backend", [sys.executable, "-m", server_module], ROOT / "backend"),
            (
                "frontend",
                [
                    "node",
                    "node_modules/vite/bin/vite.js",
                    *(["--config", "vite.fullstack.config.ts"] if server_module == "tests.e2e_server" else []),
                    "--host",
                    "127.0.0.1",
                    "--port",
                    "5174",
                    "--strictPort",
                ],
                ROOT / "frontend",
            ),
        ):
            handle = (logs / f"{name}.log").open("w", encoding="utf-8")
            handles.append(handle)
            processes.append(
                subprocess.Popen(
                    command,
                    cwd=directory,
                    env=environment,
                    stdout=handle,
                    stderr=subprocess.STDOUT,
                    creationflags=flags,
                )
            )
        for url in ("http://127.0.0.1:8002/api/v1/health/live", "http://127.0.0.1:5174"):
            deadline = time.monotonic() + 30
            while True:
                try:
                    with urllib.request.urlopen(url, timeout=1):
                        break
                except OSError:
                    if time.monotonic() >= deadline or any(
                        process.poll() is not None for process in processes
                    ):
                        raise RuntimeError(
                            f"Test server unavailable; synthetic logs: {logs}"
                        ) from None
                    time.sleep(0.2)
        return subprocess.run(
            [
                "node",
                "node_modules/@playwright/test/cli.js",
                "test",
                "--config",
                playwright_config,
                # Optional spec filters / Playwright flags, e.g. activities.spec.ts.
                *(arguments or []),
            ],
            cwd=ROOT / "frontend",
            env=environment,
            timeout=900,
            check=False,
        ).returncode
    finally:
        for process in processes:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
        for handle in handles:
            handle.close()


if __name__ == "__main__":
    raise SystemExit(run(sys.argv[1:]))
