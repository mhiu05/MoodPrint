"""Fail-closed local scale runner. No hosted, email or paid-provider execution.

Run using backend's Python 3.12. Each run requires a manifest and an owned disposable
PostgreSQL marker. T1/T2/T3/T4/T6 are local probes; T5/T7/T8 explicitly remain blocked.
An ASGI probe is not network/Caddy or production capacity evidence.
"""

import argparse
import asyncio
import hashlib
import json
import math
import os
import re
import subprocess
import sys
import time
import traceback
from collections import Counter, deque
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
FIELDS = {"run_id", "environment", "provider", "workers", "users", "duration_seconds",
          "warmup_seconds", "egress", "ai_daily_budget_usd", "accounting", "target"}


def validate_manifest(data, case, output):
    if not isinstance(data, dict) or not FIELDS <= set(data) or set(data) - FIELDS - {"reservation_profile"}:
        raise ValueError("Manifest fields must match the local schema; credentials are forbidden")
    if data["environment"] != "L0" or data["provider"] != "fake" or data["egress"] != "denied":
        raise ValueError("Only local fake-provider runs with denied egress are implemented")
    if data["workers"] != 1 or data["accounting"] is not True or data["ai_daily_budget_usd"] != 50:
        raise ValueError("One process, accounting and the approved $50 candidate are required")
    if data.get("reservation_profile", "legacy") not in ("legacy", "bounded64k"):
        raise ValueError("Unknown reservation profile")
    run_id = data["run_id"]
    if not isinstance(run_id, str) or not re.fullmatch(r"[0-9a-f]{32}", run_id) or run_id != os.environ.get("MOODPRINT_TEST_RUN_ID"):
        raise ValueError("Manifest must match the provisioned run ownership")
    target = data["target"]
    if not isinstance(target, dict) or set(target) != {"host", "port", "database"}:
        raise ValueError("Invalid target fields")
    if target["host"] != "127.0.0.1" or target["database"] != f"moodprint_{run_id}_test" or type(target["port"]) is not int or not 1024 <= target["port"] <= 65535:
        raise ValueError("Target must be this run's exact loopback disposable database")
    for key, lower, upper in (("users", 1, 1000), ("duration_seconds", 1, 7200), ("warmup_seconds", 0, 600)):
        if type(data[key]) is not int or not lower <= data[key] <= upper:
            raise ValueError("Invalid finite workload limits")
    if case not in {"T1", "T2", "T3", "T4", "T6", "cleanup"}:
        raise ValueError("Case is not implemented; T5 requires verified quota/pricing/campaign controls and T7/T8 require mixed/fault fixtures")
    if output.exists() or output.suffix != ".json":
        raise ValueError("Output must be a new JSON artifact; overwriting evidence is forbidden")
    return data


def resolve_database(data):
    import psycopg
    from tests.database_target import require_local_test_database, verify_test_database_sync

    url = require_local_test_database(os.environ.get("TEST_DATABASE_URL", ""))
    target = data["target"]
    if (url.host, url.port, url.database) != (target["host"], target["port"], target["database"]):
        raise ValueError("Runner target and manifest do not match")
    with psycopg.connect(url.set(drivername="postgresql").render_as_string(hide_password=False), connect_timeout=5) as connection:
        verify_test_database_sync(connection)
    return url


def deny_external_egress():
    # A process-wide audit fence also catches accidentally enabled auxiliary providers.
    def audit(event, args):
        if event == "socket.getaddrinfo" and args[0] not in ("127.0.0.1", "::1", "localhost", None):
            raise RuntimeError("External DNS denied by local scale runner")
        if event == "socket.connect" and isinstance(args[1], tuple) and args[1][0] not in ("127.0.0.1", "::1"):
            raise RuntimeError("External connection denied by local scale runner")
    sys.addaudithook(audit)


def percentiles(values):
    if not values:
        return {"count": 0, "p50_ms": None, "p95_ms": None, "p99_ms": None}
    ordered = sorted(values)
    return {"count": len(ordered), **{f"p{q}_ms": round(ordered[max(0, math.ceil(len(ordered)*q/100)-1)], 3) for q in (50, 95, 99)}}


