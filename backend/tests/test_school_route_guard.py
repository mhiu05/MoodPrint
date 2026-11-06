"""Every API route is classified, and the school profile hides the frozen surface."""

import httpx
import pytest

from app.core.config import Settings
from app.core.profile import route_disposition
from app.main import create_app


def iter_paths(routes, prefix=""):
    for route in routes:
        if type(route).__name__ == "_IncludedRouter":
            yield from iter_paths(
                route.original_router.routes, prefix + route.include_context.prefix
            )
            continue
        path = getattr(route, "path", None)
        if isinstance(path, str):
            yield prefix + path


def test_every_api_route_is_classified():
    app = create_app(Settings(_env_file=None))
    api = [path for path in iter_paths(app.routes) if path.startswith("/api/v1")]
    assert api
    dispositions = {path: route_disposition(path) for path in api}
    unknown = sorted(path for path, kind in dispositions.items() if kind != "deny" and kind != "keep")
    assert unknown == []
    assert any(kind == "deny" for kind in dispositions.values())
    assert any(kind == "keep" for kind in dispositions.values())


@pytest.mark.asyncio
async def test_school_profile_hides_frozen_routes_and_default_does_not():
    school = create_app(Settings(_env_file=None, app_profile="school_safety"))
    default = create_app(Settings(_env_file=None))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=school), base_url="http://test") as client:
        hidden = await client.get("/api/v1/moods")
        live = await client.get("/api/v1/health/live")
        kept = await client.get("/api/v1/session")
    assert hidden.status_code == 404
    assert hidden.json()["error"]["code"] == "NOT_FOUND"
    assert live.status_code == 200
    assert kept.status_code == 401
    assert kept.json()["error"]["code"] == "AUTH_REQUIRED"
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=default), base_url="http://test") as client:
        visible = await client.get("/api/v1/moods")
        live = await client.get("/api/v1/health/live")
    assert visible.status_code == 401
    assert visible.json()["error"]["code"] == "AUTH_REQUIRED"
    assert live.status_code == 200
