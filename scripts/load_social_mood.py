"""Synthetic concurrent load for mood, matching, connections and human chat.

Starts tests/social_load_server.py as one uvicorn process (production topology)
against a disposable local *_test database, then drives N synthetic users in
pairs through a realistic mix: mood writes/reads/summary, consent and profile
publication, discovery, mutual requests (half of the pairs race reciprocal
sends), message exchange with idempotent retries, polling and the event stream,
cross-pair access probes and consent toggles. No provider or AI calls.

Reports p50/p95 latency per operation, unexpected HTTP statuses, duplicate or
missing messages, isolation failures and the peak of checked-out DB connections.
"""

import argparse
import asyncio
import hashlib
import json
import os
import random
import statistics
import subprocess
import sys
import time
from collections import defaultdict
from datetime import datetime, timedelta
from itertools import combinations
from pathlib import Path
from uuid import NAMESPACE_URL, uuid4, uuid5
from zoneinfo import ZoneInfo

import httpx

ROOT = Path(__file__).resolve().parents[1]
INTERESTS = ["reading", "music", "walking", "cooking", "english", "photography", "puzzles"]
TRIPLES = list(combinations(INTERESTS, 3))
MESSAGES_PER_USER = 10


def identity(number: int):
    return uuid5(NAMESPACE_URL, f"moodprint-social-load:user:{number}")


def pair_alias(a: int, b: int) -> str:
    seed = hashlib.sha256(":".join(sorted((str(identity(a)), str(identity(b))))).encode())
    return f"Bạn đồng hành {seed.hexdigest()[:6]}"


def summarize(values):
    if not values:
        return {"count": 0}
    ordered = sorted(values)
    return {
        "count": len(ordered),
        "p50_ms": round(statistics.median(ordered) * 1000, 1),
        "p95_ms": round(ordered[min(len(ordered) - 1, int(len(ordered) * 0.95))] * 1000, 1),
        "max_ms": round(ordered[-1] * 1000, 1),
    }


class Metrics:
    def __init__(self):
        self.latency = defaultdict(list)
        self.unexpected: list[dict] = []
        self.counters = defaultdict(int)
        self.misses: list[dict] = []
        self.info = defaultdict(int)
        self.transport_retries: list[dict] = []


THINK_SECONDS = 0.0


async def request(client, metrics, op, method, path, expect=(200, 201), **kwargs):
    if THINK_SECONDS:
        # Randomised user think time; 0 (default) is a worst-case simultaneous burst.
        await asyncio.sleep(random.uniform(0, 2 * THINK_SECONDS))
    headers = kwargs.pop("headers", {})
    if method != "GET":
        headers.setdefault("Idempotency-Key", str(uuid4()))
    started = time.perf_counter()
    try:
        response = await client.request(method, path, headers=headers, **kwargs)
    except httpx.TransportError as exc:
        # A dropped keep-alive connection is retried once with the same idempotency key
        # (safe for writes); it is reported, never hidden, and a second failure raises.
        metrics.transport_retries.append({"op": op, "error": type(exc).__name__})
        response = await client.request(method, path, headers=headers, **kwargs)
    metrics.latency[op].append(time.perf_counter() - started)
    if response.status_code not in expect:
        metrics.unexpected.append(
            {"op": op, "status": response.status_code, "code": _code(response)}
        )
    return response


def _code(response):
    try:
        return response.json().get("error", {}).get("code")
    except ValueError:
        return None


