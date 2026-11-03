import importlib.util
from pathlib import Path

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import text


@pytest.mark.postgres
async def test_search_migrations_upgrade_without_public_grants_and_refuse_destructive_downgrade(clients):
    app, _ = clients
    revisions = ["0025_search_citations", "0026_search_usage", "0027_maps_jobs"]
    modules = []
    for revision in revisions:
        path = Path(__file__).parents[1] / "alembic/versions" / (revision + ".py")
        spec = importlib.util.spec_from_file_location(revision, path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        modules.append(module)
    async with app.state.database.engine.begin() as conn:
        await conn.execute(text("drop table moodprint.ai_maps_searches"))
        await conn.execute(text("drop table moodprint.ai_search_usage"))
        await conn.execute(text("alter table moodprint.ai_messages drop constraint ck_ai_messages_citations"))
        await conn.execute(text("alter table moodprint.ai_messages drop column citations"))
        await conn.execute(text("alter table moodprint.ai_messages drop column source_backed"))
        def migrate(sync):
            with Operations.context(MigrationContext.configure(sync)):
                for module in modules:
                    module.upgrade()
                    with pytest.raises(RuntimeError, match="Forward-only"):
                        module.downgrade()
        await conn.run_sync(migrate)
        for table in ("ai_search_usage", "ai_maps_searches"):
            assert await conn.scalar(text("select relrowsecurity from pg_class where oid=cast(:table as regclass)"), {"table": "moodprint."+table})
            assert not await conn.scalar(text("select has_table_privilege('public',cast(:table as regclass),'SELECT')"), {"table": "moodprint."+table})
        columns = set((await conn.execute(text("select column_name from information_schema.columns where table_schema='moodprint' and table_name='ai_messages'"))).scalars())
        assert {"citations", "source_backed"} <= columns
