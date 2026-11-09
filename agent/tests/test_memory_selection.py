"""U-AG-80…95 (retrieval side): intent-aware selection, limits, domain headline, compaction policy."""

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from moodprint_agent.memory.compaction import (
    estimate_items_tokens,
    token_compaction_policy,
)
from moodprint_agent.memory.context_builder import DomainSummary, MemoryContextBuilder
from moodprint_agent.memory.selection import infer_categories, memory_query
from moodprint_shared.config import AgentConfig, AppConfig, MemoryConfig
from moodprint_shared.contracts.auth import AuthContext
from moodprint_shared.contracts.context import ContextRequest
from moodprint_shared.contracts.memory import Memory, MemoryHit, MemoryQuery

NOW = datetime(2026, 11, 8, tzinfo=UTC)
USER = UUID("10000000-0000-0000-0000-000000000002")


def memory_hit(
    text: str, *, score: float = 0.9, created_days_ago: int = 10, **changes
) -> MemoryHit:
    created = NOW - timedelta(days=created_days_ago)
    return MemoryHit(
        memory=Memory(
            id=uuid4(),
            owner_id=USER,
            category="preference",
            content=text,
            content_hash=text,
            created_at=created,
            updated_at=created,
            **changes,
        ),
        score=score,
    )


def request(text: str = "Bạn thân", **changes) -> ContextRequest:
    return ContextRequest(
        auth=AuthContext(USER, None, None, "{}"),
        conversation_id=uuid4(),
        user_input=text,
        token_budget=changes.pop("token_budget", 2000),
        nickname="An",
        **changes,
    )


class Search:
    def __init__(self, hits=()):
        self.hits, self.queries = list(hits), []

    async def search(self, auth, query: MemoryQuery):
        self.queries.append(query)
        return self.hits


class Domain:
    def __init__(self, summary=None, error=None):
        self._summary, self._error, self.asked = summary, error, []

    async def summary(self, auth, case_id):
        self.asked.append(case_id)
        if self._error:
            raise self._error
        return self._summary


@pytest.mark.parametrize(
    "text, expected",
    [
        ("Mình nên nhờ ai giúp đây?", ["support_person"]),
        ("Giúp mình mở lời với cô giáo", ["support_person", "communication"]),
        ("Mình thích trả lời ngắn thôi", ["preference"]),
        ("Mục tiêu tuần này của mình là gì", ["goal"]),
        ("Hôm nay trời đẹp", []),  # nothing to go on: search every category, do not guess
        ("Mình thích nhờ ai nói chuyện với thầy giáo, mục tiêu là kế hoạch", []),  # too ambiguous
    ],
)
def test_categories_are_inferred_only_when_the_intent_is_clear(text: str, expected: list[str]):
    assert sorted(infer_categories(text)) == sorted(expected)


def test_the_query_carries_the_case_title_and_stays_bounded():
    query = memory_query("Mình nên nói với ai", case_title="Nhóm chat lớp 8A", limit=3)
    assert "Nhóm chat lớp 8A" in query.text and query.limit == 3
    assert memory_query("x" * 9000, case_title=None, limit=1).text == "x" * 4000


async def test_no_match_means_no_memory_section_never_a_fallback_to_everything():
    builder = MemoryContextBuilder(Search([]), AppConfig(), clock=lambda: NOW)
    bundle = await builder.build(request("Hôm nay mình đi học"))
    assert [s.kind for s in bundle.sections] == ["identity"]


async def test_only_the_configured_number_of_memories_reaches_the_prompt():
    cfg = AppConfig(memory=MemoryConfig(max_context_memories=2, search_limit=5))
    hits = [memory_hit(f"Sở thích {n}", score=1 - n / 10) for n in range(5)]
    bundle = await MemoryContextBuilder(Search(hits), cfg, clock=lambda: NOW).build(request())
    assert [s.text for s in bundle.sections if s.kind == "memory"] == ["Sở thích 0", "Sở thích 1"]
    assert sum(1 for d in bundle.dropped if d.reason == "limit") == 3


async def test_the_label_date_is_the_approval_date_not_today():
    builder = MemoryContextBuilder(
        Search([memory_hit("Thích vẽ", created_days_ago=20)]), AppConfig(), clock=lambda: NOW
    )
    section = next(s for s in (await builder.build(request())).sections if s.kind == "memory")
    assert section.provenance[0].retrieved_at == NOW - timedelta(days=20)
    assert section.provenance[0].source_kind == "approved_memory"


async def test_a_stale_memory_is_marked_and_ranked_below_a_fresh_one():
    cfg = AppConfig()
    old = memory_hit("Cũ", score=0.9, created_days_ago=200)
    fresh = memory_hit("Mới", score=0.5, created_days_ago=5)
    bundle = await MemoryContextBuilder(Search([old, fresh]), cfg, clock=lambda: NOW).build(
        request()
    )
    by_text = {s.text: s for s in bundle.sections if s.kind == "memory"}
    assert by_text["Cũ"].provenance[0].stale and not by_text["Mới"].provenance[0].stale
    assert by_text["Mới"].priority > by_text["Cũ"].priority


async def test_the_domain_section_is_a_headline_without_events_or_people():
    case_id = uuid4()
    domain = Domain(DomainSummary("Nhóm chat lớp 8A", "active", 4, NOW - timedelta(days=2)))
    search = Search([])
    bundle = await MemoryContextBuilder(
        search, AppConfig(), clock=lambda: NOW, domain=domain
    ).build(request("Mình nên làm gì tiếp", linked_case_id=case_id))
    section = next(s for s in bundle.sections if s.kind == "domain")
    assert domain.asked == [case_id]
    assert '"events":4' in section.text and "Nhóm chat lớp 8A" in section.text
    assert "[người dùng kể]" in section.text and "2026-11-06" in section.text
    assert "Nhóm chat lớp 8A" in search.queries[0].text  # the title helps find related memories


async def test_no_domain_lookup_without_a_linked_case_and_failures_degrade():
    domain = Domain(DomainSummary("x", "active", 0, NOW))
    builder = MemoryContextBuilder(Search([]), AppConfig(), clock=lambda: NOW, domain=domain)
    assert [s.kind for s in (await builder.build(request())).sections] == ["identity"]
    assert domain.asked == []
    broken = MemoryContextBuilder(
        Search([]),
        AppConfig(),
        clock=lambda: NOW,
        domain=Domain(error=RuntimeError("private-canary")),
    )
    bundle = await broken.build(request(linked_case_id=uuid4()))
    assert any(d.kind == "domain" and d.reason == "service_unavailable" for d in bundle.dropped)
    assert "private-canary" not in bundle.model_dump_json()


def test_compaction_waits_for_the_token_threshold_not_an_item_count():
    cfg = AppConfig(agent=AgentConfig(compaction_trigger_tokens=1000))
    policy = token_compaction_policy(cfg)
    small = [{"role": "assistant", "content": "ok"} for _ in range(40)]  # many items, few tokens
    assert estimate_items_tokens(small) < 1000
    assert policy({"compaction_candidate_items": small, "session_items": small}) is False
    big = [{"role": "assistant", "content": "x" * 1200} for _ in range(3)]
    assert policy({"compaction_candidate_items": big, "session_items": big}) is True
    # A session that is mostly user text has nothing the SDK may rewrite.
    assert policy({"compaction_candidate_items": [], "session_items": big}) is False
    assert policy({}) is False