async def user_flow(number, users, base, metrics, barriers, rooms):
    partner = number ^ 1
    pair = number // 2
    tag = f"PAIR{pair:02d}"
    client = httpx.AsyncClient(base_url=base, timeout=30)
    client.cookies.set("moodprint_session", f"load-session-{number}")
    client.headers["X-CSRF-Token"] = f"load-csrf-{number}"
    try:
        today = datetime.now(ZoneInfo("Asia/Bangkok")).date()
        await request(client, metrics, "session", "GET", "/api/v1/session")
        for offset in range(5):
            day = today - timedelta(days=offset)
            await request(
                client,
                metrics,
                "mood_put",
                "PUT",
                f"/api/v1/moods/{day}",
                json={
                    "value": 1 + (number + offset) % 5,
                    "note": f"{tag} n{number}",
                    "timezone": "Asia/Bangkok",
                    "expectedVersion": 0,
                },
            )
        headers = {"Idempotency-Key": str(uuid4())}
        edit = {
            "value": 3,
            "note": f"{tag} edited",
            "timezone": "Asia/Bangkok",
            "expectedVersion": 1,
        }
        for _ in range(2):  # a retried edit must not bump the version twice
            last = await request(
                client,
                metrics,
                "mood_edit",
                "PUT",
                f"/api/v1/moods/{today}",
                json=edit,
                headers=dict(headers),
            )
        if last.status_code == 200 and last.json()["version"] != 2:
            metrics.counters["mood_duplicate_versions"] += 1
        moods = await request(client, metrics, "mood_list", "GET", "/api/v1/moods")
        if len(moods.json()) != 5 or any(tag not in m["note"] for m in moods.json()):
            metrics.counters["mood_isolation_failures"] += 1
        summary = await request(
            client, metrics, "mood_summary", "GET", "/api/v1/moods/summary", params={"days": 30}
        )
        if summary.json().get("count") != 5:
            metrics.counters["mood_summary_mismatch"] += 1

        await request(
            client,
            metrics,
            "consent",
            "PUT",
            "/api/v1/consents/MATCH",
            json={"enabled": True, "expectedVersion": 1, "policyVersion": "v1"},
        )
        profile = {
            "interests": list(TRIPLES[pair % len(TRIPLES)]),
            "values": ["respect", "sincerity"],
            "style": "balanced",
            "goal": "friendship",
            "languages": ["vi"],
        }
        await request(
            client,
            metrics,
            "draft_save",
            "PUT",
            "/api/v1/profiles/matching-draft",
            json={**profile, "expectedVersion": 0},
        )
        preview = (
            await request(
                client, metrics, "draft_preview", "POST", "/api/v1/profiles/matching-draft/preview"
            )
        ).json()
        await request(
            client,
            metrics,
            "publish",
            "POST",
            "/api/v1/profiles/published",
            json={
                "draftVersion": preview["draftVersion"],
                "previewDigest": preview["previewDigest"],
                "expectedPublishedVersion": 0,
            },
        )
        await barriers["published"].wait()

        cards = (
            await request(client, metrics, "candidates", "GET", "/api/v1/matching/candidates")
        ).json()["candidates"]
        if partner >= users:
            # Odd user count: the unpaired user only browses; it must still pass every
            # barrier so the paired users are not blocked.
            for name in ("requested", "accepted", "chatted"):
                await barriers[name].wait()
            return
        card = next((c for c in cards if c["alias"] == pair_alias(number, partner)), None)
        if card is None:
            # A partner who already invited this user is shown as an incoming request,
            # not as a discovery card; only a partner found in neither place is a miss.
            incoming = (
                await request(client, metrics, "request_list", "GET", "/api/v1/connection-requests")
            ).json()
            if any(i["direction"] == "incoming" and i["status"] == "pending" for i in incoming):
                metrics.info["partner_seen_as_incoming_request"] += 1
            else:
                metrics.counters["partner_not_discovered"] += 1
                metrics.misses.append(
                    {"user": number, "partner": partner, "cards": [c["alias"] for c in cards]}
                )
        racing = pair % 2 == 0
        if card and (number % 2 == 0 or racing):
            await request(
                client,
                metrics,
                "request_send",
                "POST",
                "/api/v1/connection-requests",
                json={"candidateRef": card["candidateRef"]},
                expect=(201, 409),
            )
        await barriers["requested"].wait()
        # Whoever holds a pending incoming invitation accepts it.
        listed = (
            await request(client, metrics, "request_list", "GET", "/api/v1/connection-requests")
        ).json()
        for item in listed:
            if item["direction"] == "incoming" and item["status"] == "pending":
                await request(
                    client,
                    metrics,
                    "request_accept",
                    "POST",
                    f"/api/v1/connection-requests/{item['id']}/accept",
                    json={"expectedVersion": item["version"]},
                )
        await barriers["accepted"].wait()

        open_rooms = (
            await request(client, metrics, "connections", "GET", "/api/v1/connections")
        ).json()
        if len(open_rooms) != 1:
            metrics.counters["room_count_mismatch"] += 1
            await barriers["chatted"].wait()
            return
        room = open_rooms[0]["id"]
        rooms[number] = room
        events = asyncio.create_task(stream_watch(client, metrics, room))
        cursor = "0"
        for index in range(MESSAGES_PER_USER):
            body = {"text": f"{tag} from {number} #{index}", "clientMessageId": str(uuid4())}
            key = {"Idempotency-Key": str(uuid4())}
            sent = await request(
                client,
                metrics,
                "message_send",
                "POST",
                f"/api/v1/connections/{room}/messages",
                json=body,
                headers=dict(key),
            )
            if index % 3 == 0:  # double-submit with the same key and client id
                again = await request(
                    client,
                    metrics,
                    "message_retry",
                    "POST",
                    f"/api/v1/connections/{room}/messages",
                    json=body,
                    headers=dict(key),
                )
                if again.json().get("id") != sent.json().get("id"):
                    metrics.counters["message_duplicates"] += 1
            page = (
                await request(
                    client,
                    metrics,
                    "message_poll",
                    "GET",
                    f"/api/v1/connections/{room}/messages",
                    params={"afterSeq": cursor},
                )
            ).json()
            if page["messages"]:
                cursor = page["messages"][-1]["seq"]
            await asyncio.sleep(0.05)
        events.cancel()
        await asyncio.gather(events, return_exceptions=True)
        if number % 5 == 0:
            for expected, enabled in ((1, True), (2, False)):
                await request(
                    client,
                    metrics,
                    "consent_toggle",
                    "PUT",
                    "/api/v1/consents/AI",
                    json={"enabled": enabled, "expectedVersion": expected, "policyVersion": "v1"},
                )
        await barriers["chatted"].wait()

        history = (
            await request(client, metrics, "history", "GET", f"/api/v1/connections/{room}/messages")
        ).json()["messages"]
        seqs = [int(m["seq"]) for m in history]
        if seqs != list(range(1, 2 * MESSAGES_PER_USER + 1)):
            metrics.counters["sequence_gaps_or_duplicates"] += 1
        if any(not m["text"].startswith(tag) for m in history):
            metrics.counters["message_isolation_failures"] += 1
        foreign = rooms.get((number + 2) % users)
        if foreign and foreign != room:
            probe = await request(
                client,
                metrics,
                "foreign_probe",
                "GET",
                f"/api/v1/connections/{foreign}/messages",
                expect=(404,),
            )
            if probe.status_code != 404 or "PAIR" in probe.text:
                metrics.counters["foreign_room_leaks"] += 1
    finally:
        await client.aclose()


