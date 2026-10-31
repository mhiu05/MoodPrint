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
from app.infrastructure.database.models import (
    AgeDeclaration,
    AuthSession,
    Base,
    Consent,
    Memory,
    User,
)
from app.main import create_app
from app.modules.guests import models as guest_models  # noqa: F401 -- register before reset
from app.modules.moderation.models import StaffRole
from tests.database_target import verify_test_database
from tests.e2e_auth import LocalAuth
from tests.feedback_schema import install_feedback_functions
from tests.guest_helpers import LIFETIME, add_guest, enable_paid_fixture
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
        guest_auth_enabled=True,
        guest_captcha_site_key="synthetic-site-key",
        guest_abuse_hmac_key="synthetic-local-hmac-key-not-a-secret-123456789",
        feedback_enabled=True,
        feedback_admin_enabled=True,
        product_tour_enabled=True,
    )
)
app.state.ai.model_override = MoodE2EModel([])
# Only the disposable test entrypoint installs this transport. Production
# SupabaseAuth still verifies passwords, provider tokens and durable session rows.
app.state.settings.supabase_url = "https://local-auth.invalid"
app.state.settings.supabase_publishable_key = __import__("pydantic").SecretStr("synthetic-only")
app.state.auth_transport = httpx.MockTransport(LocalAuth(app.state.database).handle)
enable_paid_fixture(app)


class SyntheticTranscriber:
    async def transcribe(self, data):
        return "Bản chữ tổng hợp để bạn duyệt"


app.state.transcriber = SyntheticTranscriber()


@app.post("/__test/reset-admission", include_in_schema=False)
async def reset_admission():
    # Scenario isolation only; production rate limits are unchanged and separately tested.
    from sqlalchemy import delete

    from app.modules.guests.models import GuestAbuseBucket
    async with app.state.database.sessions.begin() as db:
        await db.execute(delete(GuestAbuseBucket))
    return {"reset": True}


@app.post("/__test/near-expiry", include_in_schema=False)
async def near_expiry():
    guest = await add_guest(app, started_ago=LIFETIME - timedelta(seconds=7))
    cookies = [
        {"name": "moodprint_session", "value": guest.client.cookies.get("moodprint_session"),
         "url": "http://127.0.0.1:5174", "httpOnly": True, "sameSite": "Strict"},
        {"name": "moodprint_csrf", "value": guest.client.headers["X-CSRF-Token"],
         "url": "http://127.0.0.1:5174", "sameSite": "Strict"},
    ]
    await guest.client.aclose()
    return {"cookies": cookies}


@app.post("/__test/purge", include_in_schema=False)
async def purge_expired_guests():
    from sqlalchemy import func, select

    from app.modules.guests.jobs import process_guest_cleanup
    await process_guest_cleanup(app)
    async with app.state.database.sessions() as db:
        count = await db.scalar(select(func.count()).select_from(User).where(
            User.account_kind == "guest", User.guest_expires_at <= func.clock_timestamp()))
    return {"remainingExpired": count}


@app.post("/__test/proposal", include_in_schema=False)
async def seed_guest_proposal(body: dict):
    from sqlalchemy import select
    uid = UUID(body["userId"])
    async with app.state.database.sessions.begin() as db:
        user = await db.get(User, uid)
        assert user and user.account_kind == "guest"
        consents = {c.purpose: c.version for c in (await db.scalars(select(Consent).where(Consent.user_id == uid))).all()}
        proposal = MemoryProposal(user_id=uid, bot_id="may", text="SYNTHETIC-GUEST-MEMORY", data_version=user.data_version,
                                  ai_consent_version=consents["AI"], mem_consent_version=consents["MEM"], expires_at=user.guest_expires_at)
        db.add(proposal)
        await db.flush()
        return {"id": str(proposal.id), "version": proposal.version}


async def seed():
    async with app.state.database.engine.begin() as connection:
        await verify_test_database(connection)
        await connection.execute(text("create schema if not exists moodprint"))
        await connection.execute(text("create schema if not exists extensions"))
        await connection.execute(text("create extension if not exists vector with schema extensions"))
        await connection.run_sync(Base.metadata.drop_all)
        # The feedback CHECK constraints call private functions that must exist first.
        await install_feedback_functions(connection)
        await connection.run_sync(Base.metadata.create_all)
        await install_guest_guards(connection)
        await install_auth_fixture(connection)
    async with app.state.database.sessions.begin() as db:
        # 1-9 back the original journeys; 10-20 are fresh adults for the MVP journeys;
        # 21-36 back the activity, matching-v2 and moderation journeys; 37 is staff;
        # 38-39 are the responsive/accessibility pair; 40-41 the v2-only-goal pair.
        # 44 covers assistant review; 47-48 mood evidence; 51-52 isolate product starters.
        for number in range(1, 53):
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
            if not 7 <= number <= 9:
                db.add(AgeDeclaration(user_id=uid, birth_year=2000, policy_version="self-declared-age-v1"))
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
                db.add(MemoryProposal(user_id=uid, bot_id="guong", text="Đề xuất tổng hợp để bạn chỉnh sửa", data_version=1, ai_consent_version=1, mem_consent_version=1, expires_at=datetime.now(UTC) + timedelta(minutes=15)))
            await db.execute(
                text("insert into auth.sessions(id,user_id) values (:id,:uid)"),
                {"id": provider, "uid": uid},
            )
            if number == 37:
                db.add(StaffRole(user_id=uid, role="moderator", granted_by="e2e-seed"))
            if number == 49:
                db.add(StaffRole(user_id=uid, role="admin", granted_by="e2e-seed"))
    await app.state.database.engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed(), loop_factory=asyncio.SelectorEventLoop)
    uvicorn.run(
        app, host="127.0.0.1", port=8002, loop="app.core.loop:selector_factory", log_config=None
    )