def failure_location(error):
    # Frame names and line numbers only: no source lines, locals, provider body or DSN.
    return [{"file": Path(frame.filename).name, "function": frame.name, "line": frame.lineno}
            for frame in traceback.extract_tb(error.__traceback__)]


def git_provenance():
    try:
        return {
            "head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, stderr=subprocess.DEVNULL).strip(),
            "working_tree_dirty": bool(subprocess.check_output(["git", "status", "--porcelain", "--untracked-files=no"], cwd=ROOT, text=True, stderr=subprocess.DEVNULL)),
        }
    except (OSError, subprocess.CalledProcessError):
        # Minimal Linux images may have no git. The source tree hash still identifies
        # the exact tested bytes; do not invent a clean checkout or commit identity.
        return {"head": "UNKNOWN", "working_tree_dirty": "UNKNOWN"}


def isolate_settings():
    from app.core.config import Settings
    from tests.settings_baseline import ALL_FEATURES_OFF

    Settings.model_config["env_file"] = None
    os.environ.update({name.upper(): str(value).lower() for name, value in ALL_FEATURES_OFF.items()})
    os.environ.update({name: "" for name in ("DATABASE_URL", "DATABASE_MIGRATION_URL", "OPENAI_API_KEY",
                                           "SUPABASE_URL", "SUPABASE_PUBLISHABLE_KEY", "JOURNAL_STORAGE_KEY",
                                           "VOYAGE_API_KEY", "APIFY_API_TOKEN")})
    os.environ.update(APP_ENV="test", MOODPRINT_LOAD_POOL_SIZE="4", MOODPRINT_LOAD_POOL_OVERFLOW="1",
                      MOODPRINT_LOAD_MODEL_DELAY="16", MOODPRINT_LOAD_WORKERS="1", DATABASE_POOL_METRICS_ENABLED="true")


async def auth_probe(data, shared_app=None):
    import httpx
    from app.core.config import Settings
    from app.main import create_app
    from app.modules.auth.routes import EMAIL_LIMIT

    EMAIL_LIMIT.attempts.clear()
    own = shared_app is None
    app = shared_app or create_app(Settings(_env_file=None))
    settings = app.state.settings
    settings.supabase_url, settings.supabase_publishable_key = "https://synthetic.invalid", __import__("pydantic").SecretStr("synthetic")
    settings.auth_captcha_enabled = settings.auth_nat_policy_enabled = True
    provider_accepted = 0

    def fake(request):
        nonlocal provider_accepted
        body = json.loads(request.content)
        if body.get("gotrue_meta_security", {}).get("captcha_token") != "synthetic-valid":
            return httpx.Response(422, json={"error_code": "captcha_failed"})
        provider_accepted += 1
        return httpx.Response(200, json={})

    app.state.auth_transport = httpx.MockTransport(fake)
    durations, statuses = [], Counter()
    count = data["users"]
    started = time.monotonic()

    async def one(index):
        # Distributed peers are ASGI fixtures, not forged XFF or real distributed egress.
        peer = f"198.51.100.{index % 200 + 1}" if data.get("case") == "T2" else "198.51.100.1"
        await asyncio.sleep(index * data["duration_seconds"] / count)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app, client=(peer, 12000)), base_url="http://test") as client:
            at = time.monotonic()
            response = await client.post("/api/v1/auth/signup", json={
                "email": f"scale-{index}@example.com", "password": "synthetic-password",
                "captchaToken": "synthetic-valid", "eligibility": {"birthYear": 2000,
                    "confirmedMinimumAge": True, "confirmedAdultAge": True, "expectedVersion": 0,
                    "policyVersion": "self-declared-age-v2-18plus"}})
            durations.append((time.monotonic()-at)*1000)
            statuses[str(response.status_code)] += 1
    try:
        await asyncio.gather(*(one(i) for i in range(count)))
        return {"scope": "ASGI application admission with fake CAPTCHA/Auth; no identities or mail created",
                "status": "LOCAL_SYNTHETIC_PASS" if statuses.get("202") == count else "FAILED",
                "requests": count, "statuses": dict(statuses), "provider_mock_accepted": provider_accepted,
                "created_accounts": None, "delivered_emails": None, "confirmed_accounts": None,
                "latency": percentiles(durations), "wall_seconds": round(time.monotonic()-started, 3),
                "arrival_window_seconds": data["duration_seconds"], "cpu_rss": "not sampled for ASGI-only auth probe"}
    finally:
        if own:
            await app.state.ai.close()


