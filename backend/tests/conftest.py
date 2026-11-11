import pytest
from safevoice_shared.env import EnvSettings


@pytest.fixture
def settings():
    return EnvSettings(
        app_env="test",
        supabase_url="http://127.0.0.1:54321",
        supabase_publishable_key="test-public",
        supabase_secret_key="test-secret",
        database_url="postgresql+asyncpg://safevoice_api:local@127.0.0.1:54322/postgres",
        cors_allowed_origins=["http://127.0.0.1:5173"],
    )
