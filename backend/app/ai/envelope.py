"""Opt-in 64k text envelope, enforced on the actual serialized Responses HTTP body.

Uses the official exact input-count endpoint BEFORE every generation. Unknown/malformed
counts, stateful references and provider-hosted tools fail closed. This candidate adds
preflight latency; it never truncates context. Production activation requires account-level
validation of the count endpoint, pricing and UX acceptance. No network runs at import.
"""

import json
from contextvars import ContextVar

import httpx2

from app.core.errors import DomainError

BOUNDED_PRICING_VERSION = "openai-conservative-64k-2026-11-05-v2"
MAX_INPUT_TOKENS = 64_000
MAX_OUTPUT_TOKENS = 1200
MAX_CALLS = 3
COUNT_FIELDS = frozenset({"model", "input", "instructions", "tools", "tool_choice", "text",
                          "parallel_tool_calls", "personality", "reasoning", "truncation"})
NON_INPUT_FIELDS = frozenset({"store", "stream", "stream_options", "max_output_tokens", "max_tool_calls",
                              "temperature", "top_p", "service_tier", "prompt_cache_key", "prompt_cache_retention",
                              "include", "user", "safety_identifier", "metadata", "background",
                              "previous_response_id", "conversation", "prompt"})
# 3 * (64000*550 + 1200*1650) =111,540,000 nano; round UP to120,000,000.
BOUNDED_RESERVATION_NANO = 120_000_000
LEGACY_GUEST_DISPATCH: ContextVar[bool] = ContextVar("legacy_guest_dispatch", default=False)


def unavailable():
    return DomainError(503, "AI_ENVELOPE_UNAVAILABLE", "Chưa xác minh được giới hạn chi phí cho lượt này. Bạn hãy thử lại sau.", True)


def count_payload(body):
    if (not isinstance(body, dict) or body.get("model") != "gpt-6-luna"
            or body.get("store") is not False
            or type(body.get("max_output_tokens")) is not int
            or not 1 <= body["max_output_tokens"] <= MAX_OUTPUT_TOKENS
            or any(body.get(k) for k in ("previous_response_id", "conversation", "prompt", "background"))
            or body.get("truncation", "disabled") != "disabled"):
        raise unavailable()
    if set(body) - COUNT_FIELDS - NON_INPUT_FIELDS:
        # A future unknown input-affecting parameter cannot silently escape counting.
        raise unavailable()
    if body.get("service_tier") not in (None, "auto", "default", "flex", "fast", "priority"):
        raise unavailable()
    tools = body.get("tools", [])
    if not isinstance(tools, list) or any(not isinstance(t, dict) or t.get("type") != "function" for t in tools):
        # Hosted search/MCP/image calls can introduce uncounted inputs and fees inside a call.
        raise unavailable()

    def static_text(value):
        if isinstance(value, dict):
            if value.get("type") == "item_reference" or any(k in value for k in ("image_url", "file_id", "file_url", "file_data", "audio")):
                raise unavailable()
            for item in value.values():
                static_text(item)
        elif isinstance(value, list):
            for item in value:
                static_text(item)

    static_text(body.get("input"))
    # The pinned InputTokenCountParams accepts these input-affecting fields. Generation-only
    # controls are validated separately, not sent as unsupported count API parameters.
    return {key: value for key, value in body.items() if key in COUNT_FIELDS}


class BoundedResponsesTransport(httpx2.AsyncBaseTransport):
    def __init__(self, delegate):
        self.delegate = delegate

    async def handle_async_request(self, request):
        if LEGACY_GUEST_DISPATCH.get():
            # Guests retain the existing full-context reservation and last-await lifetime guard.
            return await self.delegate.handle_async_request(request)
        if (request.method != "POST" or request.url.scheme != "https"
                or request.url.host != "api.openai.com" or request.url.path != "/v1/responses"):
            raise unavailable()
        try:
            payload = count_payload(json.loads(await request.aread()))
            headers = {k: v for k, v in request.headers.items() if k.lower() not in ("content-length", "accept")}
            headers["Accept"] = "application/json"
            counter = httpx2.Request("POST", request.url.copy_with(path="/v1/responses/input_tokens"),
                                    headers=headers, json=payload, extensions=request.extensions)
            response = await self.delegate.handle_async_request(counter)
            try:
                await response.aread()
                if response.status_code != 200:
                    raise unavailable()
                counted = response.json()
            finally:
                await response.aclose()
            if (not isinstance(counted, dict) or counted.get("object") != "response.input_tokens"
                    or type(counted.get("input_tokens")) is not int or counted["input_tokens"] <= 0):
                raise unavailable()
            if counted["input_tokens"] > MAX_INPUT_TOKENS:
                raise DomainError(422, "AI_CONTEXT_LIMIT", "Ngữ cảnh lượt này vượt giới hạn thử nghiệm an toàn. Lịch sử chưa bị cắt; bạn có thể bắt đầu cuộc trò chuyện mới.")
        except (httpx2.HTTPError, ValueError, TypeError, KeyError):
            raise unavailable() from None
        # Only the validated original body is dispatched. Counting never mutates/rebuilds it.
        return await self.delegate.handle_async_request(request)

    async def aclose(self):
        await self.delegate.aclose()
