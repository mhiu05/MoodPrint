"""Deterministic, bounded context built exclusively from service contracts."""

import json
import math
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Protocol
from uuid import UUID

from moodprint_shared.config import AppConfig
from moodprint_shared.contracts.auth import AuthContext
from moodprint_shared.contracts.context import (
    ContextBundle,
    ContextKind,
    ContextRequest,
    ContextSection,
    DroppedSection,
    Provenance,
)
from moodprint_shared.contracts.memory import MemoryHit, MemoryQuery

from moodprint_agent.memory.selection import memory_query


class MemorySearch(Protocol):
    async def search(self, auth: AuthContext, query: MemoryQuery) -> list[MemoryHit]: ...


@dataclass(frozen=True, slots=True)
class DomainSummary:
    """Headline facts about the linked case. Never events, people or evidence content."""

    title: str
    status: str
    event_count: int
    updated_at: datetime


class DomainSummaries(Protocol):
    async def summary(self, auth: AuthContext, case_id: UUID) -> DomainSummary | None: ...


def _now() -> datetime:
    return datetime.now(UTC)


def estimate_tokens(text: str) -> int:
    return math.ceil(len(text) / 3)


class MemoryContextBuilder:
    def __init__(
        self,
        memory: MemorySearch,
        cfg: AppConfig,
        *,
        clock: Callable[[], datetime] = _now,
        domain: DomainSummaries | None = None,
    ) -> None:
        self.memory, self.cfg, self.clock = memory, cfg, clock
        self.domain = domain

    async def build(self, request: ContextRequest) -> ContextBundle:
        now = self.clock()
        sections: list[ContextSection] = []
        dropped: list[DroppedSection] = []

        def add(
            kind: ContextKind,
            text: str,
            source_kind: str,
            source_id: str,
            priority: int,
            stale: bool = False,
            at: datetime | None = None,
        ) -> None:
            sections.append(
                ContextSection(
                    kind=kind,
                    text=text,
                    tokens=estimate_tokens(text),
                    priority=priority,
                    provenance=[
                        Provenance(
                            source_kind=source_kind,
                            source_id=source_id,
                            retrieved_at=at or now,
                            stale=stale,
                        )
                    ],
                )
            )

        # No raw claims are inspected: only profile fields explicitly passed by the service.
        identity = json.dumps(
            {
                "nickname": request.nickname,
                "age_band": request.age_band,
                "locale": request.locale,
            },
            ensure_ascii=False,
            separators=(",", ":"),
        )
        add("identity", identity, "profile", "profile", 1000)
        if request.conversation_summary:
            add(
                "conversation_summary",
                request.conversation_summary,
                "conversation_summary",
                str(request.conversation_id),
                900,
            )

        summary: DomainSummary | None = None
        if request.linked_case_id is not None and self.domain is not None:
            try:
                summary = await self.domain.summary(request.auth, request.linked_case_id)
            except Exception:
                dropped.append(
                    DroppedSection(kind="domain", reason="service_unavailable", source_ids=[])
                )
        if summary is not None:
            # Headline only: the details are fetched with get_case_context, by the model, on demand.
            add(
                "domain",
                json.dumps(
                    {
                        "label": "[người dùng kể]",
                        "case_id": str(request.linked_case_id),
                        "title": summary.title,
                        "status": summary.status,
                        "events": summary.event_count,
                        "updated": summary.updated_at.date().isoformat(),
                    },
                    ensure_ascii=False,
                    separators=(",", ":"),
                ),
                "case_summary",
                str(request.linked_case_id),
                700,
            )

        hits: list[MemoryHit] = []
        if request.user_input.strip():
            try:
                hits = await self.memory.search(
                    request.auth,
                    memory_query(
                        request.user_input,
                        case_title=summary.title if summary else None,
                        limit=self.cfg.memory.search_limit,
                    ),
                )
            except Exception:
                dropped.append(
                    DroppedSection(kind="memory", reason="service_unavailable", source_ids=[])
                )

        hashes: set[str] = set()
        ids: set[str] = set()
        included = 0
        # Stable lexical order on ties; adapter ordering cannot alter prompt caching.
        for hit in sorted(hits, key=lambda hit: (-hit.score, str(hit.memory.id))):
            memory = hit.memory
            source_id = str(memory.id)
            if (
                hit.score <= 0
                or memory.status != "active"
                or memory.owner_id != request.auth.user_id
                or (memory.expires_at is not None and memory.expires_at <= now)
            ):
                continue
            if memory.content_hash in hashes or source_id in ids:
                dropped.append(
                    DroppedSection(kind="memory", reason="duplicate", source_ids=[source_id])
                )
                continue
            if included >= self.cfg.memory.max_context_memories:
                dropped.append(
                    DroppedSection(kind="memory", reason="limit", source_ids=[source_id])
                )
                continue
            hashes.add(memory.content_hash)
            ids.add(source_id)
            included += 1
            stale = memory.updated_at < now - timedelta(days=self.cfg.memory.stale_days)
            priority = 500 + min(100, int(hit.score * 100)) - (200 if stale else 0)
            # The label shows when the user approved it (memories are created on approval).
            add(
                "memory",
                memory.content,
                "approved_memory",
                source_id,
                priority,
                stale,
                at=memory.created_at,
            )

        # Phase 0 has no domain or knowledge injection; both remain explicit service/tool seams.
        remaining = request.token_budget
        kept: set[int] = set()
        for index in sorted(
            range(len(sections)), key=lambda index: (-sections[index].priority, index)
        ):
            section = sections[index]
            if section.tokens <= remaining:
                kept.add(index)
                remaining -= section.tokens
            else:
                dropped.append(
                    DroppedSection(
                        kind=section.kind,
                        reason="token_budget",
                        source_ids=[source.source_id for source in section.provenance],
                    )
                )
        output = [section for index, section in enumerate(sections) if index in kept]
        return ContextBundle(
            sections=output, dropped=dropped, total_tokens=sum(s.tokens for s in output)
        )
