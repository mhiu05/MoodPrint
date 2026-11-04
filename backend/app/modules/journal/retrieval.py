"""Exact owner-filtered journal ranking; provider work never holds an owner lock."""

import asyncio
import json
import logging
import time
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import Float, func, select

from app.ai.voyage import VoyageProvider, validate_vector
from app.core.errors import DomainError
from app.infrastructure.database.models import User
from app.modules.journal.ai_models import JournalEntryEmbedding
from app.modules.journal.ai_settings import journal_ai_allowed
from app.modules.journal.models import JournalEntry

log = logging.getLogger("moodprint.journal_retrieval")


async def journal_query_vector(database, settings, actor, query: str, *, embedder=None):
    if not query.strip():
        return None, None, None
    async with database.require()() as db:
        user = await db.get(User, actor.user_id)
        version = await journal_ai_allowed(db, user, settings, "embed") if user else None
    if version is None:
        return None, None, "disabled"
    try:
        async with asyncio.timeout(settings.journal_query_timeout_seconds):
            vector = validate_vector(await (embedder or VoyageProvider(settings)).embed(query, "query"), settings.voyage_dimensions)
        return vector, version, None
    except TimeoutError:
        return None, version, "timeout"
    except Exception:
        return None, version, "provider_unavailable"


async def hybrid_search(db, user, args, *, query_vector, settings, reason):
    started = time.monotonic()
    today = datetime.now(ZoneInfo(user.timezone)).date()
    start, end = args.from_date or today-timedelta(days=89), args.to_date or today
    if start > end or end > today or start < today-timedelta(days=89):
        raise DomainError(422, "JOURNAL_SCOPE_EXPIRED", "Chọn khoảng ngày trong 90 ngày gần đây.")
    scope = (JournalEntry.user_id == user.id, JournalEntry.status == "saved",
             JournalEntry.local_date >= start, JournalEntry.local_date <= end)
    base = select(JournalEntry).where(*scope)
    order = (JournalEntry.local_date.desc(), JournalEntry.created_at.desc(), JournalEntry.id.desc())
    query = args.query.strip()
    version = await journal_ai_allowed(db, user, settings, "embed") if settings else None
    indexed = 0
    semantic = []
    if version is not None:
        vector_scope = (*scope, JournalEntryEmbedding.user_id == user.id,
                        JournalEntryEmbedding.entry_version == JournalEntry.version,
                        JournalEntryEmbedding.settings_version == version,
                        JournalEntryEmbedding.model == settings.voyage_model,
                        JournalEntryEmbedding.dimensions == settings.voyage_dimensions)
        joined = select(JournalEntry).join(JournalEntryEmbedding, JournalEntryEmbedding.entry_id == JournalEntry.id).where(*vector_scope)
        indexed = await db.scalar(select(func.count()).select_from(joined.subquery())) or 0
        if query_vector is not None and indexed:
            distance = JournalEntryEmbedding.embedding.op("OPERATOR(extensions.<=>)", return_type=Float)(query_vector)
            semantic = list((await db.scalars(joined.where(distance <= 1-settings.journal_similarity_threshold)
                                             .order_by(distance, *order).limit(settings.journal_semantic_top_k))).all())
        if query and not indexed and reason is None:
            reason = "not_indexed"
    elif query and reason is None:
        reason = "disabled"
    keyword = list((await db.scalars(base.where(JournalEntry.text.icontains(query, autoescape=True))
                                    .order_by(*order).limit(args.limit+1))).all()) if query else []
    recent_k = settings.journal_recent_k if settings else 2
    # An empty query preserves a useful bounded chronological sample.
    recent = list((await db.scalars(base.order_by(*order).limit(recent_k if query else args.limit+1))).all())
    ranked: dict[UUID, tuple[JournalEntry, str]] = {}
    for kind, rows in (("semantic", semantic), ("keyword", keyword), ("recent", recent)):
        for row in rows:
            ranked.setdefault(row.id, (row, kind))
    entries: list[dict[str, Any]] = []
    for row, kind in ranked.values():
        if len(entries) >= args.limit:
            break
        position = row.text.lower().find(query.lower()) if query else 0
        offset = max(0, position-300)
        snippet = row.text[offset:offset+1000]
        candidate = {"id": str(row.id), "version": row.version, "localDate": str(row.local_date),
                     "mood": row.mood, "emotions": [str(item)[:48] for item in row.emotions[:12]],
                     "factors": [str(item)[:48] for item in row.factors[:12]], "snippet": snippet,
                     "snippetTruncated": offset > 0 or offset+len(snippet) < len(row.text), "match": kind}
        if len(json.dumps(entries+[candidate], ensure_ascii=False).encode()) > 24_000:
            break
        entries.append(candidate)
    mode = "hybrid" if query_vector is not None and version is not None and indexed else "keyword" if query else "recent"
    log.info("metric=journal_retrieval mode=%s semantic=%d keyword=%d recent=%d latency_ms=%d",
             mode, len(semantic), len(keyword), len(recent), (time.monotonic()-started)*1000)
    return {"entries": entries, "coverage": {"from": str(start), "to": str(end), "returnedCount": len(entries),
            "hasMore": len(ranked) > len(entries), "limit": args.limit, "completeHistory": False,
            "indexed": indexed, "retrieval": {"mode": mode, "reason": reason}}}
