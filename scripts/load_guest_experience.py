"""One-worker 50-visitor synthetic guest load, bounded admission, crash and quarantined restore."""

import argparse
import asyncio
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
from collections import Counter, defaultdict
from pathlib import Path
from uuid import uuid4

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))


def validate_target(raw, *, workers, users):
    from tests.database_target import require_local_test_database
    try:
        target = require_local_test_database(raw)
    except RuntimeError:
        raise ValueError("Explicit loopback PostgreSQL *_test target required") from None
    if target.query:
        raise ValueError("Connection overrides are refused")
    if workers != 1 or users != 50:
        raise ValueError("This proof requires exactly one worker and 50 visitors")
    return target


async def run(args):
    raw = os.environ.get("TEST_DATABASE_URL", "")
    target = validate_target(raw, workers=args.workers, users=args.users)
    with socket.socket() as probe:
        try:
            probe.bind(("127.0.0.1", args.port))
        except OSError:
            raise RuntimeError("Occupied port; existing process will not be touched") from None
    from load_chat_memory import summarize

    from tests import guest_load_server as fixture
    from tests.test_voice import audio
    deadline = await fixture.seed(50)
    logs = Path(tempfile.mkdtemp(prefix="moodprint-guest-load-"))
    handle = (logs / "server.log").open("w", encoding="utf-8")
    env = {**os.environ, "MOODPRINT_GUEST_LOAD_PORT": str(args.port)}
    flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    process = None
    timings, statuses, peaks = defaultdict(list), Counter(), {}
    base = f"http://127.0.0.1:{args.port}"

    def start():
        return subprocess.Popen([sys.executable, "-m", "tests.guest_load_server"], cwd=ROOT / "backend",
                                env=env, stdout=handle, stderr=subprocess.STDOUT, creationflags=flags)

    async def stop(kill=False):
        if process and process.poll() is None:
            process.kill() if kill else process.terminate()
            await asyncio.to_thread(process.wait, timeout=10)

    def headers(number, registered=False):
        return {"Cookie": f"moodprint_session={'e2e-synthetic-session-50' if registered else f'guest-load-session-{number}'}",
                "X-CSRF-Token": "e2e-synthetic-csrf-50" if registered else f"guest-load-csrf-{number}",
                "Idempotency-Key": str(uuid4())}

    async with httpx.AsyncClient(base_url=base, timeout=30, trust_env=False, limits=httpx.Limits(max_connections=100)) as client:
        async def ready():
            until = time.monotonic() + 30
            while time.monotonic() < until:
                try:
                    if (await client.get("/api/v1/health/live")).status_code == 200:
                        return
                except httpx.HTTPError:
                    pass
                await asyncio.sleep(0.2)
            raise RuntimeError(f"Owned server unavailable; logs: {logs}")

        async def request(kind, number, method, path, **kwargs):
            before = time.perf_counter()
            response = await client.request(method, path, headers=headers(number), **kwargs)
            timings[kind].append((time.perf_counter() - before) * 1000)
            statuses[f"{kind}:{response.status_code}"] += 1
            assert response.status_code < 500, f"{kind} server error {response.status_code}"
            return response

        async def sample():
            snapshot = (await client.get("/__synthetic/stats")).json()
            for key, value in snapshot.items():
                peaks[key] = max(peaks.get(key, 0), value)
            assert snapshot["aiPeak"] <= 10 and snapshot["voicePeak"] <= 3
            return snapshot

        try:
            process = start()
            await ready()
            async def personal(number):
                session = await request("browse", number, "GET", "/api/v1/session")
                assert session.status_code == 200
                day = session.json()["serverTime"][:10]
                mood = await request("journal", number, "PUT", f"/api/v1/moods/{day}", json={"value": 3, "note": f"SYNTHETIC-OWNER-{number}", "timezone": "Asia/Bangkok", "expectedVersion": 0})
                assert mood.status_code == 200
                own = await request("read", number, "GET", "/api/v1/moods")
                assert [row["note"] for row in own.json()] == [f"SYNTHETIC-OWNER-{number}"]
                for purpose in ("AI", "VOICE"):
                    consent = await request("consent", number, "PUT", f"/api/v1/consents/{purpose}", json={"enabled": True, "expectedVersion": 1, "policyVersion": "v1"})
                    assert consent.status_code == 200
                created = await request("conversation", number, "POST", "/api/v1/ai/conversations", json={"botId": "may"})
                assert created.status_code == 201
                return created.json()
            conversations = await asyncio.gather(*(personal(n) for n in range(50)))

            async def paid(number):
                conversation = conversations[number]
                accepted = await request("ai", number, "POST", f"/api/v1/ai/conversations/{conversation['conversationId']}/messages", json={"text": "Synthetic load", "clientMessageId": str(uuid4()), "expectedConversationVersion": conversation["version"]})
                assert accepted.status_code in (202, 429), accepted.text
                if accepted.status_code == 429:
                    assert "retry-after" in accepted.headers
                else:
                    stream = await request("sse", number, "GET", accepted.json()["eventsUrl"])
                    assert "event: final" in stream.text and "RAW-SYNTHETIC" not in stream.text
            tasks = [asyncio.create_task(paid(n)) for n in range(50)]
            async def voice(number):
                before = time.perf_counter()
                response = await client.post("/api/v1/voice/transcriptions", content=audio(), headers={**headers(number), "Content-Type": "audio/wav"})
                timings["voice"].append((time.perf_counter() - before) * 1000)
                statuses[f"voice:{response.status_code}"] += 1
                assert response.status_code in (200, 429), response.status_code
            tasks += [asyncio.create_task(voice(n)) for n in range(50)]
            while not all(task.done() for task in tasks):
                await sample()
                before = time.perf_counter()
                canary = await client.get("/api/v1/session", headers=headers(0, True))
                timings["registeredCanary"].append((time.perf_counter() - before) * 1000)
                assert canary.status_code == 200
                await asyncio.sleep(0.05)
            await asyncio.gather(*tasks)
            assert statuses["ai:202"] > 0 and statuses["ai:429"] > 0
            assert statuses["voice:200"] > 0 and statuses["voice:429"] > 0
            crash = None
            if args.crash_kill:
                c = (await request("crashConversation", 0, "POST", "/api/v1/ai/conversations", json={"botId": "may"})).json()
                accepted = await request("crashAccept", 0, "POST", f"/api/v1/ai/conversations/{c['conversationId']}/messages", json={"text": "HOLD-FOR-CRASH", "clientMessageId": str(uuid4()), "expectedConversationVersion": c["version"]})
                assert accepted.status_code == 202
                for _ in range(100):
                    if (await sample())["aiActive"]:
                        break
                    await asyncio.sleep(0.05)
                else:
                    raise AssertionError("Crash target never reached the synthetic provider")
                await stop(kill=True)
                process = start()
                await ready()
                snapshot = await sample()
                assert snapshot["aiCalls"] == 0, "restart replayed provider work"
                crash = {"ownedWorkerKilled": True, "providerCallsReplayed": snapshot["aiCalls"]}
            # Snapshot is taken BEFORE T and restored AFTER T, never by changing immutable clocks.
            backup = None
            if args.crash_kill:
                if target.port != 26432:
                    raise ValueError("Snapshot rehearsal is pinned to the inspected local container port 26432")
                backup = await asyncio.to_thread(subprocess.run, ["docker", "exec", "moodprint-guest-impl-db", "pg_dump", "-U", "postgres", "-d", target.database, "-Fc"], capture_output=True, check=True)
                (logs / "synthetic-snapshot.dump").write_bytes(backup.stdout)
            from datetime import UTC, datetime
            await asyncio.sleep(max(0, (deadline - datetime.now(UTC)).total_seconds()) + 0.1)
            for n in range(50):
                assert (await client.get("/api/v1/session", headers=headers(n))).status_code == 401
            expiry_seen = time.monotonic()
            until = time.monotonic() + 60
            while (await sample())["guests"] and time.monotonic() < until:  # noqa: ASYNC110 -- polling another owned process
                await asyncio.sleep(0.5)
            final = await sample()
            assert final["guests"] == 0
            assert final["runningAi"] == 0 and final["liabilityNanoUsd"] > 0
            assert (await client.get("/api/v1/session", headers=headers(0, True))).status_code == 200
            restore = None
            if backup:
                restore = await restore_snapshot(target, backup.stdout, headers(0), headers(0, True))
            result = {"status": "PASS", "visitors": 50, "workers": 1, "latencies": {k: summarize(v) for k, v in timings.items()},
                      "statuses": dict(statuses), "peaks": peaks, "cleanupObservedSeconds": round(time.monotonic() - expiry_seen, 3),
                      "crash": crash, "restore": restore, "scope": "Synthetic local providers; seeded guests bypass signup source-IP bucket only. Defaults: AI 10, voice 3, lifetime 7200s. No hosted/paid capacity claim."}
            await asyncio.to_thread(Path(args.output).write_text, json.dumps(result, indent=2), encoding="utf-8")
            print(json.dumps({"status": "PASS", "output": str(args.output), "visitors": 50}))
        finally:
            await stop()
            handle.close()


