import os
import re
from contextlib import contextmanager
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.engine import make_url


def require_local_test_database(raw: str):
    """Fail before connecting or resetting anything outside a disposable local DB."""
    try:
        target = make_url(raw)
    except Exception:
        raise RuntimeError("Invalid disposable PostgreSQL test target") from None
    if (
        target.drivername != "postgresql+psycopg"
        or target.host not in ("localhost", "127.0.0.1", "::1")
        or not (target.database or "").endswith("_test")
        or target.query
    ):
        raise RuntimeError("Tests require a local PostgreSQL database ending _test")
    return target


IDENTITY_SQL = """
    select current_database() as database, current_user as "user",
           session_user as session_user, pg_get_userbyid(datdba) as owner,
           shobj_description(oid, 'pg_database') as marker
    from pg_database where datname = current_database()
"""


def _run_id():
    value = os.environ.get("MOODPRINT_TEST_RUN_ID", "")
    if not re.fullmatch(r"[0-9a-f]{32}", value):
        raise RuntimeError("Destructive tests require MOODPRINT_TEST_RUN_ID from provisioning")
    return value


def _verify_identity(identity):
    if os.environ.get("APP_ENV") != "test":
        raise RuntimeError("Destructive setup requires APP_ENV=test")
    run_id = _run_id()
    owner = f"moodprint_test_{run_id}"
    if (
        not re.fullmatch(rf"moodprint_{run_id}(?:_[0-9a-f]{{12}})?_test", identity["database"])
        or identity["user"] != owner
        or identity["session_user"] != owner
        or identity["owner"] != owner
        or identity["marker"] != f"moodprint-disposable-test:{run_id}"
    ):
        raise RuntimeError(
            "Refusing destructive setup: database is not owned by this disposable run"
        )


async def verify_test_database(connection):
    """Verify a SQLAlchemy async connection before dropping tables or schemas."""
    require_local_test_database(connection.engine.url.render_as_string(hide_password=False))
    raw = await connection.get_raw_connection()
    if raw.driver_connection.info.hostaddr not in ("127.0.0.1", "::1"):
        raise RuntimeError("Destructive tests require an actual loopback PostgreSQL peer")
    result = await connection.execute(text(IDENTITY_SQL))
    _verify_identity(result.mappings().one())


def verify_test_database_sync(connection):
    """Verify a psycopg connection before changing a disposable database."""
    if connection.info.host not in (
        "localhost",
        "127.0.0.1",
        "::1",
    ) or connection.info.hostaddr not in ("127.0.0.1", "::1"):
        raise RuntimeError("Destructive tests require a loopback PostgreSQL connection")
    row = connection.execute(IDENTITY_SQL).fetchone()
    keys = ("database", "user", "session_user", "owner", "marker")
    _verify_identity(dict(zip(keys, row, strict=True)))


@contextmanager
def owned_scratch_database(raw=None):
    """Create a unique sibling; remove only that sibling after ownership recheck.

    CREATE DATABASE deliberately has no pre-delete or IF NOT EXISTS. Collision
    fails safely; cleanup runs only after this invocation successfully creates it.
    """
    import psycopg
    from psycopg import sql

    target = require_local_test_database(raw or os.environ.get("TEST_DATABASE_URL", ""))
    dsn = target.set(drivername="postgresql").render_as_string(hide_password=False)
    database = f"moodprint_{_run_id()}_{uuid4().hex[:12]}_test"
    scratch = target.set(database=database)
    scratch_dsn = scratch.set(drivername="postgresql").render_as_string(hide_password=False)
    with psycopg.connect(dsn, autocommit=True) as admin:
        verify_test_database_sync(admin)
        admin.execute(
            sql.SQL("CREATE DATABASE {} OWNER {}").format(
                sql.Identifier(database), sql.Identifier(target.username)
            )
        )
        # Do not clean up if marking failed: an unmarked database must always be
        # left for explicit inspection, never treated as safely owned by a reset.
        admin.execute(
            sql.SQL("COMMENT ON DATABASE {} IS {}").format(
                sql.Identifier(database), sql.Literal(f"moodprint-disposable-test:{_run_id()}")
            )
        )
        try:
            with psycopg.connect(scratch_dsn) as check:
                verify_test_database_sync(check)
            yield scratch
        finally:
            with psycopg.connect(scratch_dsn) as check:
                verify_test_database_sync(check)
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(database)))
