"""Disposable synthetic full-stack fixture. Never used by the application entrypoint."""
# ruff: noqa: E402 -- sanitize inherited configuration before importing app.main

import asyncio
import hashlib
import os
from datetime import UTC, datetime, timedelta
from uuid import UUID

import httpx
import uvicorn
from sqlalchemy import text
from sqlalchemy.engine import make_url

# Do not inherit real secrets from a developer's .env or environment.
url = os.environ.get("TEST_DATABASE_URL", "")
target = make_url(url) if url else None
if (
    not target
    or target.host not in ("127.0.0.1", "localhost")
    or not target.database.endswith("_test")
):
    raise RuntimeError("E2E requires an explicitly configured disposable local *_test database")
os.environ.update(
    {
        "APP_ENV": "test",
        "DATABASE_URL": "",
        "DATABASE_MIGRATION_URL": "",
        "SUPABASE_URL": "",
        "SUPABASE_PUBLISHABLE_KEY": "",
        "OPENAI_API_KEY": "",
        "OPENAI_MODEL": "",
        "AI_ENABLED": "false",
        "STT_ENABLED": "false",
        "VOYAGE_API_KEY": "",
        "SEMANTIC_MEMORY_ENABLED": "false",
        "VOYAGE_DIMENSIONS": "1024",
    }
)

from app.ai import embedding_models  # noqa: F401
from app.ai import models as chat_models  # noqa: F401
from app.ai.memory_models import MemoryProposal
from app.core.config import Settings
from app.infrastructure.database.models import AuthSession, Base, Consent, Memory, User
from app.main import create_app
from app.modules.guests import models as guest_models  # noqa: F401 -- register before reset
from app.modules.moderation.models import StaffRole
from tests.e2e_auth import LocalAuth
from tests.guest_schema import install_auth_fixture, install_guest_guards
from tests.mood_e2e_model import MoodE2EModel

# Phase D-I features on, as in a beta deployment; focus phases shortened to seconds
# (test env only). MATCHING_SCORER follows E2E_MATCHING_SCORER so the v2 spec can run
# against both the default (v1) and the candidate scorer.
app = create_app(
    Settings(
        _env_file=None,
        app_env="test",
        database_url=url,
        frontend_origin="http://127.0.0.1:5174",
        activities_enabled=True,
        focus_test_plan_seconds=int(os.environ.get("E2E_FOCUS_SECONDS", "20")),
        moderation_admin_enabled=True,
        matching_scorer=os.environ.get("E2E_MATCHING_SCORER", "v1"),
    )
)
app.state.ai.model_override = MoodE2EModel([])
# Only the disposable test entrypoint installs this transport. Production
# SupabaseAuth still verifies passwords, provider tokens and durable session rows.
app.state.settings.supabase_url = "https://local-auth.invalid"
app.state.settings.supabase_publishable_key = __import__("pydantic").SecretStr("synthetic-only")
app.state.auth_transport = httpx.MockTransport(LocalAuth(app.state.database).handle)


async def seed():
    async with app.state.database.engine.begin() as connection:
        await connection.execute(text("create schema if not exists moodprint"))
        await connection.execute(text("create schema if not exists extensions"))
        await connection.execute(text("create extension if not exists vector with schema extensions"))
        await connection.run_sync(Base.metadata.drop_all)
        await connection.run_sync(Base.metadata.create_all)
        await install_guest_guards(connection)
        await install_auth_fixture(connection)
    async with app.state.database.sessions.begin() as db:
        # 1-9 back the original journeys; 10-20 are fresh adults for the MVP journeys;
        # 21-36 back the activity, matching-v2 and moderation journeys; 37 is staff;
        # 38-39 are the responsive/accessibility pair; 40-41 the v2-only-goal pair.
        # 42-43 cover product experience; 44 the five-assistant review; 47-48 mood evidence.
        for number in range(1, 49):
            uid = UUID(f"00000000-0000-4000-8000-{number:012d}")
            provider = UUID(f"00000000-0000-4000-9000-{number:012d}")
            db.add(
                User(
                    id=uid,
                    auth_subject=uid,
                    alias=f"Bạn {number}",
                    age_band="unknown" if 7 <= number <= 9 else "adult",
                )
            )
            await db.flush()
            for purpose in ("AI", "MEM", "MATCH", "VOICE"):
                db.add(
                    Consent(
                        user_id=uid,
                        purpose=purpose,
                        enabled=number == 5 and purpose in ("AI", "MEM"),
                        version=1,
                    )
                )

            def hash_(value):
                return hashlib.sha256(value.encode()).hexdigest()

            auth_session = AuthSession(
                user_id=uid,
                token_hash=hash_(f"e2e-synthetic-session-{number}"),
                csrf_hash=hash_(f"e2e-synthetic-csrf-{number}"),
                provider_session_id=provider,
                expires_at=datetime.now(UTC) + timedelta(hours=1),
            )
            db.add(auth_session)
            await db.flush()
            if number == 5:
                db.add(
                    Memory(
                        user_id=uid,
                        bot_id="may",
                        text="Mục ghi nhớ tổng hợp đã được duyệt",
                        proposal_id=__import__("uuid").uuid4(),
                    )
                )
                db.add(MemoryProposal(user_id=uid, bot_id="guong", text="Đề xuất tổng hợp để bạn chỉnh sửa", purpose="memory", data_version=1, ai_consent_version=1, mem_consent_version=1, expires_at=datetime.now(UTC) + timedelta(minutes=15)))
            await db.execute(
                text("insert into auth.sessions(id,user_id) values (:id,:uid)"),
                {"id": provider, "uid": uid},
            )
            if number == 37:
                db.add(StaffRole(user_id=uid, role="moderator", granted_by="e2e-seed"))
    await app.state.database.engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed(), loop_factory=asyncio.SelectorEventLoop)
    uvicorn.run(
        app, host="127.0.0.1", port=8002, loop="app.core.loop:selector_factory", log_config=None
    )
