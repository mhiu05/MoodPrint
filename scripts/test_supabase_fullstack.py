"""Run two authorized hosted fixtures through local HTTP/browser; never reset databases."""

import argparse
import base64
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "docs/plans/validation-artifacts"
REQUEST = ARTIFACTS / "supabase-restart-request.json"
ACK = ARTIFACTS / "supabase-restart-ack.json"


def ready(url, process):
    deadline = time.monotonic() + 40
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as response:
                if response.status == 200:
                    return
        except OSError:
            pass
        if process.poll() is not None:
            break
        time.sleep(0.2)
    raise RuntimeError("Owned hosted-test server unavailable; inspect sanitized local logs")


def stop(process):
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=8)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite", choices=("core", "scoped"), default="core")
    args = parser.parse_args()
    values = dotenv_values(ROOT / "backend/.env")
    if values.get("SUPABASE_URL") != "https://roznanxbiyqybjpvtilq.supabase.co":
        raise ValueError("Unexpected hosted test project")
    environment = {**os.environ, "AI_ENABLED": "false", "STT_ENABLED": "false",
                   "MOODPRINT_API_PROXY": "http://127.0.0.1:8003"}
    for actor in ("A", "B"):
        prefix = f"MOODPRINT_TEST_{actor}_"
        email, identity = values.get(prefix + "EMAIL"), values.get(prefix + "USER_ID")
        password = values.get(prefix + "PASSWORD")
        if values.get(prefix + "PASSWORD_B64"):
            password = base64.b64decode(values[prefix + "PASSWORD_B64"]).decode()
        if not email or not identity or not password:
            raise ValueError("Configure the two authorized test accounts locally first")
        environment.update({prefix + "EMAIL": email, prefix + "PASSWORD": password})
    environment["MOODPRINT_TEST_SUPABASE_URL"] = values["SUPABASE_URL"]
    environment["MOODPRINT_TEST_PUBLISHABLE_KEY"] = values["SUPABASE_PUBLISHABLE_KEY"]
    environment["MOODPRINT_HOSTED_REPORT"] = "evidence/supabase-scoped-results.json" if args.suite == "scoped" else "evidence/supabase-results.json"
    environment.pop("DEBUG", None)
    environment.pop("PWDEBUG", None)
    for port in (8003, 5176):
        with socket.socket() as check:
            check.bind(("127.0.0.1", port))
    for marker in (REQUEST, ACK):
        if marker.exists():
            marker.unlink()  # Exact owned non-secret marker files only.
    flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    logs = Path(tempfile.mkdtemp(prefix="moodprint-hosted-"))
    handles, processes = [], []

    def start_backend():
        handle = (logs / f"backend-{len(handles)}.log").open("w", encoding="utf-8")
        handles.append(handle)
        # Do not put test account passwords in the backend process environment.
        backend_env = {**os.environ, "AI_ENABLED": "false", "STT_ENABLED": "false"}
        process = subprocess.Popen([sys.executable, "-m", "tests.supabase_server"], cwd=ROOT / "backend",
            env=backend_env, stdout=handle, stderr=subprocess.STDOUT, creationflags=flags)
        processes.append(process)
        ready("http://127.0.0.1:8003/api/v1/health/ready", process)
        return process

    try:
        backend = start_backend()
        handle = (logs / "frontend.log").open("w", encoding="utf-8")
        handles.append(handle)
        frontend = subprocess.Popen(["node", "node_modules/vite/bin/vite.js", "--host", "127.0.0.1", "--port", "5176", "--strictPort"],
            cwd=ROOT / "frontend", env={**os.environ, "MOODPRINT_API_PROXY": "http://127.0.0.1:8003"},
            stdout=handle, stderr=subprocess.STDOUT, creationflags=flags)
        processes.append(frontend)
        ready("http://127.0.0.1:5176", frontend)
        browser = subprocess.Popen(["node", "node_modules/@playwright/test/cli.js", "test", "--config", "playwright.supabase.config.ts", "--grep", "hosted Nhịp" if args.suite == "scoped" else "hosted Auth"],
            cwd=ROOT / "frontend", env=environment, creationflags=flags)
        processes.append(browser)
        restarted = False
        deadline = time.monotonic() + 530
        while browser.poll() is None:
            if time.monotonic() >= deadline:
                raise TimeoutError("Hosted E2E reached its bounded deadline")
            if REQUEST.exists() and not restarted:
                old_pid = backend.pid
                stop(backend)
                backend = start_backend()
                ACK.write_text(json.dumps({"restarted": True, "oldPid": old_pid, "newPid": backend.pid}), encoding="utf-8")
                restarted = True
            time.sleep(0.2)
        return browser.returncode
    finally:
        for process in reversed(processes):
            stop(process)
        for handle in handles:
            handle.close()


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (Exception, KeyboardInterrupt) as error:
        print(json.dumps({"status": "failed", "errorType": type(error).__name__, "secretsPrinted": False}))
        sys.exit(1)
