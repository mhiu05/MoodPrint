"""Opt-in local PostgreSQL matching benchmark. Uses only synthetic accounts."""

import asyncio
import hashlib
import json
import os
import platform
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import httpx
from sqlalchemy import insert, text
from sqlalchemy.engine import make_url

os.environ.update(
    {
        "DATABASE_URL": "",
        "DATABASE_MIGRATION_URL": "",
        "SUPABASE_URL": "",
        "OPENAI_API_KEY": "",
        "OPENAI_MODEL": "",
        "AI_ENABLED": "false",
        "STT_ENABLED": "false",
    }
)
from app.core.config import Settings
from app.infrastructure.database.models import AuthSession, Base, Consent, User
from app.main import create_app
from app.modules.social.models import PublishedProfile
from tests.test_social import PROFILE


async def main():
    url = os.environ.get("TEST_DATABASE_URL", "")
    target = make_url(url) if url else None
    if (
        not target
        or target.host not in ("127.0.0.1", "localhost")
        or not target.database.endswith("_test")
    ):
        raise RuntimeError(
            "Benchmark requires an explicitly configured disposable local *_test database"
        )
    app = create_app(Settings(_env_file=None, app_env="test", database_url=url))
    results = []
    for count in (100, 1000, 10000):
        async with app.state.database.engine.begin() as db:
            await db.execute(text("create schema if not exists moodprint"))
            await db.run_sync(Base.metadata.drop_all)
            await db.run_sync(Base.metadata.create_all)
            await db.execute(text("create schema if not exists auth"))
            await db.execute(
                text(
                    "create table if not exists auth.sessions (id uuid primary key,user_id uuid not null)"
                )
            )
            await db.execute(text("truncate auth.sessions"))
        ids = [uuid4() for _ in range(count + 1)]
        owner = ids[0]
        sid = uuid4()
        async with app.state.database.sessions.begin() as db:
            await db.execute(
                insert(User),
                [
                    {"id": uid, "auth_subject": uid, "age_band": "adult", "profile_version": 1}
                    for uid in ids
                ],
            )
            await db.execute(
                insert(Consent),
                [
                    {"user_id": uid, "purpose": "MATCH", "enabled": True, "version": 1}
                    for uid in ids
                ],
            )
            await db.execute(
                insert(PublishedProfile),
                [
                    {"user_id": uid, "payload": PROFILE, "version": 1, "consent_version": 1}
                    for uid in ids
                ],
            )
            await db.execute(
                insert(AuthSession),
                [
                    {
                        "user_id": owner,
                        "token_hash": hashlib.sha256(b"synthetic-benchmark").hexdigest(),
                        "csrf_hash": hashlib.sha256(b"csrf").hexdigest(),
                        "provider_session_id": sid,
                        "expires_at": datetime.now(UTC) + timedelta(hours=1),
                    }
                ],
            )
            await db.execute(
                text("insert into auth.sessions(id,user_id) values (:id,:uid)"),
                {"id": sid, "uid": owner},
            )
        durations = []
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
            cookies={"moodprint_session": "synthetic-benchmark"},
        ) as client:
            for _ in range(5):
                started = time.perf_counter()
                response = await client.get("/api/v1/matching/candidates")
                elapsed = time.perf_counter() - started
                if response.status_code != 200 or len(response.json()["candidates"]) != 5:
                    raise RuntimeError("Matching benchmark failed its functional checks")
                durations.append(round(elapsed * 1000, 2))
        ordered = sorted(durations)
        results.append(
            {
                "profiles": count,
                "samplesMs": durations,
                "medianMs": ordered[2],
                "maxMs": ordered[-1],
                "aiProviderCalls": 0,
            }
        )
    await app.state.database.engine.dispose()
    artifact = {
        "scope": "Local PostgreSQL/ASGI matching only; no production SLA or live model claim",
        "python": platform.python_version(),
        "measuredAt": datetime.now(UTC).isoformat(),
        "results": results,
    }
    await asyncio.to_thread(write_artifact, artifact)
    print(json.dumps(results))


def write_artifact(artifact):
    path = (
        Path(__file__).resolve().parents[3]
        / "docs/plans/validation-artifacts/matching-performance.json"
    )
    path.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    asyncio.run(main(), loop_factory=asyncio.SelectorEventLoop)
