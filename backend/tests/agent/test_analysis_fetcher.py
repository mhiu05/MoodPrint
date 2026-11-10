"""U-AG-126…140: the evidence fetcher only talks to the one signed Storage origin.

Strings are not enough, so the resolver and transport are exercised too: redirects, private
addresses, missing Content-Length, userinfo tricks and the byte cap.
"""

import httpx
import pytest
from app.modules.analysis.fetcher import FetchRefused, SignedUrlFetcher

BASE = "https://project.supabase.co"
GOOD = BASE + "/storage/v1/object/sign/bucket/users/u/originals/e.png?token=abc"


async def public(host: str, port: int) -> list[str]:
    return ["93.184.216.34"]


def fetcher(handler=None, *, base: str = BASE, production: bool = True, resolver=public, cap=1000):
    transport = httpx.MockTransport(
        handler or (lambda request: httpx.Response(200, content=b"PNG"))
    )
    return SignedUrlFetcher(
        base, production=production, max_bytes=cap, resolver=resolver, transport=transport
    )


async def test_the_exact_signed_origin_is_fetched() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, content=b"pixels")

    assert await fetcher(handler).fetch(GOOD) == b"pixels"
    assert str(seen[0].url) == GOOD and "authorization" not in seen[0].headers


@pytest.mark.parametrize(
    "url",
    [
        "https://evil.example/storage/v1/object/sign/x",  # other host
        "https://project.supabase.co.evil.example/storage/v1/object/sign/x",  # suffix trick
        "https://user:pw@project.supabase.co/storage/v1/object/sign/x",  # userinfo
        "https://project.supabase.co@evil.example/storage/v1/object/sign/x",  # userinfo host swap
        "http://project.supabase.co/storage/v1/object/sign/x",  # downgrade
        "https://project.supabase.co:8443/storage/v1/object/sign/x",  # other port
        "https://project.supabase.co/rest/v1/profiles",  # not a signed object
        "https://project.supabase.co/storage/v1/object/sign/../../auth/v1/admin",  # traversal
        "https://project.supabase.co/storage/v1/object/sign/x#frag",
        "file:///etc/passwd",
        "gopher://project.supabase.co/storage/v1/object/sign/x",
    ],
)
async def test_urls_outside_the_signed_storage_origin_are_refused_before_any_request(
    url: str,
) -> None:
    calls = []
    guarded = fetcher(lambda request: calls.append(request) or httpx.Response(200, content=b"x"))
    with pytest.raises(FetchRefused):
        await guarded.fetch(url)
    assert calls == []


@pytest.mark.parametrize(
    "address",
    ["127.0.0.1", "10.0.0.5", "192.168.1.9", "169.254.169.254", "::1", "fd00::1", "0.0.0.0"],
)
async def test_a_host_that_resolves_to_a_private_address_is_refused(address: str) -> None:
    async def resolver(host: str, port: int) -> list[str]:
        return ["93.184.216.34", address]  # one bad answer poisons the lookup

    with pytest.raises(FetchRefused):
        await fetcher(resolver=resolver).fetch(GOOD)


async def test_redirects_are_never_followed() -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        return httpx.Response(302, headers={"location": "http://169.254.169.254/latest/meta-data"})

    with pytest.raises(FetchRefused):
        await fetcher(handler).fetch(GOOD)
    assert calls == [GOOD]


async def test_non_200_responses_are_a_failure_not_data() -> None:
    with pytest.raises(FetchRefused):
        await fetcher(lambda r: httpx.Response(404, content=b"nope")).fetch(GOOD)


async def test_the_byte_cap_holds_with_and_without_content_length() -> None:
    declared = httpx.Response(200, headers={"content-length": "5000"}, content=b"x" * 10)
    with pytest.raises(FetchRefused) as caught:
        await fetcher(lambda r: declared, cap=1000).fetch(GOOD)
    assert caught.value.code == "object_too_large"

    def chunked(request: httpx.Request) -> httpx.Response:
        async def body():
            for _ in range(50):
                yield b"x" * 100  # no Content-Length: only the streamed count can stop it

        return httpx.Response(200, content=body())

    with pytest.raises(FetchRefused) as caught2:
        await fetcher(chunked, cap=1000).fetch(GOOD)
    assert caught2.value.code == "object_too_large"


async def test_transport_errors_become_a_fetch_failure() -> None:
    def boom(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused")

    with pytest.raises(FetchRefused) as caught:
        await fetcher(boom).fetch(GOOD)
    assert caught.value.code == "fetch_failed"


async def test_local_stack_loopback_is_allowed_only_outside_production() -> None:
    local = "http://127.0.0.1:54521"

    async def loopback(host: str, port: int) -> list[str]:
        return ["127.0.0.1"]

    url = local + "/storage/v1/object/sign/b/users/u/o.png?token=t"
    assert await fetcher(base=local, production=False, resolver=loopback).fetch(url) == b"PNG"
    with pytest.raises(ValueError):
        SignedUrlFetcher(local, production=True, max_bytes=10)
    with pytest.raises(ValueError):
        SignedUrlFetcher("http://project.supabase.co", production=True, max_bytes=10)

    # The loopback allowance does not extend to other private ranges on the same host.
    async def lan(host: str, port: int) -> list[str]:
        return ["10.0.0.9"]

    with pytest.raises(FetchRefused):
        await fetcher(base=local, production=False, resolver=lan).fetch(url)
