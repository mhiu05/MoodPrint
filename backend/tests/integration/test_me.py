import asyncio

import pytest
from app.modules.profiles.schemas import ProfilePatch
from app.modules.profiles.service import ProfileService

pytestmark = pytest.mark.integration


async def test_first_get_idempotent_and_concurrent(db_engine, identities):
    service = ProfileService(db_engine)
    a, b = identities
    results = await asyncio.gather(
        *(service.get(a, {"nickname": "Synthetic An", "age_band": "invalid"}) for _ in range(8))
    )
    assert {p.user_id for p in results} == {a.user_id}
    assert {p.nickname for p in results} == {"Synthetic An"}
    assert all(p.age_band is None for p in results)
    await service.patch(a, ProfilePatch(nickname="Synthetic Mai", age_band="11-13"))
    assert (await service.get(a)).nickname == "Synthetic Mai"
    assert (await service.get(b)).nickname == "Bạn"
