"""Outbound HTTP transport for paid providers.

Retries apply only to connection establishment (httpx ConnectError/ConnectTimeout), so a
request that may have reached the provider is never sent twice. Some networks drop a share
of parallel IPv6 handshakes; PROVIDER_FORCE_IPV4 binds outbound sockets to IPv4.
"""

import httpx

CONNECT_RETRIES = 2


def provider_timeout(total: float) -> httpx.Timeout:
    return httpx.Timeout(total, connect=min(5.0, total))


def provider_transport(force_ipv4: bool) -> httpx.AsyncHTTPTransport:
    return httpx.AsyncHTTPTransport(
        retries=CONNECT_RETRIES,
        local_address="0.0.0.0" if force_ipv4 else None,
        limits=httpx.Limits(max_connections=100, max_keepalive_connections=20, keepalive_expiry=60),
    )


def openai_http_client(force_ipv4: bool, total: float = 30):
    """The OpenAI SDK ships its own httpx fork (httpx2) with the same transport API."""
    import httpx2

    return httpx2.AsyncClient(
        transport=httpx2.AsyncHTTPTransport(
            retries=CONNECT_RETRIES,
            local_address="0.0.0.0" if force_ipv4 else None,
            limits=httpx2.Limits(
                max_connections=100, max_keepalive_connections=20, keepalive_expiry=60
            ),
        ),
        timeout=httpx2.Timeout(total, connect=min(5.0, total)),
    )
