"""Fetch the original evidence bytes from the one trusted Storage origin, nowhere else.

The URL is produced by ``EvidenceService.open_read_url``; the model never supplies a URL, host or
header. Besides the string checks (scheme, userinfo, exact origin, signed-object path) every
resolved address is checked, redirects are never followed and the body is streamed under a hard
byte cap even when the server sends no Content-Length. Known limit: the connection resolves the
(fixed, project-controlled) host again, so DNS rebinding by an attacker who controls that host's
DNS is out of scope here; production origins are HTTPS with public addresses only.
"""

import asyncio
import ipaddress
import socket
from collections.abc import Awaitable, Callable
from urllib.parse import urlsplit

import httpx
from moodprint_agent.evidence.image import ImageRejected

Resolver = Callable[[str, int], Awaitable[list[str]]]
SIGNED_PATH_PREFIX = "/storage/v1/object/sign/"


class FetchRefused(ImageRejected):
    """The URL or response is not acceptable; the code never echoes the URL."""


async def system_resolver(host: str, port: int) -> list[str]:
    infos = await asyncio.get_running_loop().getaddrinfo(host, port, type=socket.SOCK_STREAM)
    return sorted({str(info[4][0]) for info in infos})


class SignedUrlFetcher:
    def __init__(
        self,
        storage_base_url: str,
        *,
        production: bool,
        max_bytes: int,
        timeout_s: float = 20,
        resolver: Resolver = system_resolver,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        origin = urlsplit(storage_base_url)
        self._scheme = origin.scheme
        self._host = (origin.hostname or "").lower()
        self._port = origin.port or (443 if origin.scheme == "https" else 80)
        self._production, self._max_bytes, self._timeout = production, max_bytes, timeout_s
        self._resolver, self._transport = resolver, transport
        loopback = self._host in {"localhost", "127.0.0.1", "::1"}
        # Only the stack's own loopback origin may be plain HTTP, and never in production.
        self._allow_loopback = loopback and not production
        if production and (origin.scheme != "https" or loopback):
            raise ValueError("production storage origin must be public HTTPS")

    def _check_url(self, url: str) -> str:
        parts = urlsplit(url)
        if parts.username is not None or parts.password is not None or "@" in parts.netloc:
            raise FetchRefused("fetch_refused")
        if (parts.hostname or "").lower() != self._host or parts.scheme != self._scheme:
            raise FetchRefused("fetch_refused")
        if (parts.port or (443 if parts.scheme == "https" else 80)) != self._port:
            raise FetchRefused("fetch_refused")
        if not parts.path.startswith(SIGNED_PATH_PREFIX) or ".." in parts.path or parts.fragment:
            raise FetchRefused("fetch_refused")
        return self._host

    async def _check_addresses(self, host: str) -> None:
        for address in await self._resolver(host, self._port):
            ip = ipaddress.ip_address(address)
            if ip.is_loopback and self._allow_loopback:
                continue
            if not ip.is_global:
                raise FetchRefused("fetch_refused")

    async def fetch(self, url: str) -> bytes:
        host = self._check_url(url)
        await self._check_addresses(host)
        body = bytearray()
        try:
            async with httpx.AsyncClient(
                follow_redirects=False, timeout=self._timeout, transport=self._transport
            ) as client:
                async with client.stream("GET", url, headers={"Accept": "image/*"}) as response:
                    if response.is_redirect or response.status_code != 200:
                        raise FetchRefused("fetch_failed")
                    declared = response.headers.get("content-length")
                    if (
                        declared is not None
                        and declared.isdigit()
                        and int(declared) > self._max_bytes
                    ):
                        raise FetchRefused("object_too_large")
                    async for chunk in response.aiter_bytes():
                        body.extend(chunk)
                        if len(body) > self._max_bytes:
                            raise FetchRefused("object_too_large")
        except httpx.HTTPError:
            raise FetchRefused("fetch_failed") from None
        return bytes(body)
