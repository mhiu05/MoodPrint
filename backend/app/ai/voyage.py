"""Small HTTP adapter. Exceptions never include request/response content or credentials."""

import math
from typing import Literal, Protocol

import httpx

from app.ai.embedding_config import EmbeddingSettings
from app.core.outbound import provider_timeout, provider_transport


class EmbeddingError(Exception):
    pass


class EmbeddingProvider(Protocol):
    async def embed(self, text: str, input_type: Literal["query", "document"]) -> list[float]: ...


def validate_vector(value: object, dimensions: int) -> list[float]:
    if not isinstance(value, list) or len(value) != dimensions:
        raise EmbeddingError("embedding_invalid_vector")
    if any(isinstance(v, bool) or not isinstance(v, (int, float)) for v in value):
        raise EmbeddingError("embedding_invalid_vector")
    vector = [float(v) for v in value]
    if any(not math.isfinite(v) for v in vector) or not any(vector):
        raise EmbeddingError("embedding_invalid_vector")
    return vector


class VoyageProvider:
    def __init__(self, settings: EmbeddingSettings, *, client: httpx.AsyncClient | None = None):
        self.settings = settings
        self.client = client

    async def embed(self, text: str, input_type: Literal["query", "document"]) -> list[float]:
        if not self.settings.voyage_api_key.get_secret_value():
            raise EmbeddingError("embedding_unconfigured")
        if not text or len(text) > 8000:
            raise EmbeddingError("embedding_input_invalid")
        if self.client is not None:
            return await self._request(self.client, text, input_type)
        async with httpx.AsyncClient(
            transport=provider_transport(self.settings.provider_force_ipv4),
            timeout=provider_timeout(self.settings.voyage_timeout_seconds),
        ) as client:
            return await self._request(client, text, input_type)

    async def _request(self, client: httpx.AsyncClient, text: str, input_type: str) -> list[float]:
        try:
            response = await client.post(
                "https://api.voyageai.com/v1/embeddings",
                headers={
                    "Authorization": "Bearer " + self.settings.voyage_api_key.get_secret_value()
                },
                json={
                    "input": [text],
                    "model": self.settings.voyage_model,
                    "input_type": input_type,
                    "output_dimension": self.settings.voyage_dimensions,
                    "output_dtype": "float",
                    "truncation": False,
                },
                timeout=provider_timeout(self.settings.voyage_timeout_seconds),
            )
            response.raise_for_status()
        except httpx.HTTPError:
            raise EmbeddingError("embedding_provider_unavailable") from None
        try:
            data = response.json()["data"]
            if not isinstance(data, list) or len(data) != 1 or data[0]["index"] != 0:
                raise ValueError
            return validate_vector(data[0]["embedding"], self.settings.voyage_dimensions)
        except (ValueError, KeyError, TypeError, IndexError):
            raise EmbeddingError("embedding_invalid_response") from None