async def stream_watch(client, metrics, room):
    """Keeps the room's event stream open like an open chat tab until cancelled."""
    started = time.perf_counter()
    first = True
    try:
        async with client.stream(
            "GET", f"/api/v1/connections/{room}/events", params={"afterSeq": "0"}, timeout=None
        ) as response:
            if response.status_code != 200:
                metrics.unexpected.append({"op": "events", "status": response.status_code})
                return
            async for line in response.aiter_lines():
                if line.startswith("event: messages_available"):
                    metrics.info["events_received"] += 1
                    if first:
                        metrics.latency["events_first"].append(time.perf_counter() - started)
                        first = False
                elif line.startswith("event: access_revoked"):
                    metrics.counters["unexpected_stream_revocations"] += 1
                    return
    except asyncio.CancelledError:
        return
    except httpx.HTTPError as exc:
        metrics.unexpected.append({"op": "events", "status": type(exc).__name__})


async def sample_pool(base, stop, samples):
    async with httpx.AsyncClient(base_url=base, timeout=5) as client:
        while not stop.is_set():
            try:
                samples.append((await client.get("/__load/pool")).json())
            except httpx.HTTPError:
                pass
            await asyncio.sleep(0.05)


async def run(args, base):
    metrics = Metrics()
    barriers = {
        name: asyncio.Barrier(args.users)
        for name in ("published", "requested", "accepted", "chatted")
    }
    rooms: dict[int, str] = {}
    stop, samples = asyncio.Event(), []
    sampler = asyncio.create_task(sample_pool(base, stop, samples))
    started = time.perf_counter()
    results = await asyncio.gather(
        *[user_flow(n, args.users, base, metrics, barriers, rooms) for n in range(args.users)],
        return_exceptions=True,
    )
    elapsed = time.perf_counter() - started
    stop.set()
    await sampler
    failures = [repr(r) for r in results if isinstance(r, BaseException)]
    total = sum(len(v) for v in metrics.latency.values())
    report = {
        "users": args.users,
        "workers": 1,
        "think_seconds": THINK_SECONDS,
        "elapsed_s": round(elapsed, 2),
        "requests": total,
        "throughput_rps": round(total / elapsed, 1),
        "unexpected_statuses": metrics.unexpected,
        "flow_exceptions": failures,
        "integrity": dict(metrics.counters),
        "discovery_misses": metrics.misses,
        "info": dict(metrics.info),
        "transport_retries": metrics.transport_retries,
        "rooms_opened": len(set(rooms.values())),
        "expected_rooms": args.users // 2,
        "pool_peak_checked_out": max((s["checkedOut"] for s in samples), default=None),
        "pool_peak_overflow": max((s["overflow"] for s in samples), default=None),
        "pool_size": samples[0]["size"] if samples else None,
        "latency": {op: summarize(v) for op, v in sorted(metrics.latency.items())},
    }
    report["passed"] = (
        not metrics.unexpected
        and not failures
        and not any(metrics.counters.values())
        and report["rooms_opened"] == report["expected_rooms"]
    )
    return report


