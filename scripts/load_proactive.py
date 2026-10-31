"""Check-in load test (P1-18): N due schedules drained by a separate worker process while M users chat.

Synthetic accounts and a fake model with fixed latency only; requires a disposable local *_test
database in TEST_DATABASE_URL. Measures chat latency with and without the worker, check-in lag,
worker pool peak, PostgreSQL connections/idle-in-transaction and worker RSS. Prints JSON.

    TEST_DATABASE_URL=postgresql+psycopg://…/moodprint_p1_load_test \
      backend/.venv/Scripts/python scripts/load_proactive.py --users 100 --chat 20 --concurrency 2
"""

import argparse
import asyncio
import hashlib
import json
import os
import subprocess
import sys
import time
from datetime import UTC, datetime, timedelta
from datetime import time as wall
from pathlib import Path
from uuid import UUID, uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
URL = os.environ.get("TEST_DATABASE_URL", "")
from sqlalchemy.engine import make_url

target = make_url(URL) if URL else None
if not target or target.host not in ("127.0.0.1", "localhost") or not target.database.endswith("_test"):
    raise SystemExit("Set TEST_DATABASE_URL to a disposable local *_test database")
os.environ.update({"APP_ENV": "test", "DATABASE_URL": "", "OPENAI_API_KEY": "", "AI_ENABLED": "false",
                   "VOYAGE_API_KEY": "", "SEMANTIC_MEMORY_ENABLED": "false"})

import httpx
from sqlalchemy import func, select, text, update

BOTS = ("may", "guong", "rure", "nhip")


def pct(values, q):
    if not values:
        return None
    ordered = sorted(values)
    return round(ordered[min(len(ordered) - 1, round(q * (len(ordered) - 1)))], 3)


def summary(values):
    return {"n": len(values), "p50": pct(values, 0.5), "p95": pct(values, 0.95), "p99": pct(values, 0.99),
            "max": round(max(values), 3) if values else None}


async def reset_and_seed(app, users: int, chatters: int):
    from app.ai import embedding_models, memory_models  # noqa: F401
    from app.ai import models as chat_models  # noqa: F401
    from app.ai.proactive.models import AiProactiveSchedule, AiProactiveSettings
    from app.infrastructure.database.models import AuthSession, Base, Consent, User
    from app.modules.activities import models as activity_models  # noqa: F401
    from app.modules.feedback import models as feedback_models  # noqa: F401
    from app.modules.guests import models as guest_models  # noqa: F401
    from app.modules.journal import models as journal_models  # noqa: F401
    from app.modules.moderation import models as safety_models  # noqa: F401
    from app.modules.social import models as social_models  # noqa: F401
    from app.modules.users import models as lifecycle_models  # noqa: F401
    from tests.conftest import IDENTITY_HELPER
    from tests.feedback_schema import install_feedback_functions
    from tests.guest_schema import install_auth_fixture, install_guest_guards

    async with app.state.database.engine.begin() as conn:
        await conn.execute(text("create schema if not exists moodprint"))
        await conn.execute(text("create schema if not exists extensions"))
        await conn.execute(text("create extension if not exists vector with schema extensions"))
        await conn.run_sync(Base.metadata.drop_all)
        await install_feedback_functions(conn)
        await conn.run_sync(Base.metadata.create_all)
        await install_guest_guards(conn)
        await install_auth_fixture(conn)
        await conn.execute(text(IDENTITY_HELPER))
    tokens = []
    async with app.state.database.sessions.begin() as db:
        for number in range(users + chatters):
            uid, provider = uuid4(), uuid4()
            db.add(User(id=uid, auth_subject=uid, alias=f"Load {number}", age_band="adult"))
            await db.flush()
            for purpose in ("AI", "MEM", "MATCH", "VOICE"):
                db.add(Consent(user_id=uid, purpose=purpose, enabled=False, version=1))
            token, csrf = f"load-{uuid4()}", f"csrf-{uuid4()}"
            db.add(AuthSession(user_id=uid, token_hash=hashlib.sha256(token.encode()).hexdigest(),
                               csrf_hash=hashlib.sha256(csrf.encode()).hexdigest(), provider_session_id=provider,
                               expires_at=datetime.now(UTC) + timedelta(hours=2)))
            await db.execute(text("insert into auth.sessions(id,user_id) values (:id,:uid)"), {"id": provider, "uid": uid})
            if number < users:
                db.add(AiProactiveSettings(user_id=uid, timezone="Asia/Ho_Chi_Minh"))
                db.add(AiProactiveSchedule(user_id=uid, bot_id=BOTS[number % len(BOTS)], slot="morning",
                                           enabled=True, local_time=wall(7, 30), next_due_at=None))
            else:
                tokens.append((token, csrf))
    return tokens


class SlowChatModel:
    """Factory for a fake chat model with fixed provider latency."""

    @staticmethod
    def build(delay: float):
        from tests.fakes import ScriptedModel, message_output

        class Model(ScriptedModel):
            async def stream_response(self, *args, **kwargs):
                self.responses = [[message_output(json.dumps({"text": "Mây nghe bạn.", "cards": []}, ensure_ascii=False))]]
                await asyncio.sleep(delay)
                async for event in super().stream_response(*args, **kwargs):
                    yield event

        return Model([])


