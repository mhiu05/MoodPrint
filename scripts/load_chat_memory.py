"""Reproduce synthetic 1-50 user chat/memory load on one or two owned local server workers.

Run from backend: uv run --locked python ../scripts/load_chat_memory.py --users 50
Requires TEST_DATABASE_URL pointing to an explicitly disposable local *_test database.
"""

import argparse
import asyncio
import json
import math
import os
import signal
import socket
import subprocess
import sys
import tempfile
import time
from collections import Counter, defaultdict
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

import httpx  # noqa: E402
from sqlalchemy import func, select, text  # noqa: E402


def summarize(values):
    ordered = sorted(values)
    return (
        {
            "count": len(ordered),
            "p50_ms": round(ordered[max(0, math.ceil(len(ordered) * 0.5) - 1)], 2),
            "p95_ms": round(ordered[max(0, math.ceil(len(ordered) * 0.95) - 1)], 2),
            "max_ms": round(ordered[-1], 2),
        }
        if ordered
        else {"count": 0}
    )


async def run(args):
    from app.ai.embedding_models import EmbeddingJob, MemoryEmbedding
    from app.ai.models import AiConversation, AiMessageRecord, AiTurn
    from app.infrastructure.database.models import AiRun, now
    from tests import chat_load_server as fixture

    # The fixture validates the resolved local PostgreSQL target before this reset.
    with socket.socket() as probe:
        try:
            probe.bind(("127.0.0.1", args.port))
        except OSError:
            raise RuntimeError(
                "Load port occupied; existing processes will not be touched"
            ) from None
    await fixture.seed(args.users)
    await fixture.app.state.database.engine.dispose()
    environment = {
        **os.environ,
        "MOODPRINT_LOAD_PORT": str(args.port),
        "MOODPRINT_LOAD_MODEL_DELAY": str(args.model_delay),
        "MOODPRINT_LOAD_WORKERS": str(args.workers),
    }
    logs = Path(tempfile.mkdtemp(prefix="moodprint-chat-load-"))
    handle = (logs / "server.log").open("w", encoding="utf-8")
    flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0

    async def start_server():
        return await asyncio.to_thread(
            subprocess.Popen,
            [sys.executable, "-m", "tests.chat_load_server"],
            cwd=ROOT / "backend",
            env=environment,
            stdout=handle,
            stderr=subprocess.STDOUT,
            creationflags=flags,
            start_new_session=sys.platform != "win32",
        )

    async def stop_server(owned):
        if owned.poll() is None:
            if sys.platform == "win32":
                await asyncio.to_thread(
                    subprocess.run,
                    ["taskkill.exe", "/PID", str(owned.pid), "/T", "/F"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=False,
                )
            else:
                os.killpg(owned.pid, signal.SIGTERM)
            try:
                await asyncio.to_thread(owned.wait, timeout=10)
            except subprocess.TimeoutExpired:
                owned.kill()
                await asyncio.to_thread(owned.wait, timeout=5)

    process = await start_server()
    server_start_attempts = 1
    base = f"http://127.0.0.1:{args.port}"
    timings, statuses, failures = defaultdict(list), Counter(), []
    completions, workers = [], {}
    peaks = {
        "admitted_runs": 0,
        "postgres_connections": 0,
        "embedding_backlog": 0,
        "pool_checked_out_sum": 0,
        "worker_rss_sum_bytes": 0,
    }
    stopping = asyncio.Event()
    sampler = None

    async def probe_workers(count=8):
        async def one():
            async with httpx.AsyncClient(
                base_url=base,
                timeout=3,
                trust_env=False,
                limits=httpx.Limits(max_keepalive_connections=0),
            ) as probe:
                try:
                    return (await probe.get("/__synthetic_load_stats")).json()
                except (httpx.HTTPError, ValueError):
                    return None

        snapshots = [
            value for value in await asyncio.gather(*(one() for _ in range(count))) if value
        ]
        for snapshot in snapshots:
            merge(snapshot)
        return snapshots

    def merge(snapshot):
        previous = workers.get(snapshot["pid"], {})
        workers[snapshot["pid"]] = {
            key: max(previous.get(key, 0), value)
            if isinstance(value, (int, float)) and not isinstance(value, bool)
            else value
            for key, value in snapshot.items()
        }

    def headers(number):
        return {
            "Cookie": f"moodprint_session=load-session-{number}",
            "X-CSRF-Token": f"load-csrf-{number}",
            "Idempotency-Key": str(uuid4()),
        }

    async with httpx.AsyncClient(
        base_url=base,
        timeout=45,
        trust_env=False,
        limits=httpx.Limits(max_connections=150, max_keepalive_connections=60),
    ) as client:

        async def request(number, method, route, label, expected=200, **kwargs):
            started = time.perf_counter()
            try:
                response = await client.request(method, route, headers=headers(number), **kwargs)
            except httpx.HTTPError as error:
                failures.append({"label": label, "error": type(error).__name__})
                raise
            elapsed = (time.perf_counter() - started) * 1000
            timings[label].append(elapsed)
            statuses[f"{label}:{response.status_code}"] += 1
            if response.status_code != expected:
                code = response.json().get("error", {}).get("code", "unexpected_status")
                failures.append({"label": label, "status": response.status_code, "code": code})
                raise AssertionError(f"{label} returned {response.status_code}/{code}")
            return response

        async def sample():
            async with httpx.AsyncClient(
                base_url=base, timeout=3, trust_env=False, headers={"Connection": "close"}
            ) as metrics:
                while not stopping.is_set():
                    try:
                        async with fixture.app.state.database.sessions() as db:
                            active = await db.scalar(
                                select(func.count())
                                .select_from(AiRun)
                                .where(AiRun.status == "running")
                            )
                            connections = await db.scalar(
                                text(
                                    "select count(*) from pg_stat_activity where datname=current_database()"
                                )
                            )
                            backlog = await db.scalar(
                                select(func.count())
                                .select_from(EmbeddingJob)
                                .where(EmbeddingJob.status.in_(("pending", "running", "retry")))
                            )
                        peaks["admitted_runs"] = max(peaks["admitted_runs"], active or 0)
                        peaks["postgres_connections"] = max(
                            peaks["postgres_connections"], connections or 0
                        )
                        peaks["embedding_backlog"] = max(peaks["embedding_backlog"], backlog or 0)
                        for _ in range(2):
                            merge((await metrics.get("/__synthetic_load_stats")).json())
                        peaks["pool_checked_out_sum"] = max(
                            peaks["pool_checked_out_sum"],
                            sum(value["pool_checked_out"] for value in workers.values()),
                        )
                        peaks["worker_rss_sum_bytes"] = max(
                            peaks["worker_rss_sum_bytes"],
                            sum(value["rss_bytes"] for value in workers.values()),
                        )
                    except (httpx.HTTPError, ValueError):
                        pass
                    await asyncio.sleep(0.1)

        try:
            for _ in range(200):
                if process.poll() is not None:
                    raise RuntimeError(f"Synthetic server stopped; inspect {logs}")
                try:
                    ready = await client.get("/api/v1/health/live")
                    if ready.status_code == 200:
                        break
                except httpx.HTTPError:
                    pass
                await asyncio.sleep(0.1)
            else:
                raise RuntimeError(f"Synthetic server unavailable; inspect {logs}")
            # A liveness response can precede the second worker's import/startup;
            # Windows worker import can take >10 s. Measure only after both answer.
            # On Windows a worker sometimes receives uvicorn's CTRL_BREAK during startup
            # and never finishes shutting down; restart the owned tree (reported).
            deadline = time.monotonic() + 45
            while len(workers) < args.workers:
                if process.poll() is not None:
                    raise RuntimeError(f"Synthetic server stopped; inspect {logs}")
                if time.monotonic() > deadline:
                    if server_start_attempts >= 3:
                        raise RuntimeError(
                            f"{args.workers} workers not ready after {server_start_attempts} starts "
                            f"(seen={len(workers)}); inspect {logs}"
                        )
                    await stop_server(process)
                    workers.clear()
                    process = await start_server()
                    server_start_attempts += 1
                    deadline = time.monotonic() + 45
                await probe_workers()
                await asyncio.sleep(0.1)

            async def final_snapshots():
                for _ in range(5):
                    await probe_workers()

            sampler = asyncio.create_task(sample())
            started = time.perf_counter()

            async def approve(number):
                route = f"/api/v1/proposals/{fixture.identity('pending', number)}/confirm"
                first = await request(
                    number, "POST", route, "memory_approve", json={"expectedVersion": 1}
                )
                retry = await request(
                    number, "POST", route, "memory_retry", json={"expectedVersion": 1}
                )
                assert retry.json() == first.json(), "decision replay changed receipt"

            await asyncio.gather(*(approve(number) for number in range(args.users)))
            await fixture.index_seeded_memories()
            # Server workers' own embedding loops may still hold leased jobs.
            for _ in range(300):
                async with fixture.app.state.database.sessions() as db:
                    indexed_before_chat = await db.scalar(
                        select(func.count()).select_from(MemoryEmbedding)
                    )
                if indexed_before_chat >= args.users * 3:
                    break
                await asyncio.sleep(0.1)
            assert indexed_before_chat == args.users * 3, "not all approved memories were indexed"

            async def prepare(number):
                await request(number, "GET", "/api/v1/ai/preferences", "preferences")
                await request(number, "GET", "/api/v1/memories", "memory_list")
                await request(number, "GET", "/api/v1/ai/conversations", "history_list")
                bot = "may" if number % 2 == 0 else "guong"
                response = await request(
                    number,
                    "POST",
                    "/api/v1/ai/conversations",
                    "create",
                    201,
                    json={"botId": bot, "persistent": True},
                )
                return number, bot, response.json()["conversationId"]

            conversations = await asyncio.gather(*(prepare(number) for number in range(args.users)))

            async def chat(number, bot, conversation_id):
                route = f"/api/v1/ai/conversations/{conversation_id}"
                await request(
                    (number + 1) % args.users, "GET", route, "foreign_history_denied", 404
                )
                payload = {
                    "text": f"LOAD_ACTOR:{number:03d} BOT:{bot} preference",
                    "clientMessageId": str(uuid4()),
                    "expectedConversationVersion": 1,
                }
                turn_started = time.perf_counter()
                sent = await request(
                    number, "POST", route + "/messages", "message_admission", 202, json=payload
                )
                retry = await request(
                    number, "POST", route + "/messages", "message_retry", 202, json=payload
                )
                assert sent.json()["runId"] == retry.json()["runId"], (
                    "client retry created another run"
                )
                stream = await request(number, "GET", sent.json()["eventsUrl"], "sse_completion")
                assert "event: completed" in stream.text, "SSE missing completed status"
                assert f"Synthetic completion actor {number:03d} bot {bot}" in stream.text
                assert "RAW-SYNTHETIC-CANARY" not in stream.text, "raw SDK delta escaped"
                completions.append((time.perf_counter() - turn_started) * 1000)
                resumed = await request(number, "GET", route, "history_resume")
                messages = resumed.json()["messages"]
                assert [message["actor"] for message in messages] == ["self", "bot"], (
                    "retry duplicated durable messages"
                )
                exported = await request(number, "GET", route + "/export", "history_export")
                assert len(exported.json()["messages"]) == 2

            await asyncio.gather(*(chat(*conversation) for conversation in conversations))

            async def held_on(number):
                for _ in range(200):
                    for snapshot in await probe_workers():
                        if f"{number:03d}" in snapshot["held"]:
                            return snapshot
                    await asyncio.sleep(0.05)
                raise AssertionError("held synthetic turn never reached the model")

            async def pinned_to_other(worker_id):
                # Concurrent keep-alive clients; keep one bound to the other worker.
                for _ in range(50):
                    candidates = [
                        httpx.AsyncClient(
                            base_url=base,
                            timeout=10,
                            trust_env=False,
                            limits=httpx.Limits(max_connections=1, max_keepalive_connections=1),
                        )
                        for _ in range(6)
                    ]
                    answers = await asyncio.gather(
                        *(c.get("/__synthetic_load_stats") for c in candidates),
                        return_exceptions=True,
                    )
                    chosen = None
                    for candidate, answer in zip(candidates, answers, strict=True):
                        if (
                            chosen is None
                            and isinstance(answer, httpx.Response)
                            and answer.json()["runtime_worker_id"] != worker_id
                        ):
                            chosen = candidate
                        else:
                            await candidate.aclose()
                    if chosen:
                        return chosen
                raise AssertionError("could not reach the second worker")

            async def manage(number, bot, first_id):
                # Pagination, rename, delete and ownership on a second saved thread.
                other = "guong" if bot == "may" else "may"
                created = await request(
                    number,
                    "POST",
                    "/api/v1/ai/conversations",
                    "create",
                    201,
                    json={"botId": other, "persistent": True},
                )
                second_id = created.json()["conversationId"]
                title = f"Synthetic thread {number:03d}"
                renamed = await request(
                    number,
                    "PATCH",
                    f"/api/v1/ai/conversations/{second_id}",
                    "rename",
                    json={"title": title},
                )
                assert renamed.json()["title"] == title
                page = await request(
                    number, "GET", "/api/v1/ai/conversations?limit=1", "history_page"
                )
                cursor = page.json()[0]["conversationId"]
                older = await request(
                    number,
                    "GET",
                    f"/api/v1/ai/conversations?limit=1&before={cursor}",
                    "history_page",
                )
                seen = [c["conversationId"] for c in page.json() + older.json()]
                assert sorted(seen) == sorted([first_id, second_id]), "pagination lost a thread"
                await request(
                    (number + 1) % args.users,
                    "DELETE",
                    f"/api/v1/ai/conversations/{second_id}",
                    "foreign_delete_denied",
                    410,
                )
                await request(
                    number,
                    "DELETE",
                    f"/api/v1/ai/conversations/{second_id}",
                    "history_delete",
                    204,
                )
                gone = await client.get(
                    f"/api/v1/ai/conversations/{second_id}", headers=headers(number)
                )
                assert gone.status_code in (404, 410), "deleted thread still readable"

            await asyncio.gather(*(manage(*conversation) for conversation in conversations))

            cancel_users = [n for n in range(args.users) if n % 5 == 0]
            revoke_users = [n for n in range(args.users) if n % 5 == 1]
            cross_worker_cancels = 0

            async def cancel_turn(number):
                nonlocal cross_worker_cancels
                created = await request(
                    number,
                    "POST",
                    "/api/v1/ai/conversations",
                    "create",
                    201,
                    json={"botId": "may", "persistent": True},
                )
                route = f"/api/v1/ai/conversations/{created.json()['conversationId']}"
                sent = await request(
                    number,
                    "POST",
                    route + "/messages",
                    "message_admission",
                    202,
                    json={
                        "text": f"LOAD_ACTOR:{number:03d} BOT:may HOLD",
                        "clientMessageId": str(uuid4()),
                        "expectedConversationVersion": 1,
                    },
                )
                running_on = (await held_on(number))["runtime_worker_id"]
                # Pin one keep-alive connection to the worker that is NOT running the
                # model, so cancellation must travel through PostgreSQL. With a single
                # process, a separate connection still exercises the durable cancel path.
                pinned = (
                    await pinned_to_other(running_on)
                    if args.workers > 1
                    else httpx.AsyncClient(base_url=base, timeout=10, trust_env=False)
                )
                started_cancel = time.perf_counter()
                try:
                    response = await pinned.post(
                        f"/api/v1/ai/runs/{sent.json()['runId']}/cancel",
                        json={"expectedVersion": 1},
                        headers=headers(number),
                    )
                finally:
                    await pinned.aclose()
                timings["cancel"].append((time.perf_counter() - started_cancel) * 1000)
                statuses[f"cancel:{response.status_code}"] += 1
                assert response.status_code == 200, response.text
                if response.headers.get("X-Synthetic-Worker") != running_on:
                    cross_worker_cancels += 1
                stream = await request(number, "GET", sent.json()["eventsUrl"], "sse_cancelled")
                assert "event: cancelled" in stream.text, "cancel did not reach SSE"
                assert "Synthetic completion" not in stream.text, "cancelled turn published"

            async def revoke_turn(number):
                await request(
                    number,
                    "PUT",
                    "/api/v1/consents/MEM",
                    "consent_revoke",
                    json={"enabled": False, "expectedVersion": 1, "policyVersion": "v1"},
                )
                created = await request(
                    number,
                    "POST",
                    "/api/v1/ai/conversations",
                    "create",
                    201,
                    json={"botId": "may", "persistent": True},
                )
                route = f"/api/v1/ai/conversations/{created.json()['conversationId']}"
                sent = await request(
                    number,
                    "POST",
                    route + "/messages",
                    "message_admission",
                    202,
                    json={
                        "text": f"LOAD_ACTOR:{number:03d} BOT:may NOMEM",
                        "clientMessageId": str(uuid4()),
                        "expectedConversationVersion": 1,
                    },
                )
                stream = await request(number, "GET", sent.json()["eventsUrl"], "sse_completion")
                assert "event: completed" in stream.text, "MEM-withdrawn turn did not complete"
                await request(
                    number,
                    "PUT",
                    "/api/v1/consents/AI",
                    "consent_revoke",
                    json={"enabled": False, "expectedVersion": 1, "policyVersion": "v1"},
                )
                blocked = await client.post(
                    route + "/messages",
                    headers=headers(number),
                    json={
                        "text": f"LOAD_ACTOR:{number:03d} BOT:may after revoke",
                        "clientMessageId": str(uuid4()),
                        "expectedConversationVersion": 3,
                    },
                )
                statuses[f"post_revoke_send:{blocked.status_code}"] += 1
                assert blocked.status_code == 403, "AI revocation did not block new turns"
                # Saved history stays manageable with AI off.
                await request(number, "GET", route, "history_resume")
                await request(number, "GET", route + "/export", "history_export")

            await asyncio.gather(
                *(cancel_turn(n) for n in cancel_users), *(revoke_turn(n) for n in revoke_users)
            )

            # Crash recovery is a lease-expired synthetic turn, never replayed to a model.
            recovery_id = uuid4()
            number, _, cid = conversations[0]
            from uuid import UUID

            async with fixture.app.state.database.sessions.begin() as db:
                db.add(
                    AiRun(
                        id=recovery_id,
                        user_id=fixture.identity("user", number),
                        conversation_id=UUID(cid),
                        bot_id="may",
                    )
                )
                await db.flush()
                db.add(
                    AiTurn(
                        run_id=recovery_id,
                        user_id=fixture.identity("user", number),
                        scope_id=UUID(cid),
                        conversation_id=UUID(cid),
                        session_id=fixture.identity("session", number),
                        client_message_id=uuid4(),
                        input_digest="0" * 64,
                        data_version=2,
                        worker_id=uuid4(),
                        lease_until=now() - fixture.timedelta(seconds=1),
                    )
                )
            recovery_started = time.perf_counter()
            await request(number, "GET", f"/api/v1/ai/conversations/{cid}", "recovery_read")
            async with fixture.app.state.database.sessions() as db:
                recovered = await db.get(AiRun, recovery_id)
                recovered_status = recovered.status
                counts = dict(
                    (
                        await db.execute(select(AiRun.status, func.count()).group_by(AiRun.status))
                    ).all()
                )
                message_count = await db.scalar(select(func.count()).select_from(AiMessageRecord))
                conversation_count = await db.scalar(
                    select(func.count()).select_from(AiConversation)
                )
                backlog_end = await db.scalar(
                    select(func.count())
                    .select_from(EmbeddingJob)
                    .where(EmbeddingJob.status.in_(("pending", "running", "retry")))
                )
            recovery_ms = (time.perf_counter() - recovery_started) * 1000
            assert recovered_status == "interrupted", "expired lease was not fenced"
            expected_completed = args.users + len(revoke_users)
            assert counts.get("completed") == expected_completed, counts
            assert counts.get("cancelled") == len(cancel_users), counts
            # Two messages per completed turn; a cancelled turn keeps only its input.
            assert message_count == expected_completed * 2 + len(cancel_users), message_count
            assert conversation_count == args.users + len(cancel_users) + len(revoke_users)
            await final_snapshots()
            assert len(workers) == args.workers, "did not observe every serving process"
            assert sum(w["sdk_calls"] for w in workers.values()) == (
                args.users + len(cancel_users) + len(revoke_users)
            ), "a provider call was replayed or skipped"
            # MEM-withdrawn turns make no external query; held turns query before the model.
            assert sum(w["query_calls"] for w in workers.values()) == args.users + len(cancel_users)
            assert sum(w["cancelled_calls"] for w in workers.values()) == len(cancel_users)
            assert not sum(w["isolation_failures"] + w["missing_memory"] for w in workers.values())
            if args.workers > 1:
                assert cross_worker_cancels == len(cancel_users), "a cancel stayed on its own worker"
            wall_seconds = round(time.perf_counter() - started, 2)
            crash = None
            if args.crash_kill:
                # Real process loss: kill the worker holding a turn and require lease
                # recovery to mark it interrupted without replaying the provider call.
                number = cancel_users[0]
                created = await request(
                    number,
                    "POST",
                    "/api/v1/ai/conversations",
                    "create",
                    201,
                    json={"botId": "may", "persistent": True},
                )
                cid = created.json()["conversationId"]
                sent = await request(
                    number,
                    "POST",
                    f"/api/v1/ai/conversations/{cid}/messages",
                    "message_admission",
                    202,
                    json={
                        "text": f"LOAD_ACTOR:{number:03d} BOT:may HOLD",
                        "clientMessageId": str(uuid4()),
                        "expectedConversationVersion": 1,
                    },
                )
                holder = await held_on(number)
                calls_before = {pid: w["sdk_calls"] for pid, w in workers.items()}
                if sys.platform == "win32":
                    await asyncio.to_thread(
                        subprocess.run,
                        ["taskkill.exe", "/PID", str(holder["pid"]), "/F"],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        check=True,
                    )
                else:
                    os.kill(holder["pid"], signal.SIGKILL)
                killed = time.perf_counter()
                if args.workers == 1:
                    # The only process died: restart it as a process supervisor would.
                    await stop_server(process)
                    process = await start_server()
                    server_start_attempts += 1
                status = None
                while time.perf_counter() - killed < args.crash_timeout:
                    try:
                        # Pooled connections to the killed process fail; retry on another.
                        response = await client.get(
                            f"/api/v1/ai/conversations/{cid}", headers=headers(number)
                        )
                    except httpx.HTTPError:
                        await asyncio.sleep(0.2)
                        continue
                    if response.status_code == 200:
                        messages = response.json()["messages"]
                        status = messages[-1]["status"] if messages else None
                        if status != "running":
                            break
                    await asyncio.sleep(1)
                recovered_after = time.perf_counter() - killed
                for _ in range(5):
                    try:
                        stream = await client.get(sent.json()["eventsUrl"], headers=headers(number))
                        break
                    except httpx.HTTPError:
                        await asyncio.sleep(0.2)
                await final_snapshots()
                survivors = {pid: w for pid, w in workers.items() if pid != holder["pid"]}
                replayed = sum(
                    w["sdk_calls"] - calls_before.get(pid, 0) for pid, w in survivors.items()
                )
                assert status == "interrupted", f"killed turn ended as {status}"
                assert "AI_INTERRUPTED" in stream.text, "SSE did not report interruption"
                assert replayed == 0, "a surviving worker replayed the killed provider call"
                crash = {
                    "killed_pid": holder["pid"],
                    "final_status": status,
                    "recovered_after_seconds": round(recovered_after, 1),
                    "lease_seconds": float(os.environ.get("MOODPRINT_LOAD_AI_TIMEOUT", "30")) + 15,
                    "provider_replayed_calls": replayed,
                    "sse_reported_interruption": True,
                }
            non_ai = [
                value
                for name, values in timings.items()
                if not name.startswith("sse_")
                for value in values
            ]
            report = {
                "status": "PASS",
                "synthetic_only": True,
                "users": args.users,
                "workers": args.workers,
                "server_start_attempts": server_start_attempts,
                "model_delay_ms": args.model_delay * 1000,
                "wall_seconds": wall_seconds,
                "non_ai_endpoint_latency": summarize(non_ai),
                "ai_completion_latency": summarize(completions),
                "endpoints": {name: summarize(values) for name, values in timings.items()},
                "http_statuses": dict(statuses),
                "unexpected_errors": failures,
                "sampled_peaks": peaks,
                "worker_observations": list(workers.values()),
                "indexed_before_chat": indexed_before_chat,
                "durable_messages": message_count,
                "run_status_counts": counts,
                "embedding_backlog_end": backlog_end,
                "cancellation": {
                    "cancelled_turns": len(cancel_users),
                    "cross_worker_cancels": cross_worker_cancels,
                    "provider_observed_cancel": sum(w["cancelled_calls"] for w in workers.values()),
                },
                "consent_revocation": {
                    "users": len(revoke_users),
                    "memory_free_turns": len(revoke_users),
                    "post_revoke_sends_blocked": statuses.get("post_revoke_send:403", 0),
                },
                "crash_recovery": crash or "not run (use --crash-kill)",
                "recovery": {
                    "status": recovered_status,
                    "latency_ms": round(recovery_ms, 2),
                    "provider_replayed": False,
                },
                "limits": {
                    "global_admission": 50,
                    "per_user": 2,
                    "timeout_seconds": 30,
                    "pool_per_worker": "5 + 5 overflow",
                    "sampling_seconds": 0.1,
                },
                "scope": "Local synthetic providers; no external latency, billing, production traffic, crash-kill, or sustained soak measurement.",
            }
            output = Path(args.output)
            output.parent.mkdir(parents=True, exist_ok=True)
            await asyncio.to_thread(
                output.write_text, json.dumps(report, indent=2) + "\n", encoding="utf-8"
            )
            print(
                json.dumps(
                    {
                        key: report[key]
                        for key in (
                            "status",
                            "users",
                            "workers",
                            "non_ai_endpoint_latency",
                            "ai_completion_latency",
                            "sampled_peaks",
                            "durable_messages",
                        )
                    },
                    indent=2,
                )
            )
        finally:
            stopping.set()
            if sampler:
                await sampler
            await stop_server(process)
            handle.close()
            await fixture.app.state.database.engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--users", type=int, default=50, choices=range(2, 51), metavar="2..50")
    parser.add_argument("--port", type=int, default=8003)
    parser.add_argument("--workers", type=int, default=2, choices=(1, 2))
    parser.add_argument("--model-delay", type=float, default=0.2)
    parser.add_argument(
        "--crash-kill",
        action="store_true",
        help="Also kill the worker holding a turn and wait for lease recovery",
    )
    parser.add_argument("--crash-timeout", type=float, default=90)
    parser.add_argument("--output", default=str(ROOT / "docs/ai-chat-memory/load-results-50.json"))
    options = parser.parse_args()
    asyncio.run(run(options), loop_factory=asyncio.SelectorEventLoop)
