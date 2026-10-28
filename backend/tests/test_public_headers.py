"""Public shell headers: a strict CSP that only opens to the configured CAPTCHA origin."""

import httpx

from app.core.config import Settings
from app.main import create_app


async def test_public_shell_headers_widen_csp_only_for_the_configured_challenge(tmp_path):
    (tmp_path / "assets").mkdir()
    (tmp_path / "index.html").write_text("<!doctype html><div id=root></div>", encoding="utf-8")

    async def headers(**settings):
        app = create_app(Settings(_env_file=None, static_dir=str(tmp_path), **settings))
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
            return {
                "root": (await c.get("/")).headers,
                "callback": (await c.get("/auth/callback")).headers,
                "api": (await c.get("/api/v1/does-not-exist")).headers,
            }

    plain = await headers()
    policy = plain["root"]["Content-Security-Policy"]
    assert "challenges.cloudflare.com" not in policy
    assert "frame-src" not in policy and "script-src 'self';" in policy

    enabled = await headers(guest_captcha_site_key="public-site-key")
    policy = enabled["root"]["Content-Security-Policy"]
    # Only the CAPTCHA origin is added, and only to the three directives it needs.
    assert "script-src 'self' https://challenges.cloudflare.com;" in policy
    assert "frame-src https://challenges.cloudflare.com;" in policy
    assert "connect-src 'self' https://challenges.cloudflare.com;" in policy
    assert "default-src 'self';" in policy and "frame-ancestors 'none'" in policy
    assert "unsafe-inline" not in policy and "unsafe-eval" not in policy
    assert "Content-Security-Policy" not in enabled["api"]

    # The email-link landing is never indexed or cached, whatever the serving mode.
    for result in (plain, enabled):
        assert result["callback"]["X-Robots-Tag"] == "noindex, nofollow"
        assert result["callback"]["Cache-Control"] == "no-store"
        assert "X-Robots-Tag" not in result["root"]
