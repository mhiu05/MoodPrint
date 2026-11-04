"""Synthetic journal ranking benchmark. No dotenv, hosted DB or implicit live call."""

import argparse
import asyncio
import json
import math
import os
import statistics
import sys
import time
from datetime import timedelta
from pathlib import Path
from uuid import uuid4

from pydantic import SecretStr
from sqlalchemy import delete

from app.ai.voyage import VoyageProvider
from app.core.config import Settings
from app.infrastructure.database.connection import Database
from app.infrastructure.database.models import AgeDeclaration, Consent, User, now
from app.modules.journal.ai import JournalSearchInput
from app.modules.journal.ai_models import JournalEntryEmbedding
from app.modules.journal.indexing import journal_document
from app.modules.journal.models import JournalEntry
from app.modules.journal.retrieval import hybrid_search
from tests.database_target import require_local_test_database, verify_test_database
from tests.fakes import FakeEmbedder

DATASET = Path(__file__).with_name("dataset.json")


def load_dataset():
    data = json.loads(DATASET.read_text(encoding="utf-8"))
    if data.get("synthetic") is not True:
        raise ValueError("Only the committed synthetic dataset is supported")
    return data


def metrics(results):
    return {"recall@6": statistics.mean(row[0] for row in results),
            "MRR@6": statistics.mean(row[1] for row in results),
            "p50_ms": statistics.median(row[2] for row in results),
            "p95_ms": sorted(row[2] for row in results)[math.ceil(len(results)*.95)-1]}


async def evaluate(database, settings, user_id, embedder, data=None):
    data = data or load_dataset()
    ids = {}
    entries = []
    # Callers supply a fresh synthetic user. Never delete another actor's entries.
    async with database.require()() as db, db.begin():
        for item in data["entries"]:
            row = JournalEntry(user_id=user_id, local_date=now().date()-timedelta(days=item["daysAgo"]),
                               timezone="UTC", mood=item["mood"], text=item["text"], emotions=[], factors=[], status="saved")
            db.add(row)
            await db.flush()
            ids[row.id] = item["id"]
            entries.append(row)
    calls = 0
    for row in entries:
        vector = await embedder.embed(journal_document(row, settings.journal_document_char_limit), "document")
        calls += 1
        async with database.require()() as db, db.begin():
            db.add(JournalEntryEmbedding(user_id=user_id, entry_id=row.id, entry_version=row.version, settings_version=1,
                   model=settings.voyage_model, dimensions=settings.voyage_dimensions,
                   content_sha256="0"*64, embedding=vector))
    groups = {mode: {group: [] for group in ("keyword", "paraphrase", "pattern", "all")}
              for mode in ("keyword", "hybrid")}
    for query in data["queries"]:
        for mode in groups:
            started = time.monotonic()
            vector = await embedder.embed(query["text"], "query") if mode == "hybrid" else None
            calls += int(mode == "hybrid")
            async with database.require()() as db:
                user = await db.get(User, user_id)
                result = await hybrid_search(db, user, JournalSearchInput(query=query["text"]),
                                             query_vector=vector, settings=settings, reason=None)
            ranked = [ids[next(key for key in ids if str(key) == row["id"])] for row in result["entries"]]
            relevant = set(query["relevant"])
            score = (len(set(ranked) & relevant)/len(relevant),
                     next((1/(index+1) for index, identity in enumerate(ranked) if identity in relevant), 0),
                     (time.monotonic()-started)*1000)
            groups[mode][query["group"]].append(score)
            groups[mode]["all"].append(score)
    return {**{mode: {group: metrics(rows) for group, rows in values.items()} for mode, values in groups.items()},
            "providerCalls": calls, "synthetic": True, "qualityClaim": "pipeline only when embedder=fake"}


async def main(args):
    raw = os.environ.get("TEST_DATABASE_URL", "")
    require_local_test_database(raw)
    if args.embedder == "voyage" and not args.confirm_cost:
        raise SystemExit("Voyage requires --confirm-cost and a separately reviewed cost approval")
    settings = Settings(_env_file=None, app_env="test", database_url=raw, journal_semantic_enabled=True,
                        voyage_api_key=SecretStr(os.environ.get("VOYAGE_API_KEY", "") if args.embedder == "voyage" else "synthetic-no-network"),
                        voyage_dimensions=256, voyage_model="voyage-4-lite" if args.embedder == "voyage" else "synthetic")
    if not settings.journal_semantic_available:
        raise SystemExit("Explicit session provider key required for live evaluation")
    database = Database(settings)
    user_id = uuid4()
    created = False
    try:
        async with database.engine.begin() as connection:
            await verify_test_database(connection)
        async with database.require()() as db, db.begin():
            db.add(User(id=user_id, auth_subject=user_id, alias="Synthetic journal evaluation", age_band="adult", timezone="UTC"))
            await db.flush()
            db.add(AgeDeclaration(user_id=user_id, birth_year=2000, policy_version="self-declared-age-v1"))
            db.add(Consent(user_id=user_id, purpose="AI", enabled=True, policy_version="v1"))
        created = True
        provider = VoyageProvider(settings) if args.embedder == "voyage" else FakeEmbedder(256)
        report = await evaluate(database, settings, user_id, provider)
        report["embedder"] = args.embedder
        args.out.mkdir(parents=True, exist_ok=True)
        (args.out/"report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(report, ensure_ascii=False))
    finally:
        if created:
            async with database.require()() as db, db.begin():
                await db.execute(delete(JournalEntry).where(JournalEntry.user_id == user_id))
                await db.execute(delete(Consent).where(Consent.user_id == user_id))
                await db.execute(delete(AgeDeclaration).where(AgeDeclaration.user_id == user_id))
                await db.execute(delete(User).where(User.id == user_id))
        if database.engine:
            await database.engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--embedder", choices=("fake", "voyage"), default="fake")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--confirm-cost", action="store_true")
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main(parser.parse_args()))
