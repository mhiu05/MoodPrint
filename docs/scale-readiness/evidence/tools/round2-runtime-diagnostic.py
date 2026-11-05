"""Static SSM payload: bounded read-only host/container metadata; no secrets/logs."""
import json
import re
import subprocess
from datetime import UTC, datetime
from pathlib import Path


def run(args):
    result = subprocess.run(args, capture_output=True, text=True, timeout=15, check=False)
    return result.stdout if result.returncode == 0 else ""


def main():
    report = {"observed_at_utc": datetime.now(UTC).isoformat(), "read_only": True}
    report["uptime_seconds"] = float(Path("/proc/uptime").read_text().split()[0])
    mem = {key: int(value.split()[0]) * 1024 for key, value in
           (line.split(":", 1) for line in Path("/proc/meminfo").read_text().splitlines())}
    report["host_memory_bytes"] = {key: mem[key] for key in ("MemTotal", "MemAvailable", "SwapTotal", "SwapFree")}
    report["load_average"] = [float(v) for v in Path("/proc/loadavg").read_text().split()[:3]]
    report["docker_available"] = bool(run(["docker", "version", "--format", "{{.Server.Version}}"])); containers = []
    ids = run(["docker", "ps", "-q", "--filter", "label=com.docker.compose.project=moodprint-staging"]).split()
    for container_id in ids:
        raw = run(["docker", "inspect", "--format", '{{json .State.Status}}|{{json .State.Health.Status}}|{{.RestartCount}}|{{.Image}}|{{index .Config.Labels "com.docker.compose.service"}}', container_id])
        parts = raw.strip().split("|")
        if len(parts) != 5 or parts[4] not in {"api", "web", "proactive", "maps"}:
            continue
        status, health, restarts, digest, service = parts
        entry = {"service": service, "status": json.loads(status), "health": json.loads(health),
                 "restart_count": int(restarts), "image_id": digest if re.fullmatch(r"sha256:[a-f0-9]{64}", digest) else "redacted"}
        if service in {"api", "proactive", "maps"}:
            # Only known numeric/boolean names are accessed. No environment object is emitted.
            code = "import os,json,re;names=('AI_GLOBAL_CONCURRENCY','AI_USER_CONCURRENCY','AI_TIMEOUT_SECONDS','AI_DAILY_BUDGET_USD','AI_ACCOUNTING_ENABLED','DATABASE_POOL_SIZE','DATABASE_POOL_OVERFLOW','DATABASE_POOL_TIMEOUT','PROACTIVE_WORKER_ENABLED','AUTH_CAPTCHA_ENABLED');print(json.dumps({k:(os.environ[k] if re.fullmatch(r'[0-9]+(?:\\.[0-9]+)?|true|false',os.environ[k],re.I) else 'non_numeric_redacted') for k in names if k in os.environ}))"
            selected = run(["docker", "exec", container_id, "/srv/moodprint/.venv/bin/python", "-c", code])
            entry["configured_allowlist"] = json.loads(selected) if selected else {"status": "unavailable"}
        stats = run(["docker", "stats", "--no-stream", "--format", "{{json .}}", container_id])
        if stats:
            data = json.loads(stats); entry["resource_snapshot"] = {key: data[key] for key in ("CPUPerc", "MemUsage", "MemPerc", "PIDs")}
        containers.append(entry)
    report["containers"] = containers
    report["release_poller_active"] = run(["systemctl", "is-active", "moodprint-release-poll.timer"]).strip() == "active"
    report["five_xx_aggregate"] = {"status": "unknown", "reason": "no log bodies read and no aggregate metric endpoint identified"}
    print(json.dumps(report))


try:
    main()
except Exception as error:  # noqa: BLE001 - suppress all potentially sensitive diagnostics.
    print(json.dumps({"status": "diagnostic_failed", "error_type": type(error).__name__, "details_suppressed": True}))
