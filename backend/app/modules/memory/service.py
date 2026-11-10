from __future__ import annotations

import builtins
import hashlib
import unicodedata
from datetime import UTC, datetime
from uuid import UUID, uuid4

from moodprint_shared.config import AppConfig
from moodprint_shared.contracts.auth import AuthContext
from moodprint_shared.contracts.errors import NotFound, VersionConflict
from moodprint_shared.contracts.memory import (
    CandidateDecision,
    Memory,
    MemoryCandidate,
    MemoryCandidateCreate,
    MemoryCreate,
    MemoryHit,
    MemoryQuery,
    MemoryStatus,
)
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.uow import user_uow


def content_hash(content: str) -> str:
    return hashlib.sha256(
        " ".join(unicodedata.normalize("NFKC", content).casefold().split()).encode()
    ).hexdigest()


def dto(model, row):
    return model.model_validate({name: row[name] for name in model.model_fields if name in row})


class MemoryService:
    def __init__(self, engine: AsyncEngine, cfg: AppConfig | None = None):
        self.engine, self.cfg = engine, cfg or AppConfig()

    async def _lock_owner(self, session, auth: AuthContext) -> None:
        # Serialize graph mutations across processes, without locking another user's memory.
        await session.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:key,0))"),
            {"key": "memory:" + str(auth.user_id)},
        )

    async def _link_supersession(
        self, session, auth: AuthContext, canonical_id: UUID, previous_id: UUID
    ) -> None:
        if canonical_id == previous_id:
            return
        rows = builtins.list(
            (
                await session.execute(
                    text("""WITH RECURSIVE ancestors AS (
            SELECT id,supersedes_id FROM app.user_memories WHERE id=:id AND owner_id=:owner
            UNION SELECT m.id,m.supersedes_id FROM app.user_memories m JOIN ancestors a ON m.id=a.supersedes_id WHERE m.owner_id=:owner
            ) SELECT id,supersedes_id FROM ancestors"""),
                    {"id": canonical_id, "owner": auth.user_id},
                )
            ).mappings()
        )
        if previous_id in {row["id"] for row in rows}:
            return
        roots = [row for row in rows if row["supersedes_id"] is None]
        if len(roots) != 1:
            raise VersionConflict()
        # Canonical dedupe joins both version chains instead of dropping either history.
        await session.execute(
            text(
                "UPDATE app.user_memories SET supersedes_id=:previous WHERE id=:root AND owner_id=:owner"
            ),
            {"previous": previous_id, "root": roots[0]["id"], "owner": auth.user_id},
        )

    async def list(self, auth: AuthContext, *, status: MemoryStatus = "active") -> list[Memory]:
        async with user_uow(self.engine, auth) as uow:
            rows = (
                await uow.session.execute(
                    text(
                        "SELECT * FROM app.user_memories WHERE owner_id=:owner AND status=:status ORDER BY updated_at DESC,id"
                    ),
                    {"owner": auth.user_id, "status": status},
                )
            ).mappings()
            return [dto(Memory, row) for row in rows]

    async def _insert(
        self, session, auth, data: MemoryCreate, *, supersedes=None, candidate=None
    ) -> Memory:
        content = data.content.strip()
        if not content:
            from app.core.errors import ApiError

            raise ApiError("validation_failed", "Nội dung ký ức không được để trống.", 422)
        params = {
            "id": uuid4(),
            "owner": auth.user_id,
            "category": data.category,
            "content": content,
            "hash": content_hash(content),
            "source_conversation": data.source_conversation_id,
            "expires": data.expires_at,
            "supersedes": supersedes,
            "candidate": candidate,
            "source_kind": "approved_candidate" if candidate else "user_created",
        }
        await session.execute(
            text("""INSERT INTO app.user_memories
            (id,owner_id,category,content,content_hash,source_conversation_id,expires_at,supersedes_id,source_candidate_id,source_kind)
            VALUES(:id,:owner,:category,:content,:hash,:source_conversation,:expires,:supersedes,:candidate,:source_kind)
            ON CONFLICT(owner_id,content_hash) WHERE status='active' DO NOTHING"""),
            params,
        )
        row = (
            (
                await session.execute(
                    text(
                        "SELECT * FROM app.user_memories WHERE owner_id=:owner AND content_hash=:hash AND status='active'"
                    ),
                    params,
                )
            )
            .mappings()
            .one()
        )
        if supersedes and row["id"] != params["id"]:
            await self._link_supersession(session, auth, row["id"], supersedes)
            row = (
                (
                    await session.execute(
                        text("SELECT * FROM app.user_memories WHERE id=:id AND owner_id=:owner"),
                        {"id": row["id"], "owner": auth.user_id},
                    )
                )
                .mappings()
                .one()
            )
        return dto(Memory, row)

    async def create(self, auth: AuthContext, data: MemoryCreate) -> Memory:
        async with user_uow(self.engine, auth) as uow:
            await self._lock_owner(uow.session, auth)
            return await self._insert(uow.session, auth, data)

    async def update(self, auth: AuthContext, memory_id: UUID, content: str) -> Memory:
        async with user_uow(self.engine, auth) as uow:
            await self._lock_owner(uow.session, auth)
            row = (
                (
                    await uow.session.execute(
                        text(
                            "SELECT * FROM app.user_memories WHERE id=:id AND owner_id=:owner AND status='active' FOR UPDATE"
                        ),
                        {"id": memory_id, "owner": auth.user_id},
                    )
                )
                .mappings()
                .first()
            )
            if not row:
                raise NotFound()
            data = MemoryCreate(
                category=row["category"],
                content=content,
                source_conversation_id=row["source_conversation_id"],
                expires_at=row["expires_at"],
            )
            existing = (
                (
                    await uow.session.execute(
                        text(
                            "SELECT * FROM app.user_memories WHERE owner_id=:owner AND content_hash=:hash AND status='active'"
                        ),
                        {"owner": auth.user_id, "hash": content_hash(content)},
                    )
                )
                .mappings()
                .first()
            )
            if existing and existing["id"] == memory_id:
                return dto(Memory, existing)
            await uow.session.execute(
                text(
                    "UPDATE app.user_memories SET status='superseded' WHERE id=:id AND owner_id=:owner"
                ),
                {"id": memory_id, "owner": auth.user_id},
            )
            return await self._insert(uow.session, auth, data, supersedes=memory_id)

    async def delete(self, auth: AuthContext, memory_id: UUID) -> None:
        async with user_uow(self.engine, auth) as uow:
            await self._lock_owner(uow.session, auth)
            params = {"id": memory_id, "owner": auth.user_id}
            exists = await uow.session.scalar(
                text(
                    "SELECT id FROM app.user_memories WHERE id=:id AND owner_id=:owner FOR UPDATE"
                ),
                params,
            )
            if exists is None:
                raise NotFound()
            ids = builtins.list(
                (
                    await uow.session.execute(
                        text("""WITH RECURSIVE chain AS (
              SELECT id,supersedes_id FROM app.user_memories WHERE id=:id AND owner_id=:owner
              UNION
              SELECT m.id,m.supersedes_id FROM app.user_memories m JOIN chain c ON m.id=c.supersedes_id OR m.supersedes_id=c.id WHERE m.owner_id=:owner
            ) SELECT id FROM chain"""),
                        params,
                    )
                ).scalars()
            )
            await uow.session.execute(
                text(
                    "DELETE FROM app.memory_candidates WHERE owner_id=:owner AND (approved_memory_id=ANY(:ids) OR supersedes_memory_id=ANY(:ids) OR id IN (SELECT source_candidate_id FROM app.user_memories WHERE id=ANY(:ids) AND owner_id=:owner))"
                ),
                {"owner": auth.user_id, "ids": ids},
            )
            await uow.session.execute(
                text("DELETE FROM app.user_memories WHERE id=ANY(:ids) AND owner_id=:owner"),
                {"owner": auth.user_id, "ids": ids},
            )
            await uow.session.execute(
                text(
                    "INSERT INTO app.audit_events(actor_id,action,entity_type,entity_id) VALUES(:owner,'memory.deleted','memory',:id)"
                ),
                params,
            )

    async def propose(self, auth: AuthContext, data: MemoryCandidateCreate) -> MemoryCandidate:
        async with user_uow(self.engine, auth) as uow:
            await self._lock_owner(uow.session, auth)
            params = {**data.model_dump(), "id": uuid4(), "owner": auth.user_id}
            row = (
                (
                    await uow.session.execute(
                        text("""INSERT INTO app.memory_candidates
              (id,owner_id,category,content,source_kind,source_conversation_id,source_message_id,supersedes_memory_id)
              VALUES(:id,:owner,:category,:content,:source_kind,:source_conversation_id,:source_message_id,:supersedes_memory_id) RETURNING *"""),
                        params,
                    )
                )
                .mappings()
                .one()
            )
            return dto(MemoryCandidate, row)

    async def candidates(self, auth: AuthContext) -> list[MemoryCandidate]:
        async with user_uow(self.engine, auth) as uow:
            rows = (
                await uow.session.execute(
                    text(
                        "SELECT * FROM app.memory_candidates WHERE owner_id=:owner AND status='pending' AND expires_at>now() ORDER BY created_at,id"
                    ),
                    {"owner": auth.user_id},
                )
            ).mappings()
            return [dto(MemoryCandidate, row) for row in rows]

    async def decide(
        self, auth: AuthContext, candidate_id: UUID, decision: CandidateDecision
    ) -> Memory | None:
        async with user_uow(self.engine, auth) as uow:
            await self._lock_owner(uow.session, auth)
            params = {"id": candidate_id, "owner": auth.user_id}
            row = (
                (
                    await uow.session.execute(
                        text(
                            "SELECT * FROM app.memory_candidates WHERE id=:id AND owner_id=:owner FOR UPDATE"
                        ),
                        params,
                    )
                )
                .mappings()
                .first()
            )
            if not row:
                raise NotFound()
            if row["status"] != "pending" or row["expires_at"] <= datetime.now(UTC):
                raise VersionConflict()
            await uow.session.execute(
                text(
                    "UPDATE app.memory_candidates SET status=:status,decided_at=now() WHERE id=:id AND owner_id=:owner"
                ),
                {**params, "status": "approved" if decision.decision == "approve" else "rejected"},
            )
            if decision.decision == "reject":
                return None
            if row["supersedes_memory_id"]:
                old = await uow.session.scalar(
                    text(
                        "SELECT id FROM app.user_memories WHERE id=:id AND owner_id=:owner AND status='active' FOR UPDATE"
                    ),
                    {"id": row["supersedes_memory_id"], "owner": auth.user_id},
                )
                if old is None:
                    raise VersionConflict()
                await uow.session.execute(
                    text(
                        "UPDATE app.user_memories SET status='superseded' WHERE id=:id AND owner_id=:owner"
                    ),
                    {"id": old, "owner": auth.user_id},
                )
            memory = await self._insert(
                uow.session,
                auth,
                MemoryCreate(
                    category=row["category"],
                    content=decision.edited_content
                    if decision.edited_content is not None
                    else row["content"],
                    source_conversation_id=row["source_conversation_id"],
                ),
                supersedes=row["supersedes_memory_id"],
                candidate=candidate_id,
            )
            await uow.session.execute(
                text(
                    "UPDATE app.memory_candidates SET approved_memory_id=:memory WHERE id=:id AND owner_id=:owner"
                ),
                {**params, "memory": memory.id},
            )
            return memory

    async def search(self, auth: AuthContext, query: MemoryQuery) -> list[MemoryHit]:
        q = " ".join(query.text.split())
        if not q:
            return []
        async with user_uow(self.engine, auth) as uow:
            params = {
                "owner": auth.user_id,
                "q": q,
                "limit": query.limit,
                "categories": query.categories,
                "lexical": self.cfg.memory.lexical_weight,
                "similarity": self.cfg.memory.similarity_weight,
                "recency": self.cfg.memory.recency_weight,
            }
            rows = builtins.list(
                (
                    await uow.session.execute(
                        text("""SELECT m.*,
              :lexical * ts_rank(search,plainto_tsquery('simple',app_private.f_unaccent(:q))) +
              :similarity * extensions.similarity(app_private.f_unaccent(content),app_private.f_unaccent(:q)) +
              :recency / (1 + extract(epoch FROM (now()-updated_at))/86400) AS score
              FROM app.user_memories m WHERE owner_id=:owner AND status='active'
              AND (expires_at IS NULL OR expires_at>now())
              AND (cardinality(CAST(:categories AS text[]))=0 OR category=ANY(CAST(:categories AS text[])))
              AND (search @@ plainto_tsquery('simple',app_private.f_unaccent(:q))
                OR extensions.similarity(app_private.f_unaccent(content),app_private.f_unaccent(:q))>0.2)
              ORDER BY score DESC,id LIMIT :limit"""),
                        params,
                    )
                ).mappings()
            )
            if rows:
                await uow.session.execute(
                    text(
                        "UPDATE app.user_memories SET last_retrieved_at=now() WHERE id=ANY(:ids) AND owner_id=:owner"
                    ),
                    {"ids": [r["id"] for r in rows], "owner": auth.user_id},
                )
            return [MemoryHit(memory=dto(Memory, row), score=float(row["score"])) for row in rows]
