from uuid import uuid4

import httpx
import pytest
from app.infrastructure.auth_admin import AuthAdmin
from safevoice_shared.testing.auth import make_auth_context


async def test_auth_delete_error_hides_body_and_can_be_retried(settings):
    auth = make_auth_context(uuid4())
    responses = iter([httpx.Response(500, text="sensitive private data"), httpx.Response(200)])
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda request: next(responses))
    ) as client:
        admin = AuthAdmin(settings, client)
        with pytest.raises(Exception) as error:
            await admin.delete_user(auth)
        assert "sensitive private data" not in str(error.value)
        await admin.delete_user(auth)


class DeletingSession:
    """Database boundary double while local Supabase is unavailable."""

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    def begin(self):
        return self

    async def execute(self, *args):
        return None

    async def scalar(self, *args):
        from datetime import UTC, datetime

        return datetime(2026, 11, 7, tzinfo=UTC)


async def test_user_uow_rejects_account_with_persisted_deletion_flag(monkeypatch):
    from app.core.errors import ApiError
    from app.core.uow import user_uow

    monkeypatch.setattr("app.core.uow.AsyncSession", lambda *args, **kwargs: DeletingSession())
    with pytest.raises(ApiError) as error:
        async with user_uow(None, make_auth_context(uuid4())):
            pytest.fail("Deleting accounts cannot enter a normal user transaction")
    assert error.value.code == "account_deleting"
    assert error.value.status_code == 409


async def test_cleanup_scope_is_owner_and_task_scoped_and_resets_on_error(monkeypatch):
    import asyncio

    from app.core.errors import ApiError
    from app.core.uow import account_deletion_scope, user_uow

    monkeypatch.setattr("app.core.uow.AsyncSession", lambda *args, **kwargs: DeletingSession())
    owner, peer = make_auth_context(uuid4()), make_auth_context(uuid4())

    async def transaction(auth):
        async with user_uow(None, auth):
            return "entered"

    with pytest.raises(RuntimeError, match="cleanup failed"):
        with account_deletion_scope(owner):
            assert await transaction(owner) == "entered"
            with pytest.raises(ApiError):
                await asyncio.create_task(transaction(owner))
            with pytest.raises(ApiError):
                await transaction(peer)
            raise RuntimeError("cleanup failed")
    with pytest.raises(ApiError):
        await transaction(owner)
