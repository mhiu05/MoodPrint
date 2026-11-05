from uuid import uuid4

import httpx

from app.core.config import Settings
from app.main import create_app


async def test_drain_refuses_new_turns_but_preserves_liveness_and_cancel_routes():
    app = create_app(Settings(_env_file=None))
    app.state.ai.begin_drain()
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(f"/api/v1/ai/conversations/{uuid4()}/messages", json={})
        assert response.status_code == 503
        assert response.json()["error"]["code"] == "AI_DRAINING"
        assert int(response.headers["Retry-After"]) > 0
        assert (await client.get("/api/v1/health/live")).status_code == 200
        assert (await client.get("/api/v1/health/ready")).json()["error"]["code"] == "AI_DRAINING"
        assert (await client.post(f"/api/v1/ai/runs/{uuid4()}/cancel")).status_code == 401
    await app.state.ai.close()


def test_shutdown_bounds_cover_the_longest_group_turn():
    from app.core.capacity import shutdown_bounds

    assert shutdown_bounds(60) == {"server_grace": 130, "container_grace": 140}
    assert shutdown_bounds(120)["container_grace"] <= 270
