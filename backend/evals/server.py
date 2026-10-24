"""Loopback-only live AI server for the two explicitly configured synthetic actors."""

import asyncio
import contextvars
import json
import logging
from dataclasses import asdict
from pathlib import Path
from uuid import UUID

import uvicorn
from dotenv import dotenv_values
from sqlalchemy import select

from app.ai.provider import SdkProvider
from app.ai.usage import UsageEvent
from app.core.config import Settings
from app.infrastructure.database.models import User
from app.main import create_app

values = dotenv_values(".env")
identities = [UUID(values[f"MOODPRINT_TEST_{actor}_USER_ID"] or "") for actor in ("A", "B")]
if len(set(identities)) != 2:
    raise ValueError("Configure two distinct authorized synthetic actors")
settings = Settings(app_env="development", ai_enabled=False, ai_local_test_user_ids=identities,
                    stt_enabled=True, stt_model="gpt-transcribe", frontend_origin="http://127.0.0.1:5177")
app = create_app(settings)
observation: contextvars.ContextVar[dict | None] = contextvars.ContextVar("synthetic_live_run", default=None)
writer = asyncio.Lock()
artifact = Path("../docs/plans/validation-artifacts/live-ai/http-usage.jsonl")


async def observe(event: UsageEvent):
    row = {**(observation.get() or {}), **asdict(event), "model": settings.openai_model}
    async with writer:
        def append():
            artifact.parent.mkdir(parents=True, exist_ok=True)
            with artifact.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(row) + "\n")
        await asyncio.to_thread(append)


class ObservedProvider(SdkProvider):
    async def run(self, **kwargs):
        context = kwargs.get("context")
        token = observation.set({"run_id": str(context.id), "bot_id": kwargs["bot_id"]})
        try:
            return await super().run(**kwargs)
        finally:
            observation.reset(token)


app.state.ai.provider = ObservedProvider(settings, usage_observer=observe)


async def resolve_synthetic_actors():
    # Fixture IDs identify Supabase Auth subjects. Application actors have their
    # own IDs; authorize only the existing, normally authenticated mappings.
    async with app.state.database.require()() as db:
        users = (await db.scalars(select(User.id).where(User.auth_subject.in_(identities)))).all()
    if len(set(users)) != 2:
        raise ValueError("Both synthetic accounts must already exist in the application")
    settings.ai_local_test_user_ids = list(users)


if __name__ == "__main__":
    logging.disable(logging.CRITICAL)
    asyncio.run(resolve_synthetic_actors(), loop_factory=asyncio.SelectorEventLoop)
    uvicorn.run(app, host="127.0.0.1", port=8004, loop="app.core.loop:selector_factory", log_config=None, access_log=False)