def start_server(args):
    env = {
        **os.environ,
        "MOODPRINT_LOAD_USERS": str(args.users),
        "MOODPRINT_LOAD_PORT": str(args.port),
    }
    server = subprocess.Popen(
        [sys.executable, "-m", "tests.social_load_server"],
        cwd=ROOT / "backend",
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    base = f"http://127.0.0.1:{args.port}"
    for _ in range(120):
        try:
            if httpx.get(f"{base}/api/v1/health/live", timeout=2).status_code == 200:
                return server, base
        except httpx.HTTPError:
            pass
        if server.poll() is not None:
            break
        time.sleep(0.5)
    server.kill()
    raise SystemExit("load server did not start")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--users", type=int, default=10, choices=range(2, 51), metavar="2..50")
    parser.add_argument("--port", type=int, default=8005)
    parser.add_argument("--output", default=str(ROOT / "docs/mvp-validation/load-social-10.json"))
    parser.add_argument("--think", type=float, default=0.0, help="mean seconds between actions")
    args = parser.parse_args()
    global THINK_SECONDS
    THINK_SECONDS = args.think
    url = os.environ.get("TEST_DATABASE_URL", "")
    if not url.rsplit("/", 1)[-1].endswith("_test"):
        raise SystemExit("TEST_DATABASE_URL must name a disposable local *_test database")
    server, base = start_server(args)
    try:
        report = asyncio.run(run(args, base), loop_factory=asyncio.SelectorEventLoop)
    finally:
        server.terminate()
        try:
            server.wait(timeout=20)
        except subprocess.TimeoutExpired:
            server.kill()
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    keys = ("users", "passed", "requests", "elapsed_s", "pool_peak_checked_out", "integrity")
    print(json.dumps({key: report[key] for key in keys}))
    raise SystemExit(0 if report["passed"] else 1)


if __name__ == "__main__":
    main()
