"""Sharing and case deletion must acquire the parent lock in the same order."""

import asyncio
from uuid import uuid4

import pytest
from app.modules.incidents.schemas import CaseCreate
from app.modules.incidents.service import IncidentService
from app.modules.sharing.schemas import ShareCreate, ShareSubmit
from app.modules.sharing.service import SharingService
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from backend.tests.integration.conftest import local_value

pytestmark = pytest.mark.integration


async def test_submit_and_case_delete_never_deadlock(db_engine, identities, monkeypatch):
    owner = identities[0]
    school_id = uuid4()
    admin = create_async_engine(local_value("TEST_ADMIN_DATABASE_URL"), hide_parameters=True)
    async with admin.begin() as connection:
        await connection.execute(
            text(
                "insert into app.schools(id,name,verification_status) values(:id,'Synthetic concurrency school','verified')"
            ),
            {"id": school_id},
        )
    service = SharingService(db_engine, None)
    cases = IncidentService(db_engine)
    try:
        case = await cases.create(
            owner, CaseCreate(id=uuid4(), title="Synthetic", summary="Synthetic")
        )
        draft = await service.create(
            owner,
            ShareCreate(
                id=uuid4(), case_id=case.id, school_id=school_id, shared_fields=["summary"]
            ),
        )
        preview = await service.preview(owner, draft.id)
        locked = asyncio.Event()
        resume = asyncio.Event()
        original_get = service._get

        async def paused_get(*args, **kwargs):
            result = await original_get(*args, **kwargs)
            if kwargs.get("lock"):
                locked.set()
                await resume.wait()
            return result

        monkeypatch.setattr(service, "_get", paused_get)
        submit = asyncio.create_task(
            service.submit(
                owner,
                draft.id,
                ShareSubmit(
                    confirmed=True, confirmation_version="v1", preview_hash=preview.preview_hash
                ),
            )
        )
        await asyncio.wait_for(locked.wait(), 5)
        deleting = asyncio.create_task(cases.delete(owner, case.id))
        # Give the second physical connection a chance to obtain the parent lock.
        await asyncio.sleep(0.1)
        resume.set()
        results = await asyncio.wait_for(
            asyncio.gather(submit, deleting, return_exceptions=True), 10
        )
        assert not any(isinstance(result, BaseException) for result in results), [
            type(result).__name__ for result in results
        ]
        assert (await service.get(owner, draft.id)).status == "withdrawn"
    finally:
        async with admin.begin() as connection:
            await connection.execute(
                text("delete from app.case_shares where school_id=:id"), {"id": school_id}
            )
            await connection.execute(
                text("delete from app.schools where id=:id"), {"id": school_id}
            )
        await admin.dispose()
