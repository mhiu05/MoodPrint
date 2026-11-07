import pytest
from agents.extensions.memory import SQLAlchemySession
from sqlalchemy import inspect
from sqlalchemy.dialects import postgresql

pytestmark = pytest.mark.integration


async def test_sdk_tables_match_sdk_metadata(db_engine):
    session = SQLAlchemySession("synthetic-schema-check", engine=db_engine, create_tables=False)
    dialect = postgresql.dialect()
    async with db_engine.connect() as connection:
        for table in (session._sessions, session._messages):
            actual = await connection.run_sync(
                lambda sync, name=table.name: inspect(sync).get_columns(name, schema="agent_store")
            )
            expected = {
                column.name: (column.type.compile(dialect=dialect), column.nullable)
                for column in table.columns
            }
            observed = {
                column["name"]: (column["type"].compile(dialect=dialect), column["nullable"])
                for column in actual
            }
            assert observed == expected, table.name
