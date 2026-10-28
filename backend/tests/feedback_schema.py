"""Fixture DDL shared with Alembic: the private feedback validators the CHECK constraints call.

``Base.metadata.create_all`` cannot create the SQL functions the feedback CHECK constraints
reference, so every disposable database built from metadata installs them from the reviewed 0018
migration itself (same SQL, same grants) before the tables are created.
"""

import importlib.util
from pathlib import Path

_PATH = Path(__file__).resolve().parents[1] / "alembic/versions/0018_app_feedback.py"
_SPEC = importlib.util.spec_from_file_location("migration_0018", _PATH)
MIGRATION = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(MIGRATION)
FUNCTION_STATEMENTS: tuple[str, ...] = tuple(MIGRATION.function_statements())


async def install_feedback_functions(connection) -> None:
    for statement in FUNCTION_STATEMENTS:
        await connection.exec_driver_sql(statement)
