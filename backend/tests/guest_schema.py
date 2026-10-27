"""Fixture DDL shared with Alembic so synthetic databases enforce the same guest guards.

ORM ``create_all`` cannot prove triggers, so every disposable database that builds its schema from
metadata installs the reviewed 0016 guard functions and triggers from the migration itself.
"""

import importlib.util
from pathlib import Path

_MIGRATION = Path(__file__).resolve().parents[1] / "alembic/versions/0016_guest_foundation.py"


def _load():
    spec = importlib.util.spec_from_file_location("migration_0016_guest_foundation", _MIGRATION)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


MIGRATION = _load()
GUARD_STATEMENTS = (
    MIGRATION.USER_GUARD_SQL,
    MIGRATION.USER_GUARD_TRIGGER_SQL,
    MIGRATION.SESSION_GUARD_SQL,
    MIGRATION.SESSION_GUARD_TRIGGER_SQL,
)


async def install_guest_guards(connection) -> None:
    """Install the lifecycle immutability and session-cap guards on an async connection."""
    for statement in GUARD_STATEMENTS:
        await connection.exec_driver_sql(statement)
