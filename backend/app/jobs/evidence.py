"""Bounded evidence purge worker with committed claims and HTTP outside transactions."""

import asyncio
import logging
from collections import defaultdict

from sqlalchemy import text

logger = logging.getLogger(__name__)


async def purge_once(engine, storage, batch_size: int = 100) -> int:
    async with engine.begin() as connection:
        rows = list(
            (
                await connection.execute(
                    text("SELECT * FROM app_private.claim_evidence_for_purge(:batch)"),
                    {"batch": batch_size},
                )
            ).mappings()
        )
    groups = defaultdict(list)
    for row in rows:
        groups[row["id"]]
        if row["storage_key"]:
            groups[row["id"]].append(row["storage_key"])
    completed = 0
    for id, keys in groups.items():
        try:
            await storage.delete(keys)
        except asyncio.CancelledError:
            raise
        except Exception:
            # A bounded lease makes a later run retry without logging user content.
            logger.warning("evidence_purge_storage_failed")
            continue
        async with engine.begin() as connection:
            await connection.execute(
                text("SELECT app_private.finish_evidence_purge(:id)"), {"id": id}
            )
        completed += 1
    return completed


async def purge_loop(engine, storage, interval_s: float = 30):
    while True:
        try:
            await purge_once(engine, storage)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.warning("evidence_purge_iteration_failed")
        await asyncio.sleep(interval_s)
