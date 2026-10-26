"""The additive migration keeps legacy history but never backfills eligibility."""

import importlib.util
from pathlib import Path

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import select, text

from app.ai.models import AiTurn
from tests.fakes import make_test_model
from tests.test_chat_persistence import enable, key
from tests.test_context_privacy import ECHO, restart, turn

MIGRATION_PATH = Path(__file__).resolve().parents[1] / "alembic/versions/0015_context_privacy_context_privacy.py"


@pytest.mark.postgres
async def test_expand_migration_preserves_legacy_text_and_security_without_backfill(clients):
    app, actors = clients
    client, _ = actors[0]
    await enable(client)
    app.state.ai.model_override = make_test_model("ready")
    created = await client.post("/api/v1/ai/conversations", json={"botId": "may"}, headers=key())
    assert created.status_code == 201, created.text
    url = f"/api/v1/ai/conversations/{created.json()['conversationId']}"
    old = await turn(app, client, url, "Legacy synthetic input", make_test_model(ECHO))
    spec = importlib.util.spec_from_file_location("privacy_migration", MIGRATION_PATH)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)

    def migrate(connection):
        with Operations.context(MigrationContext.configure(connection)):
            migration.upgrade()

    # `clients` only uses a guarded disposable local *_test DB, never DATABASE_URL.
    async with app.state.database.engine.begin() as connection:
        acl = "select relrowsecurity, relacl::text from pg_class where oid='moodprint.ai_turns'::regclass"
        before_acl = (await connection.execute(text(acl))).one()
        await connection.execute(text("alter table moodprint.ai_turns drop column context_policy"))
        await connection.run_sync(migrate)
        assert (await connection.execute(text(acl))).one() == before_acl
        assert (
            await connection.scalar(
                text(
                    "select is_nullable from information_schema.columns where table_schema='moodprint' "
                    "and table_name='ai_turns' and column_name='context_policy'"
                )
            )
            == "YES"
        )
    async with app.state.database.sessions() as db:
        assert await db.scalar(select(AiTurn.context_policy).where(AiTurn.run_id == old.id)) is None
    assert ECHO in (await client.get(url)).text
    await restart(app)
    model = make_test_model("Safe new context")
    await turn(app, client, url, "Continue", model)
    assert all(ECHO not in str(call["input"]) for call in model.calls)
    assert ECHO in (await client.get(url + "/export")).text
