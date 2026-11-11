"""Real app composition accepts bounded providers and owns their shutdown."""

import httpx
import pytest
from app.main import create_app
from openai import AsyncOpenAI
from safevoice_shared.env import EnvSettings
from safevoice_shared.testing.knowledge_fixture import FixtureKnowledgeRetriever


@pytest.fixture
def settings():
    return EnvSettings(
        app_env="test",
        supabase_url="http://127.0.0.1:54721",
        supabase_publishable_key="synthetic",
        supabase_secret_key="synthetic",
        database_url="postgresql+asyncpg://safevoice_api:synthetic@127.0.0.1:54722/postgres",
        openai_api_key="synthetic-not-sent",
    )


async def test_injected_client_is_shared_by_real_runtime_and_closed(settings):
    def forbidden(request):
        pytest.fail("App construction must not make a provider request")

    client = AsyncOpenAI(
        api_key="synthetic", http_client=httpx.AsyncClient(transport=httpx.MockTransport(forbidden))
    )
    retriever = FixtureKnowledgeRetriever()
    app = create_app(
        settings, model_client_factory=lambda _: client, knowledge_factory=lambda *_: retriever
    )
    async with app.router.lifespan_context(app):
        assert app.state.runtime.openai_client is client
        assert app.state.knowledge is retriever
        assert not client.is_closed()
    assert client.is_closed()


async def test_knowledge_startup_failure_closes_metered_client(settings):
    client = AsyncOpenAI(api_key="synthetic")

    def failed(*args):
        raise ValueError("synthetic startup failure")

    app = create_app(settings, model_client_factory=lambda _: client, knowledge_factory=failed)
    with pytest.raises(ValueError, match="synthetic startup"):
        async with app.router.lifespan_context(app):
            pytest.fail("Startup cannot continue without its real retriever")
    assert client.is_closed()
