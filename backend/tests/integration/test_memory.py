from datetime import UTC, datetime, timedelta

import pytest
from app.core.uow import user_uow
from app.modules.memory.service import MemoryService
from moodprint_shared.contracts.errors import NotFound, VersionConflict
from moodprint_shared.contracts.memory import (
    CandidateDecision,
    MemoryCandidateCreate,
    MemoryCreate,
    MemoryQuery,
)
from sqlalchemy import text

pytestmark = pytest.mark.integration


async def test_deleting_deduped_approved_memory_removes_all_candidate_content(
    db_engine, identities
):
    service = MemoryService(db_engine)
    auth = identities[0]
    approved_ids = []
    for original in ("Synthetic private preference", "Original proposal edited before consent"):
        candidate = await service.propose(
            auth, MemoryCandidateCreate(category="preference", content=original)
        )
        result = await service.decide(
            auth,
            candidate.id,
            CandidateDecision(decision="approve", edited_content="Synthetic private preference"),
        )
        approved_ids.append(candidate.id)
    await service.delete(auth, result.id)
    async with user_uow(db_engine, auth) as uow:
        assert (
            await uow.session.scalar(
                text(
                    "SELECT count(*) FROM app.memory_candidates WHERE id=ANY(:ids) AND owner_id=:owner"
                ),
                {"ids": approved_ids, "owner": auth.user_id},
            )
            == 0
        )


async def test_supersede_into_duplicate_keeps_both_chains_deletable(db_engine, identities):
    service = MemoryService(db_engine)
    auth = identities[0]
    a = await service.create(auth, MemoryCreate(category="goal", content="Goal A old version"))
    a = await service.update(auth, a.id, "Goal A current version")
    b = await service.create(auth, MemoryCreate(category="goal", content="Goal B old version"))
    b = await service.update(auth, b.id, "Canonical goal B")
    candidate = await service.propose(
        auth, MemoryCandidateCreate(category="goal", content=b.content, supersedes_memory_id=a.id)
    )
    canonical = await service.decide(auth, candidate.id, CandidateDecision(decision="approve"))
    assert canonical.id == b.id
    await service.delete(auth, canonical.id)
    assert await service.list(auth) == []
    assert await service.list(auth, status="superseded") == []


async def test_retrieval_does_not_refresh_content_age_or_version(db_engine, identities):
    from sqlalchemy.ext.asyncio import create_async_engine

    from backend.tests.integration.conftest import local_value

    service = MemoryService(db_engine)
    auth = identities[0]
    memory = await service.create(
        auth, MemoryCreate(category="preference", content="Synthetic stale preference")
    )
    admin = create_async_engine(local_value("TEST_ADMIN_DATABASE_URL"))
    try:
        async with admin.begin() as connection:
            # This is synthetic test setup; disabling only these triggers preserves a controlled old timestamp.
            await connection.execute(
                text("ALTER TABLE app.user_memories DISABLE TRIGGER user_memories_touch")
            )
            await connection.execute(
                text(
                    "UPDATE app.user_memories SET updated_at=now()-interval '100 days' WHERE id=:id"
                ),
                {"id": memory.id},
            )
            await connection.execute(
                text("ALTER TABLE app.user_memories ENABLE TRIGGER user_memories_touch")
            )
    finally:
        await admin.dispose()
    before = (await service.list(auth))[0]
    assert await service.search(auth, MemoryQuery(text="stale preference"))
    after = (await service.list(auth))[0]
    assert after.last_retrieved_at is not None
    assert after.updated_at == before.updated_at
    assert after.version == before.version


async def test_memory_crud_dedupe_supersede_delete_chain(db_engine, identities):
    service = MemoryService(db_engine)
    a, b = identities
    first = await service.create(
        a, MemoryCreate(category="preference", content="  Mình thích bạn thân  ")
    )
    duplicate = await service.create(
        a, MemoryCreate(category="preference", content="mình THÍCH bạn thân")
    )
    assert duplicate.id == first.id
    assert (await service.list(a))[0].content == "Mình thích bạn thân"
    assert await service.list(b) == []
    with pytest.raises(NotFound):
        await service.update(b, first.id, "private")
    new = await service.update(a, first.id, "Mình thích đọc sách với bạn thân")
    assert new.supersedes_id == first.id
    assert [m.id for m in await service.list(a)] == [new.id]
    await service.delete(a, new.id)
    assert await service.list(a, status="superseded") == []
    assert await service.list(a) == []


async def test_candidate_explicit_consent_edit_reject_and_double_decide(db_engine, identities):
    service = MemoryService(db_engine)
    a, b = identities
    candidate = await service.propose(
        a, MemoryCandidateCreate(category="goal", content="Học nói rõ điều mình cần")
    )
    assert await service.list(a) == []
    with pytest.raises(NotFound):
        await service.decide(b, candidate.id, CandidateDecision(decision="approve"))
    memory = await service.decide(
        a,
        candidate.id,
        CandidateDecision(decision="approve", edited_content="Mình muốn giao tiếp rõ ràng"),
    )
    assert memory.content == "Mình muốn giao tiếp rõ ràng"
    assert memory.source_candidate_id == candidate.id
    with pytest.raises(VersionConflict):
        await service.decide(a, candidate.id, CandidateDecision(decision="reject"))
    rejected = await service.propose(
        a, MemoryCandidateCreate(category="goal", content="Không giữ mục này")
    )
    assert await service.decide(a, rejected.id, CandidateDecision(decision="reject")) is None
    assert len(await service.list(a)) == 1


async def test_search_relevant_accent_insensitive_empty_expiry_owner(db_engine, identities):
    service = MemoryService(db_engine)
    a, b = identities
    one = await service.create(
        a,
        MemoryCreate(category="support_person", content="Bạn thân là người mình có thể trò chuyện"),
    )
    await service.create(a, MemoryCreate(category="preference", content="Mình thích màu xanh"))
    await service.create(
        a,
        MemoryCreate(
            category="context",
            content="Bạn thân cũ",
            expires_at=datetime.now(UTC) - timedelta(days=1),
        ),
    )
    assert await service.search(a, MemoryQuery(text="zzzzzzzzzzzzzzz")) == []
    assert await service.search(a, MemoryQuery(text="")) == []
    assert await service.search(b, MemoryQuery(text="ban than")) == []
    hits = await service.search(a, MemoryQuery(text="ban than", limit=1))
    assert [hit.memory.id for hit in hits] == [one.id]
    assert (await service.list(a))[0].last_retrieved_at is not None or any(
        m.last_retrieved_at for m in await service.list(a)
    )