async def database_probe(data):
    from app.infrastructure.database.models import AuthSession, Consent, User
    from sqlalchemy import func, select, text
    from tests import chat_load_server as fixture

    await fixture.seed(data["users"])
    db = fixture.app.state.database
    try:
        async with db.sessions() as session:
            counts = {name: int(await session.scalar(select(func.count()).select_from(model)))
                      for name, model in (("users", User), ("sessions", AuthSession), ("consents", Consent))}
            size = int(await session.scalar(text("select pg_database_size(current_database())")))
        return {"status": "LOCAL_SYNTHETIC_PASS" if counts["users"] == data["users"] and counts["consents"] == data["users"]*4 else "FAILED",
                "scope": "Synthetic app accounts/sessions/consents only; Auth confirmation and 30/90-day journal/vector growth NOT validated",
                "counts": counts, "database_bytes": size, "growth_profile_complete": False}
    finally:
        await fixture.app.state.ai.close()
        await db.engine.dispose()


async def ai_probe(data):
    import httpx
    from app.ai.accounting import budget_liability
    from app.core.capacity import ai_capacity_fingerprint
    from app.infrastructure.database.models import AiRun, now
    from sqlalchemy import func, select
    from tests import chat_load_server as fixture

    app = fixture.app
    s = app.state.settings
    s.ai_daily_budget_usd, s.ai_accounting_enabled, s.openai_model = 50, True, "gpt-6-luna"
    s.ai_dispatch_gate_enabled = True
    s.ai_bounded_reservations_enabled = data.get("reservation_profile") == "bounded64k"
    s.ai_timeout_seconds = 60
    from app.ai.provider import SdkProvider
    await app.state.ai.provider.aclose()
    app.state.ai.provider = SdkProvider(s)
    from tests.scale_readiness_server import scale_model
    app.state.ai.model_override = scale_model()
    await fixture.seed(data["users"])
    peaks = {"parent_turns": 0, "sse_streams": 0, "provider_active": 0, "liability_nano": 0,
             "pool_checked_out": 0, "rss_bytes": 0}
    stop = asyncio.Event()
    durations, statuses, errors = [], Counter(), Counter()
    parent_samples = []
    loop_lags = deque(maxlen=20000)
    stop_arrivals = asyncio.Event()

    async def measure_loop():
        while not stop.is_set():
            at = time.monotonic()
            await asyncio.sleep(0.1)
            loop_lags.append(max(0, time.monotonic() - at - 0.1) * 1000)

    async def sample():
        while not stop.is_set():
            peaks["provider_active"] = max(peaks["provider_active"], fixture.COUNTERS["sdk_active"])
            peaks["sse_streams"] = max(peaks["sse_streams"], app.state.ai.streams.open())
            peaks["rss_bytes"] = max(peaks["rss_bytes"], fixture.rss_bytes())
            peaks["pool_checked_out"] = max(peaks["pool_checked_out"], app.state.database.engine.pool.checkedout())
            async with app.state.database.sessions() as session:
                active = await session.scalar(select(func.count()).select_from(AiRun).where(AiRun.status == "running", AiRun.parent_run_id.is_(None)))
                liability = await budget_liability(session, now())
                peaks["parent_turns"] = max(peaks["parent_turns"], int(active or 0))
                peaks["liability_nano"] = max(peaks["liability_nano"], liability)
                parent_samples.append((time.monotonic(), int(active or 0)))
            try:
                # Resource/DB sampling at1Hz, per plan; the sampler must not add a
                # second high-frequency liability scan beside production polling.
                await asyncio.wait_for(stop.wait(), timeout=1)
            except TimeoutError:
                pass

    async def turn(client, number):
        headers = {"Cookie": f"moodprint_session=load-session-{number}", "X-CSRF-Token": f"load-csrf-{number}",
                   "Idempotency-Key": str(uuid4())}
        created = await client.post("/api/v1/ai/conversations", headers=headers, json={"botId": "may", "persistent": True})
        if created.status_code != 201:
            errors["create_failed"] += 1
            return False
        cid = created.json()["conversationId"]
        at = time.monotonic()
        headers["Idempotency-Key"] = str(uuid4())
        response = await client.post(f"/api/v1/ai/conversations/{cid}/messages", headers=headers,
                                     json={"text": f"LOAD_ACTOR:{number:03d} BOT:may", "clientMessageId": str(uuid4()), "expectedConversationVersion": 1})
        statuses[str(response.status_code)] += 1
        if response.status_code != 202:
            errors[response.json().get("error", {}).get("code", "unknown")] += 1
            durations.append((time.monotonic()-at)*1000)
            return False
        events = await client.get(response.json()["eventsUrl"], headers=headers)
        durations.append((time.monotonic()-at)*1000)
        if '"completed"' not in events.text:
            errors["noncompleted_stream"] += 1
            return False
        return True

    started = time.monotonic()
    cpu_started = time.process_time()
    monitor = asyncio.create_task(sample())
    loop_monitor = asyncio.create_task(measure_loop())
    outcome = []
    mixed_auth = None
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test", timeout=60) as client:
            if data.get("case") == "T6":
                # Same app but a separate transport for synthetic Auth, never real email.
                auth_data = {**data, "users": 100, "duration_seconds": 60}
                # Lifespan HTTP pool was not started; the test adapter owns its fake pool.
                mixed_auth = asyncio.create_task(auth_probe(auth_data, app))
            async def user_worker(number):
                while not stop_arrivals.is_set() and time.monotonic() - started < data["warmup_seconds"] + data["duration_seconds"]:
                    try:
                        ok = await turn(client, number)
                    except Exception as error:
                        # Retain workload metrics on failure; never retry a possibly
                        # admitted provider operation to make the run look successful.
                        errors[f"exception:{type(error).__module__}.{type(error).__name__}"] += 1
                        ok = False
                    outcome.append(ok)
                    if not ok:
                        stop_arrivals.set()
            await asyncio.gather(*(user_worker(i) for i in range(data["users"])))
            # A failed first cohort stops the soak; never reset the ledger to make it pass.
            if mixed_auth:
                mixed_auth = await mixed_auth
        window_start = started + data["warmup_seconds"]
        window_end = window_start + data["duration_seconds"]
        window_samples = [active for at, active in parent_samples if window_start <= at < window_end]
        area = 0.0
        for (at, active), (next_at, _) in zip(parent_samples, parent_samples[1:], strict=False):
            area += active * max(0, min(next_at, window_end) - max(at, window_start))
        sampled_duration = max(0, min(time.monotonic(), window_end) - window_start)
        occupancy = area / sampled_duration if sampled_duration else 0
        elapsed = time.monotonic() - started
        passed = all(outcome) and peaks["parent_turns"] >= data["users"] and occupancy >= data["users"] * 0.9 and elapsed >= data["duration_seconds"] + data["warmup_seconds"]
        return {"status": "LOCAL_SYNTHETIC_PASS" if passed else "FAILED",
                "scope": "single-agent saved turns + ASGI SSE; real PostgreSQL/financial guards, fake SDK Model/embeddings; exact-count HTTP guard is separately unit-tested with mock transport, NOT exercised by this Model override; no socket/Caddy, multi-agent or production proof",
                "requested_users": data["users"], "requested_duration_seconds": data["duration_seconds"],
                "measured_wall_seconds": round(elapsed, 3), "completed": sum(outcome),
                "mean_parent_occupancy": round(occupancy, 2), "occupancy_samples": len(window_samples),
                "measured_window_seconds": round(sampled_duration, 3),
                "measurement_method": "time-weighted sampled parent count; warmup/drain excluded",
                "event_loop_lag": percentiles(loop_lags),
                "process_cpu_seconds": round(time.process_time() - cpu_started, 3),
                "pool_acquisition_recent_window": app.state.database.pool_metrics(),
                "simulated_provider_usage": {"input_tokens": 8000, "output_tokens": 600},
                "attempts": len(outcome), "statuses": dict(statuses), "errors": dict(errors), "peaks": peaks,
                "latency_including_rejections": percentiles(durations), "fingerprint": ai_capacity_fingerprint(s),
                "financial_invariant": peaks["liability_nano"] <= 50_000_000_000,
                "soak_stopped_on_failed_first_cohort": not all(outcome), "mixed_auth": mixed_auth}
    finally:
        stop.set()
        await asyncio.gather(monitor, loop_monitor, return_exceptions=True)
        if isinstance(mixed_auth, asyncio.Task):
            mixed_auth.cancel()
            await asyncio.gather(mixed_auth, return_exceptions=True)
        await app.state.ai.close()
        await app.state.database.engine.dispose()


