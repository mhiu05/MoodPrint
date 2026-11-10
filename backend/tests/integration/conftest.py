"""Synthetic local-only DB fixtures; deliberately never load the root dotenv."""

import json
import os
from pathlib import Path
from uuid import uuid4

import pytest
from dotenv import dotenv_values
from moodprint_shared.contracts.auth import AuthContext
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine

LOCAL_ENV = Path(__file__).resolve().parents[3] / ".local" / "test.env"


def local_value(name: str) -> str:
    value = os.environ.get(name) or dotenv_values(LOCAL_ENV).get(name)
    if not value:
        pytest.fail(f"{name} missing: start local Supabase and run bootstrap_local_db.py")
    if "DATABASE_URL" in name and make_url(value).host not in {"localhost", "127.0.0.1", "::1"}:
        pytest.fail("Integration tests only accept loopback database hosts")
    return value


@pytest.fixture
async def db_engine():
    engine = create_async_engine(
        local_value("TEST_DATABASE_URL"), pool_size=2, max_overflow=0, hide_parameters=True
    )
    try:
        yield engine
    finally:
        await engine.dispose()


@pytest.fixture
async def identities():
    admin = create_async_engine(local_value("TEST_ADMIN_DATABASE_URL"), hide_parameters=True)
    owners = [uuid4(), uuid4()]
    async with admin.begin() as conn:
        for owner in owners:
            await conn.execute(text("INSERT INTO auth.users(id) VALUES(:id)"), {"id": owner})
    contexts = [
        AuthContext(
            user_id=u,
            session_id=None,
            aal="aal1",
            claims_json=json.dumps({"sub": str(u), "role": "authenticated"}),
        )
        for u in owners
    ]
    try:
        yield contexts
    finally:
        async with admin.begin() as conn:
            sessions = list(
                (
                    await conn.execute(
                        text("SELECT id FROM app.conversations WHERE owner_id=ANY(:ids)"),
                        {"ids": owners},
                    )
                ).scalars()
            )
            if sessions:
                await conn.execute(
                    text("DELETE FROM agent_store.agent_sessions WHERE session_id=ANY(:ids)"),
                    {"ids": [str(id) for id in sessions]},
                )
            await conn.execute(text("DELETE FROM auth.users WHERE id=ANY(:ids)"), {"ids": owners})
        await admin.dispose()