async def chat_load(app, tokens, turns: int):
    latencies, errors = [], 0

    async def one(token, csrf):
        nonlocal errors
        client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://load")
        client.cookies.set("moodprint_session", token)
        client.headers["X-CSRF-Token"] = csrf
        try:
            created = await client.post("/api/v1/ai/conversations", json={"botId": "may", "persistent": True},
                                        headers={"Idempotency-Key": str(uuid4())})
            if created.status_code != 201:
                errors += 1
                return
            cid, version = created.json()["conversationId"], created.json()["version"]
            for _ in range(turns):
                started = time.perf_counter()
                sent = await client.post(f"/api/v1/ai/conversations/{cid}/messages", json={
                    "text": "Một câu tổng hợp", "clientMessageId": str(uuid4()), "expectedConversationVersion": version},
                    headers={"Idempotency-Key": str(uuid4())})
                if sent.status_code != 202:
                    errors += 1
                    continue
                run = app.state.ai.runs.get(UUID(sent.json()["runId"]))
                if run and run.task:
                    await run.task
                latencies.append(time.perf_counter() - started)
                version = (await client.get(f"/api/v1/ai/conversations/{cid}")).json()["version"]
        finally:
            await client.aclose()

    await asyncio.gather(*(one(token, csrf) for token, csrf in tokens))
    return latencies, errors


async def sample_database(engine, stop: asyncio.Event, out: dict, worker: subprocess.Popen | None):
    async with engine.connect() as conn:
        while not stop.is_set():
            rows = (await conn.execute(text(
                "select state, count(*), max(extract(epoch from now() - xact_start)) from pg_stat_activity "
                "where datname = current_database() and pid <> pg_backend_pid() group by state"))).all()
            total = sum(r[1] for r in rows)
            idle_tx = sum(r[1] for r in rows if r[0] == "idle in transaction")
            out["connections_peak"] = max(out.get("connections_peak", 0), total)
            out["idle_in_transaction_peak"] = max(out.get("idle_in_transaction_peak", 0), idle_tx)
            longest = max((r[2] or 0) for r in rows) if rows else 0
            out["longest_transaction_s"] = round(max(out.get("longest_transaction_s", 0), float(longest)), 3)
            await conn.commit()
            await asyncio.sleep(0.25)


async def run(args) -> dict:
    from app.ai.proactive.models import AiProactiveJob, AiProactiveSchedule
    from app.core.config import Settings
    from app.main import create_app

    app = create_app(Settings(_env_file=None, app_env="test", database_url=URL, database_pool_size=5,
                              database_pool_overflow=2, ai_global_concurrency=50, ai_user_concurrency=2,
                              ai_requests_per_minute=120, ai_daily_turns_per_user=1000))
    app.state.ai.model_override = SlowChatModel.build(args.model_delay)
    tokens = await reset_and_seed(app, args.users, args.chat)
    result: dict = {"users": args.users, "chatters": args.chat, "turns": args.turns,
                    "concurrency": args.concurrency, "model_delay_s": args.model_delay}

    # Two runs without the worker: the second is the control for data growth and warm-up drift.
    await chat_load(app, tokens, 1)
    baseline, base_errors = await chat_load(app, tokens, args.turns)
    result["chat_baseline_s"] = summary(baseline) | {"errors": base_errors}

    async with app.state.database.sessions.begin() as db:
        await db.execute(update(AiProactiveSchedule).values(next_due_at=func.now() - timedelta(seconds=1)))
    environment = {**os.environ, "TEST_DATABASE_URL": URL, "DATABASE_POOL_SIZE": str(args.worker_pool),
                   "DATABASE_POOL_OVERFLOW": "0", "PYTHONPATH": str(ROOT / "backend")}
    worker = subprocess.Popen([sys.executable, "-m", "tests.proactive_load_worker", str(args.concurrency),
                               str(args.model_delay)], cwd=ROOT / "backend", env=environment,
                              stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)  # noqa: ASYNC220
    stop, sampled = asyncio.Event(), {}
    sampler = asyncio.create_task(sample_database(app.state.database.engine, stop, sampled, worker))
    loaded, load_errors = await chat_load(app, tokens, args.turns)
    output, _ = await asyncio.to_thread(worker.communicate)
    stop.set()
    await sampler
    result["chat_with_worker_s"] = summary(loaded) | {"errors": load_errors}
    base_p95 = result["chat_baseline_s"]["p95"] or 0
    result["chat_p95_increase_pct"] = round(100 * ((result["chat_with_worker_s"]["p95"] or 0) - base_p95) / base_p95, 1) if base_p95 else None
    result["worker"] = json.loads(output.strip().splitlines()[-1]) if output.strip() else {"error": "no output"}
    result["database"] = sampled
    async with app.state.database.sessions() as db:
        jobs = (await db.execute(select(AiProactiveJob.status, AiProactiveJob.skip_reason, AiProactiveJob.due_at,
                                        AiProactiveJob.finished_at))).all()
    lags = [(f - d).total_seconds() for s, _r, d, f in jobs if s == "delivered" and f]
    statuses: dict[str, int] = {}
    for status, reason, _d, _f in jobs:
        key = status + (f"({reason})" if reason else "")
        statuses[key] = statuses.get(key, 0) + 1
    result["check_in_lag_s"] = summary(lags)
    result["jobs"] = statuses
    result["throughput_per_min"] = round(60 * len(lags) / result["worker"].get("seconds", 1), 1) if lags else 0
    await app.state.ai.close()
    await app.state.database.engine.dispose()
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--users", type=int, default=20)
    parser.add_argument("--chat", type=int, default=20)
    parser.add_argument("--turns", type=int, default=3)
    parser.add_argument("--concurrency", type=int, default=1)
    parser.add_argument("--worker-pool", type=int, default=2)
    parser.add_argument("--model-delay", type=float, default=1.5)
    args = parser.parse_args()
    print(json.dumps(asyncio.run(run(args), loop_factory=asyncio.SelectorEventLoop), ensure_ascii=False))


if __name__ == "__main__":
    main()
