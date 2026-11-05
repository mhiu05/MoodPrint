"""Auth scale contracts: no real provider, email, credentials or database required."""

from types import SimpleNamespace

import httpx
import pytest
from starlette.requests import Request

from app.core.config import Settings
from app.core.errors import DomainError
from app.core.limits import AttemptLimiter
from app.modules.auth.provider import SupabaseAuth


def adapter(transport, shared=None):
    settings = Settings(_env_file=None, supabase_url="https://auth.invalid",
                        supabase_publishable_key="synthetic", auth_captcha_enabled=True)
    app = SimpleNamespace(state=SimpleNamespace(settings=settings, auth_transport=transport,
                                                auth_http=shared))
    return SupabaseAuth(Request({"type": "http", "app": app, "headers": []}))


async def test_provider_429_honors_retry_after_without_leaking_response():
    auth = adapter(httpx.MockTransport(lambda r: httpx.Response(
        429, headers={"Retry-After": "123"}, json={"error": "secret-canary"})))
    with pytest.raises(DomainError) as caught:
        await auth.sign_up("synthetic@example.invalid", "synthetic-password", captcha_token="ok")
    assert caught.value.retry_after == 123
    assert caught.value.code == "AUTH_RATE_LIMITED"
    assert "secret-canary" not in caught.value.message


@pytest.mark.parametrize("header,expected", [("", 60), ("invalid", 60), ("0", 1),
    ("99999999", 86400), ("Thu, 05 Nov 2026 09:01:02 GMT", 62),
    ("Thu, 05 Nov 2026 08:59:00 GMT", 1)])
def test_retry_after_date_invalid_and_extreme_values_are_finite(monkeypatch, header, expected):
    from datetime import UTC, datetime

    from app.modules.auth import provider

    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 11, 5, 9, 0, tzinfo=UTC)

    monkeypatch.setattr(provider, "datetime", Clock)
    assert provider._retry_after(httpx.Response(429, headers={"Retry-After": header})) == expected


@pytest.mark.parametrize("method", ["resend_confirmation", "request_recovery"])
@pytest.mark.parametrize("status,code", [(400, "email_provider_disabled"),
    (422, "email_address_not_authorized"), (404, "unknown_failure"), (400, "validation_failed")])
async def test_mail_request_does_not_report_success_for_unrecognized_provider_rejection(method, status, code):
    auth = adapter(httpx.MockTransport(lambda r: httpx.Response(status, json={
        "error_code": code, "message": "secret-canary"})))
    with pytest.raises(DomainError) as caught:
        await getattr(auth, method)("synthetic@example.invalid", captcha_token="ok")
    assert caught.value.code == "AUTH_UNAVAILABLE"
    assert "secret-canary" not in caught.value.message


@pytest.mark.parametrize("method", ["resend_confirmation", "request_recovery"])
async def test_mail_unknown_identity_remains_indistinguishable_from_acceptance(method):
    for status, body in [(200, {}), (404, {"error_code": "user_not_found"})]:
        auth = adapter(httpx.MockTransport(lambda r, s=status, b=body: httpx.Response(s, json=b)))
        assert await getattr(auth, method)("synthetic@example.invalid", captcha_token="ok") is None


@pytest.mark.parametrize("path", ["sign_up", "resend_confirmation", "request_recovery"])
async def test_timeout_has_unknown_side_effect_outcome_and_is_never_retried(path):
    calls = []

    def timeout(request):
        calls.append(request)
        raise httpx.ReadTimeout("secret-canary", request=request)

    auth = adapter(httpx.MockTransport(timeout))
    args = ["synthetic@example.invalid"] + (["synthetic-password"] if path == "sign_up" else [])
    with pytest.raises(DomainError) as caught:
        await getattr(auth, path)(*args, captcha_token="ok")
    assert len(calls) == 1
    assert caught.value.code == "AUTH_OUTCOME_UNKNOWN"
    assert caught.value.retryable is False
    assert "secret-canary" not in caught.value.message


async def test_shared_client_remains_open_and_bearer_is_never_shared():
    calls = []
    transport = httpx.MockTransport(lambda request: calls.append(request) or httpx.Response(200))
    async with httpx.AsyncClient(transport=transport, follow_redirects=False) as client:
        auth = adapter(transport, client)
        auth.client = lambda: pytest.fail("Must reuse the lifespan-owned client")
        await auth._send("GET", "/user", headers={"Authorization": "Bearer synthetic-one"})
        await auth._send("POST", "/recover", json={"email": "synthetic@example.invalid"})
        assert not client.is_closed
        assert "Authorization" not in calls[1].headers
        assert "Authorization" not in client.headers


