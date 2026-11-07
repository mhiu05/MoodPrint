from moodprint_agent.knowledge import create_retriever
from moodprint_shared.config import AppConfig
from moodprint_shared.contracts.knowledge import KnowledgeQuery, RetrievalScope


async def test_foundation_factory_returns_synthetic_knowledge_fixture() -> None:
    result = await create_retriever(AppConfig()).search(
        KnowledgeQuery(text="bạn bè"),
        scope=RetrievalScope(request_id="factory-test"),
        timeout_s=1,
    )
    assert result.corpus_version == "synthetic-fixture-v1"
