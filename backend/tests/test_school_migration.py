"""troly is a direct-conversation id and is absent from the frozen catalog."""

import pytest

from app.ai.agents import (
    ALL_IDS,
    BOT_CHECK,
    DISPLAY_NAMES,
    FROZEN_IDS,
    MEMORY_IDS,
    is_legacy,
    is_v3,
)
from app.ai.models import CONVERSATION_BOT_CHECK
from app.ai.prompts import RUNTIME_VARIANTS, VERSIONS
from tests.test_database_operations import script


def test_troly_is_addressable_but_not_a_frozen_companion():
    assert ALL_IDS[-1] == "troly"
    assert "troly" not in FROZEN_IDS
    assert "troly" not in MEMORY_IDS
    assert is_v3("troly") is False
    assert is_legacy("troly") is False
    assert DISPLAY_NAMES["troly"] == "Trợ lý"
    assert RUNTIME_VARIANTS["troly"] == "assistant"
    assert VERSIONS["assistant"] == "school-assistant-v1"
    assert "troly" in CONVERSATION_BOT_CHECK
    assert "troly" not in BOT_CHECK


def test_hosted_review_declares_the_conversation_constraint_swap():
    swaps = script("apply_supabase_review").SCHOOL_CONSTRAINT_SWAPS
    assert swaps == (("ai_conversations", "ck_ai_conversations_bot"),)


def test_offline_upgrade_adds_the_profile_and_leaves_proactive_checks():
    sql = script("apply_supabase_review").alembic_export(
        "0029_journal_intelligence:0030_school_profiles"
    )
    assert "CREATE TABLE moodprint.school_profiles" in sql
    assert "ck_school_profiles_age_group" in sql
    assert "ck_school_profiles_terms_pair" in sql
    assert "'troly'" in sql
    assert "ck_ai_conversations_bot" in sql
    assert "ck_ai_proactive_schedules_bot" not in sql
    assert "memory_proposals" not in sql


@pytest.mark.asyncio
async def test_default_catalog_does_not_list_troly():
    import httpx

    from app.main import create_app

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=create_app()), base_url="http://test"
    ) as client:
        bots = (await client.get("/api/v1/bots")).json()
    assert "troly" not in {bot["botId"] for bot in bots}
    assert {bot["botId"] for bot in bots} == {"may", "guong", "nhip", "rure", "caunoi"}
