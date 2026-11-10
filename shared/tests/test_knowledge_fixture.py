import pytest
from moodprint_shared.testing.knowledge_contract import KnowledgeRetrieverContract


@pytest.fixture
def retriever():
    from moodprint_shared.testing import FixtureKnowledgeRetriever

    return FixtureKnowledgeRetriever()


class TestFixtureKnowledgeRetriever(KnowledgeRetrieverContract):
    pass


async def test_returned_citation_mutation_does_not_change_fixture(retriever):
    from moodprint_shared.contracts.knowledge import KnowledgeQuery, RetrievalScope

    query = KnowledgeQuery(text="hỗ trợ", top_k=1)
    scope = RetrievalScope(request_id="synthetic-isolation")
    first = await retriever.search(query, scope=scope, timeout_s=1)
    first.chunks[0].citation.country_scope.clear()
    second = await retriever.search(query, scope=scope, timeout_s=1)
    assert second.chunks[0].citation.country_scope


async def test_positive_timeout_is_enforced(retriever):
    from moodprint_shared.contracts.errors import KnowledgeTimeout
    from moodprint_shared.contracts.knowledge import KnowledgeQuery, RetrievalScope

    with pytest.raises(KnowledgeTimeout):
        await retriever.search(
            KnowledgeQuery(text="hỗ trợ"),
            scope=RetrievalScope(request_id="synthetic-timeout"),
            timeout_s=1e-12,
        )


@pytest.mark.parametrize("timeout_s", [1e-12, 1e-9, 1e-6, 5e-4])
async def test_timeout_below_modelled_latency_always_times_out(retriever, timeout_s):
    """Regression: sub-clock-resolution timeouts must not depend on the OS timer granularity."""
    from moodprint_shared.contracts.errors import KnowledgeTimeout
    from moodprint_shared.contracts.knowledge import KnowledgeQuery, RetrievalScope

    for _ in range(25):
        with pytest.raises(KnowledgeTimeout):
            await retriever.search(
                KnowledgeQuery(text="hỗ trợ"),
                scope=RetrievalScope(request_id="synthetic-timeout"),
                timeout_s=timeout_s,
            )


async def test_timeout_at_or_above_modelled_latency_still_serves(retriever):
    from moodprint_shared.contracts.knowledge import KnowledgeQuery, RetrievalScope
    from moodprint_shared.testing.knowledge_fixture import FIXTURE_MIN_LATENCY_S

    result = await retriever.search(
        KnowledgeQuery(text="hỗ trợ"),
        scope=RetrievalScope(request_id="synthetic-timeout-ok"),
        timeout_s=FIXTURE_MIN_LATENCY_S * 10,
    )
    assert result.status in {"ok", "no_results"}