async def test_auth_pool_local_tcp_reuse_capacity_and_cancellation():
    import asyncio
    import json
    import time

    from app.modules.auth.provider import auth_http_client

    active = peak = connections = 0
    closed = asyncio.Event()

    async def serve(reader, writer):
        nonlocal active, peak, connections
        active += 1
        connections += 1
        peak = max(peak, active)
        try:
            while True:
                await reader.readuntil(b"\r\n\r\n")
                await asyncio.sleep(0.02)
                writer.write(b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\n{}")
                await writer.drain()
        except (asyncio.IncompleteReadError, ConnectionError):
            pass
        finally:
            writer.close()
            await writer.wait_closed()
            active -= 1
            if active == 0:
                closed.set()

    server = await asyncio.start_server(serve, "127.0.0.1", 0)
    url = f"http://127.0.0.1:{server.sockets[0].getsockname()[1]}/user"
    warm = []
    try:
        async with auth_http_client() as client:
            started = time.monotonic()
            assert (await client.get(url)).status_code == 200
            cold_ms = (time.monotonic() - started) * 1000
            for _ in range(20):
                started = time.monotonic()
                assert (await client.get(url)).status_code == 200
                warm.append((time.monotonic() - started) * 1000)
            assert connections == 1  # Twenty warm exchanges reuse the initial TCP socket.
            responses = await asyncio.gather(*(client.get(url) for _ in range(80)))
            assert all(r.status_code == 200 for r in responses)
            assert peak <= 64
            pending = [asyncio.create_task(client.get(url)) for _ in range(80)]
            await asyncio.sleep(0.005)
            for task in pending:
                task.cancel()
            await asyncio.gather(*pending, return_exceptions=True)
        await asyncio.wait_for(closed.wait(), timeout=3)
        assert active == 0
        print(json.dumps({"scope": "local HTTP/1.1 loopback, 20ms fake upstream; no TLS/cloud",
            "cold_first_ms": round(cold_ms, 3), "warm_samples": len(warm),
            "warm_p95_ms": round(sorted(warm)[18], 3), "peak_tcp_connections": peak,
            "burst_requests": 80, "cancelled_requests": 80, "open_after_close": active}))
    finally:
        server.close()
        await server.wait_closed()


async def test_lifespan_auth_pool_never_replays_provider_cookies():
    from app.modules.auth.provider import auth_http_client

    seen = []

    def provider(request):
        seen.append(request)
        return httpx.Response(200, headers={"Set-Cookie": "provider_secret=synthetic; Path=/"})

    async with auth_http_client(httpx.MockTransport(provider)) as client:
        await client.get("https://auth.invalid/auth/v1/user")
        await client.get("https://auth.invalid/auth/v1/user")
    assert "Cookie" not in seen[1].headers


def test_local_limit_provides_finite_retry_after(monkeypatch):
    monkeypatch.setattr("app.core.limits.time.monotonic", lambda: 100.0)
    limit = AttemptLimiter(1, 60)
    limit.check("synthetic")
    with pytest.raises(DomainError) as caught:
        limit.check("synthetic")
    assert caught.value.retry_after == 60


async def test_candidate_nat_policy_accepts_100_distinct_signups_and_preserves_email_cooldown():
    import asyncio

    from app.main import create_app
    from app.modules.auth.routes import EMAIL_LIMIT

    EMAIL_LIMIT.attempts.clear()
    settings = Settings(_env_file=None, supabase_url="https://auth.invalid",
                        supabase_publishable_key="synthetic", auth_captcha_enabled=True,
                        auth_nat_policy_enabled=True)
    app = create_app(settings)
    calls = []
    app.state.auth_transport = httpx.MockTransport(
        lambda r: calls.append(r) or httpx.Response(200, json={}))
    body = {"password": "synthetic-password", "captchaToken": "synthetic",
            "eligibility": {"birthYear": 2000, "confirmedMinimumAge": True,
                            "confirmedAdultAge": True, "expectedVersion": 0,
                            "policyVersion": "self-declared-age-v2-18plus"}}
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        responses = await asyncio.gather(*[client.post("/api/v1/auth/signup", json={
            **body, "email": f"synthetic-{i}@example.com"}) for i in range(100)])
        assert [r.status_code for r in responses] == [202] * 100
        assert len(calls) == 100
        for _ in range(2):
            assert (await client.post("/api/v1/auth/signup", json={**body, "email": "synthetic-0@example.com"})).status_code == 202
        denied = await client.post("/api/v1/auth/signup", json={**body, "email": "synthetic-0@example.com"})
        assert denied.status_code == 429 and int(denied.headers["Retry-After"]) > 0
    await app.state.ai.close()


def test_candidate_policy_requires_captcha():
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        Settings(_env_file=None, auth_nat_policy_enabled=True, auth_captcha_enabled=False)


def test_candidate_ip_abuse_ceiling_and_action_isolation():
    from app.modules.auth.admission import AuthAdmission

    policy = AuthAdmission()
    for _ in range(150):
        policy.check("signup", "ip:synthetic")
    with pytest.raises(DomainError):
        policy.check("signup", "ip:synthetic")
    # A signup burst cannot consume the independent login IP bucket.
    policy.check("login", "ip:synthetic")


def test_untrusted_forwarded_headers_never_supply_auth_client_key():
    from app.modules.auth.routes import _client_key

    request = Request({"type": "http", "client": ("198.51.100.2", 123),
                       "headers": [(b"x-forwarded-for", b"192.0.2.10"),
                                   (b"sb-forwarded-for", b"192.0.2.11")]})
    assert _client_key(request) == "ip:198.51.100.2"


async def test_lifespan_closes_the_reused_auth_client():
    from app.main import create_app

    app = create_app(Settings(_env_file=None))
    async with app.router.lifespan_context(app):
        client = app.state.auth_http
        assert not client.is_closed
    assert client.is_closed and app.state.auth_http is None