async def restore_snapshot(target, dump, guest_headers, canary_headers):
    import psycopg

    from app.core.config import Settings
    from app.main import create_app
    from tests.guest_restore_helpers import enforce_quarantine
    name = f"moodprint_guest_restore_{uuid4().hex[:8]}_test"
    admin = target.set(drivername="postgresql", database="postgres").render_as_string(hide_password=False)
    with psycopg.connect(admin, autocommit=True) as db:
        db.execute(f'create database "{name}"')
    await asyncio.to_thread(subprocess.run, ["docker", "exec", "-i", "moodprint-guest-impl-db", "pg_restore", "-U", "postgres", "--no-owner", "-d", name], input=dump, capture_output=True, check=True)
    app = create_app(Settings(_env_file=None, app_env="test", database_url=target.set(database=name).render_as_string(hide_password=False)))
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://quarantined") as client:
            assert (await client.get("/api/v1/session", headers=guest_headers)).status_code == 401
            result = await enforce_quarantine(app)
            assert (await client.get("/api/v1/session", headers=canary_headers)).status_code == 200
        return {**result, "physicalDumpRestored": True, "networkListenerExposed": False, "quarantineLiftedAfterPurge": True}
    finally:
        await app.state.ai.close()
        await app.state.database.engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--users", type=int, default=50)
    parser.add_argument("--port", type=int, default=8018)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--crash-kill", action="store_true")
    asyncio.run(run(parser.parse_args()), loop_factory=asyncio.SelectorEventLoop)
