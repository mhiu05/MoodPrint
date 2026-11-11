"""Private ingestion notes are unavailable to runtime and client database roles."""

from __future__ import annotations

import asyncio

import pytest
from safevoice_agent.knowledge.ingest.runtime import engine_for
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import create_async_engine

from .kb_env import api_database_url, load_test_env

pytestmark = pytest.mark.integration


@pytest.mark.parametrize("role", [None, "authenticated", "anon"])
@pytest.mark.parametrize(
    "statement",
    [
        "select licence_note from knowledge.source_confidential",
        "insert into knowledge.source_confidential values ('mp-privilege-missing', 'denied')",
        "update knowledge.source_confidential set licence_note = 'denied'",
        "delete from knowledge.source_confidential",
    ],
    ids=["read", "insert", "update", "delete"],
)
def test_runtime_and_client_roles_cannot_access_ingestion_notes(
    role: str | None, statement: str
) -> None:
    async def once() -> None:
        load_test_env()
        # Runtime cannot SET ROLE anon. Exercise anon grants using the admin test
        # session as role switcher, without granting runtime any new membership.
        engine = (
            engine_for("test-env")
            if role == "anon"
            else create_async_engine(api_database_url(), hide_parameters=True)
        )
        try:
            async with engine.connect() as conn, conn.begin():
                if role is not None:
                    # Both role names are fixed test parameters, never caller input.
                    await conn.execute(text(f"set local role {role}"))
                with pytest.raises(DBAPIError) as failure:
                    await conn.execute(text(statement))
                assert getattr(failure.value.orig, "sqlstate", None) == "42501"
        finally:
            await engine.dispose()

    asyncio.run(once())


def test_admin_ingestion_can_maintain_private_notes_without_runtime_grants() -> None:
    load_test_env()

    async def once() -> None:
        engine = engine_for("test-env")
        try:
            async with engine.connect() as conn:
                transaction = await conn.begin()
                try:
                    await conn.execute(
                        text(
                            "insert into knowledge.sources (source_id, kind, publisher, title, "
                            "language, country_scope, authority_tier, licence_class, verified_on) "
                            "values ('mp-admin-privilege', 'authored', 'SafeVoice', 'Privilege test', "
                            "'vi', array['VN'], 4, 'authored', '2026-11-09')"
                        )
                    )
                    await conn.execute(
                        text(
                            "insert into knowledge.source_confidential values "
                            "('mp-admin-privilege', 'admin note')"
                        )
                    )
                    await conn.execute(
                        text(
                            "update knowledge.source_confidential set licence_note = 'revised' "
                            "where source_id = 'mp-admin-privilege'"
                        )
                    )
                    assert (
                        await conn.execute(
                            text(
                                "select licence_note from knowledge.source_confidential "
                                "where source_id = 'mp-admin-privilege'"
                            )
                        )
                    ).scalar_one() == "revised"
                    await conn.execute(
                        text(
                            "delete from knowledge.source_confidential "
                            "where source_id = 'mp-admin-privilege'"
                        )
                    )
                    assert (
                        await conn.execute(
                            text(
                                "select count(*) from knowledge.source_confidential "
                                "where source_id = 'mp-admin-privilege'"
                            )
                        )
                    ).scalar_one() == 0
                finally:
                    await transaction.rollback()
        finally:
            await engine.dispose()

    asyncio.run(once())
