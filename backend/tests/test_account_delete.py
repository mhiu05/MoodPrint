from uuid import uuid4

import httpx
import pytest
from app.infrastructure.auth_admin import AuthAdmin
from moodprint_shared.testing.auth import make_auth_context


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
