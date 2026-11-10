"""Database URL TLS options must reach asyncpg without unsupported keywords."""

import inspect

import asyncpg
import pytest
from app.core.db import create_engine
from moodprint_shared.config import AppConfig
from pydantic import SecretStr


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["require", "verify-full"])
async def test_libpq_sslmode_is_translated_for_asyncpg(settings, monkeypatch, mode):
    signature = inspect.signature(asyncpg.connect)

    class ConnectionAttempt(Exception):
        pass

    async def connect(*args, **kwargs):
        signature.bind(*args, **kwargs)
        assert kwargs["ssl"] == mode
        raise ConnectionAttempt

    monkeypatch.setattr(asyncpg, "connect", connect)
    settings = settings.model_copy(
        update={
            "database_url": SecretStr(
                "postgresql+asyncpg://moodprint_api:synthetic@127.0.0.1:54322/postgres"
                f"?sslmode={mode}"
            )
        }
    )
    engine = create_engine(settings, AppConfig())
    try:
        with pytest.raises(ConnectionAttempt):
            async with engine.connect():
                pass
    finally:
        await engine.dispose()
