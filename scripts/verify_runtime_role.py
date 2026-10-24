"""Disposable local role-separation drill. Every fixture/grant/role is rolled back."""

import asyncio
import json
import os
import sys
from pathlib import Path
from uuid import uuid4

from sqlalchemy import insert, select, text, update
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import create_async_engine

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from app.infrastructure.database.models import AgeDeclaration, User  # noqa: E402


async def drill():
    raw = os.environ["TEST_DATABASE_URL"]
    target = make_url(raw)
    if target.host not in ("localhost", "127.0.0.1", "::1") or not (target.database or "").endswith(
        "_test"
    ):
        raise RuntimeError("Requires a disposable local *_test database")
    role = "moodprint_role_check_" + uuid4().hex
    identity = uuid4()
    result = {"scope": "local disposable database only", "remoteWrites": False}
    engine = create_async_engine(
        raw, hide_parameters=True, connect_args={"prepare_threshold": None}
    )
    try:
        async with engine.connect() as db:
            transaction = await db.begin()
            await db.execute(text("CREATE SCHEMA IF NOT EXISTS auth"))
            await db.execute(
                text(
                    "CREATE TABLE IF NOT EXISTS auth.sessions (id uuid PRIMARY KEY, user_id uuid NOT NULL)"
                )
            )
            helper = (ROOT / "backend/app/infrastructure/database/provider_session.sql").read_text(
                encoding="utf-8"
            )
            await db.execute(
                text(helper.replace("CREATE FUNCTION", "CREATE OR REPLACE FUNCTION", 1))
            )
            template = (
                (ROOT / "deploy/examples/runtime-role.sql")
                .read_text(encoding="utf-8")
                .replace("moodprint_runtime", role)
            )
            # Trusted, repository-owned SQL; no user/model values are interpolated.
            for statement in template.split(";"):
                if statement.strip():
                    await db.execute(text(statement))
            await db.execute(text(f"SET LOCAL ROLE {role}"))
            await db.execute(
                insert(User).values(id=identity, auth_subject=identity, age_band="adult")
            )
            await db.execute(update(User).where(User.id == identity).values(data_version=2))
            await db.execute(
                insert(AgeDeclaration).values(
                    user_id=identity, birth_year=2000, policy_version="self-declared-age-v1"
                )
            )
            result["ageDeclarationDml"] = (
                await db.scalar(
                    select(AgeDeclaration.birth_year).where(AgeDeclaration.user_id == identity)
                )
                == 2000
            )
            result["domainDml"] = (
                await db.scalar(select(User.data_version).where(User.id == identity)) == 2
            )
            result["privateAuthBridgeCallable"] = await db.scalar(
                text("select moodprint.is_provider_session_active(:sid,:uid)=false"),
                {"sid": uuid4(), "uid": identity},
            )
            for schema in ("moodprint", "public"):
                savepoint = await db.begin_nested()
                try:
                    await db.execute(text(f"CREATE TABLE {schema}.{role} (id integer)"))
                    result[f"{schema}DdlDenied"] = False
                except DBAPIError as error:
                    result[f"{schema}DdlDenied"] = getattr(error.orig, "sqlstate", None) == "42501"
                finally:
                    await savepoint.rollback()
            await transaction.rollback()
            result["fixtureRoleRemoved"] = not await db.scalar(
                text("SELECT EXISTS(SELECT 1 FROM pg_roles WHERE rolname=:role)"), {"role": role}
            )
    finally:
        await engine.dispose()
    print(json.dumps(result, indent=2))
    if not all(
        result.get(key)
        for key in (
            "domainDml",
            "ageDeclarationDml",
            "privateAuthBridgeCallable",
            "moodprintDdlDenied",
            "publicDdlDenied",
            "fixtureRoleRemoved",
        )
    ):
        raise RuntimeError("Role separation drill failed")


if __name__ == "__main__":
    try:
        asyncio.run(drill(), loop_factory=asyncio.SelectorEventLoop)
    except Exception as error:
        print(json.dumps({"status": "failed", "errorType": type(error).__name__}))
        sys.exit(1)