async def run_case(data, case):
    isolate_settings()
    deny_external_egress()
    data = {**data, "case": case}
    if case in ("T2", "T3"):
        return await auth_probe(data)
    if case == "T1":
        return await database_probe(data)
    return await ai_probe(data)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run")
    run.add_argument("--case", required=True, choices=[f"T{i}" for i in range(1, 9)])
    run.add_argument("--manifest", type=Path, required=True)
    run.add_argument("--output", type=Path, required=True)
    cleanup = commands.add_parser("cleanup")
    cleanup.add_argument("--run-id", required=True)
    cleanup.add_argument("--manifest", type=Path, required=True)
    cleanup.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    output = args.output if args.command == "run" else args.report
    try:
        data = json.loads(args.manifest.read_text(encoding="utf8"))
        validate_manifest(data, args.case if args.command == "run" else "cleanup", output)
        if args.command == "cleanup" and args.run_id != data["run_id"]:
            raise ValueError("Cleanup ownership mismatch")
        os.environ["APP_ENV"] = "test"
        resolve_database(data)
    except (ValueError, OSError, RuntimeError):
        print("Scale run refused: invalid manifest, target, ownership, output or unsupported case", file=sys.stderr)
        return 2
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf8") as artifact:
        source_hash = hashlib.sha256()
        for path in sorted([*(ROOT / "backend/app").rglob("*.py"), *(ROOT / "backend/tests").rglob("*.py"), ROOT / "scripts/scale_readiness.py"]):
            source_hash.update(path.relative_to(ROOT).as_posix().encode())
            source_hash.update(hashlib.sha256(path.read_bytes()).digest())
        report = {"at_utc": datetime.now(UTC).isoformat(), "run_id": data["run_id"], "case": getattr(args, "case", "cleanup"),
                  "environment": "L0", "real_generation_calls": 0, "external_generation_spend_usd": 0,
                  **git_provenance()}
        report["source_sha256"] = source_hash.hexdigest()
        try:
            if args.command == "cleanup":
                # Existing provisioner rechecks UUID/label/tmpfs before container removal.
                result = subprocess.run([sys.executable, str(ROOT / "scripts/disposable_postgres.py"), "--remove", args.run_id], capture_output=True)
                report["result"] = {"status": "CLEANED" if result.returncode == 0 else "CLEANUP_FAILED"}
            else:
                factory = asyncio.SelectorEventLoop if sys.platform == "win32" else None
                report["result"] = asyncio.run(run_case(data, args.case), loop_factory=factory)
        except Exception as error:
            # Driver exceptions and request bodies may carry secrets. Never serialize them.
            report["result"] = {"status": "FAILED", "error_type": type(error).__name__,
                                "error_module": type(error).__module__,
                                "location": failure_location(error)}
        json.dump(report, artifact, indent=2)
        artifact.write("\n")
    print(json.dumps({"case": report["case"], "status": report["result"]["status"], "artifact": str(output)}))
    return 0 if report["result"]["status"] in ("LOCAL_SYNTHETIC_PASS", "CLEANED") else 1


if __name__ == "__main__":
    raise SystemExit(main())
