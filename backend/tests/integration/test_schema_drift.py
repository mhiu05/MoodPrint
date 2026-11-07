"""Catch an added, removed, mistyped, or nullable ORM/database column."""

import importlib

import pytest
from app.core.db import Base
from sqlalchemy import inspect
from sqlalchemy.dialects import postgresql

pytestmark = pytest.mark.integration


async def test_models_match_database(db_engine):
    for name in ("profiles", "conversations", "memory"):
        importlib.import_module(f"app.modules.{name}.models")
    expected_names = {
        "profiles",
        "audit_events",
        "conversations",
        "messages",
        "agent_runs",
        "tool_approvals",
        "memory_candidates",
        "user_memories",
    }
    models = {table.name: table for table in Base.metadata.tables.values() if table.schema == "app"}
    assert set(models) == expected_names

    async with db_engine.connect() as connection:
        live = await connection.run_sync(
            lambda conn: {
                name: inspect(conn).get_columns(name, schema="app")
                for name in inspect(conn).get_table_names(schema="app")
            }
        )
    assert set(live) == set(models)
    dialect = postgresql.dialect()
    for name, table in models.items():
        actual = {
            column["name"]: (str(column["type"].compile(dialect=dialect)), column["nullable"])
            for column in live[name]
        }
        expected = {
            column.name: (str(column.type.compile(dialect=dialect)), column.nullable)
            for column in table.columns
        }
        assert actual == expected, name
