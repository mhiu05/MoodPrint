"""Run headless Phase 1 E2E against the existing local Supabase stack.

Never reads the owner's .env, starts/resets Docker, or changes Supabase settings.
Bootstrap .local/test.env first. Every child receives a fresh local-only environment.
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import socket
import subprocess
import sys
import time
from contextlib import contextmanager
from pathlib import Path
from urllib.error import URLError
from urllib.parse import urlsplit
from urllib.request import urlopen

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
FRONTEND_URL = "http://127.0.0.1:5178"
API_URL = "http://127.0.0.1:8008"
LOOPBACK = {"127.0.0.1", "localhost", "::1"}
OS_ENVIRONMENT = {
    "PATH",
    "PATHEXT",
    "SYSTEMROOT",
    "WINDIR",
    "COMSPEC",
    "TEMP",
    "TMP",
    "USERPROFILE",
    "APPDATA",
    "LOCALAPPDATA",
    "PROGRAMFILES",
    "PROGRAMFILES(X86)",
    "HOME",
    "LANG",
    "LC_ALL",
    "TERM",
    "CI",
    "NUMBER_OF_PROCESSORS",
}


def require_loopback(value: str, name: str) -> None:
    try:
        parsed = urlsplit(value)
        safe = (
            not parsed.query
            and not parsed.fragment
            and parsed.hostname in LOOPBACK
            and parsed.scheme
            in {
                "http",
                "postgresql",
                "postgresql+asyncpg",
                "postgres",
            }
        )
    except ValueError:
        safe = False
    if not safe:
        raise ValueError(f"{name} must use a local loopback endpoint")


def read_local_environment(path: Path) -> dict[str, str]:
    path = path.resolve()
    if not path.is_relative_to((ROOT / ".local").resolve()):
        raise ValueError("The environment file must be inside .local; owner dotenv is forbidden")
    if not path.is_file():
        raise ValueError(".local/test.env is missing; run scripts/dev/bootstrap_local_db.py first")
    # No interpolation: a dotenv value must never expand an inherited owner secret.
    return {
        key: value
        for key, value in dotenv_values(path, interpolate=False).items()
        if value is not None
    }


def build_environment(local: dict[str, str], inherited: dict[str, str]) -> dict[str, str]:
    required = (
        "SUPABASE_URL",
        "SUPABASE_PUBLISHABLE_KEY",
        "SUPABASE_SECRET_KEY",
        "DATABASE_URL",
        "TEST_DATABASE_URL",
        "TEST_ADMIN_DATABASE_URL",
    )
    for name in required:
        if not local.get(name):
            raise ValueError(f"{name} is missing from .local/test.env")
    if local.get("APP_ENV") != "test":
        raise ValueError("APP_ENV must be test in .local/test.env")
    for name in ("SUPABASE_URL", "DATABASE_URL", "TEST_DATABASE_URL", "TEST_ADMIN_DATABASE_URL"):
        require_loopback(local[name], name)
    child = {key: value for key, value in inherited.items() if key.upper() in OS_ENVIRONMENT}
    child.update({name: local[name] for name in required})
    if local.get("AUTH_TEST_JWT_SECRET"):
        child["AUTH_TEST_JWT_SECRET"] = local["AUTH_TEST_JWT_SECRET"]
    child.update(
        {
            "APP_ENV": "test",
            "PYTHONUNBUFFERED": "1",
            "PYTHONIOENCODING": "utf-8",
            "CORS_ALLOWED_ORIGINS": FRONTEND_URL,
            "VITE_PUBLIC_SUPABASE_URL": local["SUPABASE_URL"],
            "VITE_PUBLIC_SUPABASE_PUBLISHABLE_KEY": local["SUPABASE_PUBLISHABLE_KEY"],
            "VITE_PUBLIC_API_BASE_URL": API_URL,
            "E2E_BASE_URL": FRONTEND_URL,
            "E2E_API_URL": API_URL,
            "E2E_SUPABASE_URL": local["SUPABASE_URL"],
            "E2E_MAIL_URL": "http://127.0.0.1:54324",
            "E2E_STACK_MANAGED": "1",
            "CAPTURE_SCREENSHOTS": "0",
        }
    )
    return child


def wait_ready(url: str, process: subprocess.Popen | None = None, timeout: int = 60) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process is not None and process.poll() is not None:
            raise RuntimeError(
                "Local child process exited before readiness; inspect .local/e2e logs"
            )
        try:
            with urlopen(url, timeout=2) as response:
                if response.status == 200:
                    return
        except (URLError, OSError):
            pass
        time.sleep(0.25)
    raise RuntimeError("Local endpoint did not become ready; inspect .local/e2e logs")


def assert_port_free(port: int) -> None:
    with socket.socket() as connection:
        if connection.connect_ex(("127.0.0.1", port)) == 0:
            raise RuntimeError(
                f"Port {port} is already occupied; stop its owner before running the isolated harness"
            )


def vite_config() -> Path:
    directory = ROOT / ".local/e2e"
    empty_env = directory / "empty-env"
    empty_env.mkdir(parents=True, exist_ok=True)
    path = directory / "vite.config.mts"
    original = (ROOT / "frontend/vite.config.ts").as_posix()
    path.write_text(
        f"import config from {json.dumps(original)};\nexport default {{ ...config, envDir: {json.dumps(empty_env.as_posix())} }};\n",
        encoding="utf-8",
    )
    return path


def stop_child(process: subprocess.Popen) -> None:
    if process.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    else:
        os.killpg(process.pid, signal.SIGTERM)
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()


@contextmanager
def running_stack(environment: dict[str, str], *, demo: bool = False):
    for port in (5178,) if demo else (8008, 5178):
        assert_port_free(port)
    if not demo:
        wait_ready(environment["SUPABASE_URL"] + "/auth/v1/health", timeout=8)
    output = ROOT / ".local/e2e"
    output.mkdir(parents=True, exist_ok=True)
    npm = "npm.cmd" if os.name == "nt" else "npm"
    commands = []
    if not demo:
        commands.append(
            (
                [
                    sys.executable,
                    "-c",
                    "import uvicorn; uvicorn.run('app.main:create_app', factory=True, host='127.0.0.1', port=8008, access_log=False)",
                ],
                ROOT,
                "api",
                API_URL + "/ready",
            )
        )
    commands.append(
        (
            [
                npm,
                "run",
                "dev",
                "--",
                "--config",
                str(vite_config()),
                "--mode",
                "test",
                "--host",
                "127.0.0.1",
                "--port",
                "5178",
                "--strictPort",
            ],
            ROOT / "frontend",
            "vite",
            FRONTEND_URL,
        )
    )
    processes: list[subprocess.Popen] = []
    handles = []
    try:
        for command, cwd, name, ready in commands:
            handle = (output / f"{name}.log").open("w", encoding="utf-8")
            handles.append(handle)
            process = subprocess.Popen(
                command,
                cwd=cwd,
                env=environment,
                stdout=handle,
                stderr=subprocess.STDOUT,
                start_new_session=os.name != "nt",
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
            processes.append(process)
            wait_ready(ready, process)
        print(
            f"Isolated E2E ready: frontend {FRONTEND_URL}; API {API_URL if not demo else 'unused (demo)'}. No database reset.",
            flush=True,
        )
        yield processes
    finally:
        for process in reversed(processes):
            stop_child(process)
        for handle in handles:
            handle.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--run", action="store_true", help="Run headless Playwright and stop child processes"
    )
    parser.add_argument("--project", choices=["real", "demo", "all"], default="real")
    parser.add_argument("--env-file", type=Path, default=ROOT / ".local/test.env")
    parser.add_argument("--grep", help="Run matching Playwright test titles")
    args = parser.parse_args()
    try:
        projects = ("demo", "real") if args.project == "all" else (args.project,)
        status = 0
        for project in projects:
            environment = build_environment(read_local_environment(args.env_file), dict(os.environ))
            if project == "demo":
                for name in tuple(environment):
                    if name.startswith("VITE_PUBLIC_"):
                        environment[name] = ""
            environment["PLAYWRIGHT_HTML_OUTPUT_DIR"] = str(ROOT / f".local/e2e/report-{project}")
            with running_stack(environment, demo=project == "demo") as processes:
                if not args.run:
                    print("Press Ctrl+C to stop the local API and Vite children.", flush=True)
                    while True:
                        time.sleep(1)
                npx = "npx.cmd" if os.name == "nt" else "npx"
                command = [
                    npx,
                    "playwright",
                    "test",
                    "--workers=1",
                    f"--project={project}",
                    "--output",
                    str(ROOT / f".local/e2e/results-{project}"),
                ]
                if args.grep != "E-URG-01":
                    command.extend(["--grep-invert", "E-URG-01"])
                    if args.grep:
                        command.extend(["--grep", args.grep])
                    status = max(
                        status,
                        subprocess.run(
                            command, cwd=ROOT / "frontend", env=environment, check=False
                        ).returncode,
                    )
                if project == "real" and (not args.grep or args.grep == "E-URG-01"):
                    # Prove urgent help works with the actual API child stopped.
                    stop_child(processes[0])
                    environment["E2E_URGENT_BACKEND_STOPPED"] = "1"
                    environment["PLAYWRIGHT_HTML_OUTPUT_DIR"] = str(
                        ROOT / ".local/e2e/report-urgent"
                    )
                    urgent = [
                        npx,
                        "playwright",
                        "test",
                        "--workers=1",
                        "--project=real",
                        "--grep",
                        "E-URG-01",
                        "--output",
                        str(ROOT / ".local/e2e/results-urgent"),
                    ]
                    status = max(
                        status,
                        subprocess.run(
                            urgent, cwd=ROOT / "frontend", env=environment, check=False
                        ).returncode,
                    )
        return status
    except (ValueError, RuntimeError) as error:
        print(str(error), file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
