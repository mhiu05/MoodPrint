"""Curated acquisition: HTTPS allow-list, SSRF checks, robots, and size limits."""

from __future__ import annotations

import asyncio
import hashlib
import ipaddress
import socket
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import httpx

MAX_BYTES = 15 * 1024 * 1024
_PRIVATE_NETWORKS = (
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
)


@dataclass(frozen=True, slots=True)
class RawSnapshot:
    source_id: str
    url: str
    sha256: str
    payload: bytes
    content_type: str


def assert_public_https(url: str, allow_hosts: set[str]) -> None:
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname:
        raise ValueError("only https URLs are allowed")
    host = parsed.hostname.lower()
    if host not in allow_hosts:
        raise ValueError("host is outside the source allow-list")
    try:
        infos = socket.getaddrinfo(host, parsed.port or 443)
    except socket.gaierror as exc:
        raise ValueError("host did not resolve") from exc
    for info in infos:
        sockaddr = info[4]
        address = ipaddress.ip_address(str(sockaddr[0]))
        if any(address in network for network in _PRIVATE_NETWORKS) or address.is_loopback:
            raise ValueError("resolved address is not public")


def robots_allow(url: str, robots_text: str) -> bool:
    parser = RobotFileParser()
    parser.parse(robots_text.splitlines())
    return parser.can_fetch("MoodPrintKnowledgeBot", url)


async def fetch_source(
    source_id: str,
    url: str,
    allow_hosts: list[str],
    *,
    client: httpx.AsyncClient,
    cache: Path,
    expected_sha256: str | None = None,
    min_interval_s: float = 1.0,
    host_clock: dict[str, float] | None = None,
) -> RawSnapshot | None:
    assert_public_https(url, {host.lower() for host in allow_hosts})
    parsed = urlparse(url)
    host = parsed.hostname or ""
    clock = host_clock if host_clock is not None else {}
    wait = min_interval_s - (asyncio.get_running_loop().time() - clock.get(host, -999))
    if wait > 0:
        await asyncio.sleep(wait)
    robots_url = f"https://{host}/robots.txt"
    robots = await client.get(robots_url)
    if robots.status_code == 200 and not robots_allow(url, robots.text):
        return None
    response = await _get_with_retry(client, url)
    clock[host] = asyncio.get_running_loop().time()
    if response is None:
        return None
    payload = response.content
    if len(payload) > MAX_BYTES:
        raise ValueError("response exceeded 15 MB")
    digest = hashlib.sha256(payload).hexdigest()
    if expected_sha256 and digest != expected_sha256:
        raise ValueError("sha256 did not match the pin")
    _write_cache(cache, digest, payload)
    return RawSnapshot(
        source_id=source_id,
        url=str(response.url),
        sha256=digest,
        payload=payload,
        content_type=response.headers.get("content-type", ""),
    )


def _write_cache(cache: Path, digest: str, payload: bytes) -> None:
    cache.mkdir(parents=True, exist_ok=True)
    (cache / digest).write_bytes(payload)


async def _get_with_retry(client: httpx.AsyncClient, url: str) -> httpx.Response | None:
    delay = 0.2
    for attempt in range(3):
        response = await client.get(url, follow_redirects=False)
        if response.status_code in {301, 302, 303, 307, 308}:
            raise ValueError("redirects must be re-checked by the caller")
        if response.status_code == 200:
            return response
        if response.status_code not in {429, 500, 502, 503, 504} or attempt == 2:
            raise ValueError(f"fetch failed with status {response.status_code}")
        await asyncio.sleep(delay)
        delay *= 2
    return None
