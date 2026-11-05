"""Explicit capability gate; user opt-in lives separately in ai_preferences."""

from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings


class EmbeddingSettings(BaseSettings):
    semantic_memory_enabled: bool = False
    voyage_api_key: SecretStr = SecretStr("")
    voyage_model: str = Field(default="voyage-4-lite", min_length=1, max_length=100)
    voyage_dimensions: Literal[256, 512, 1024, 2048] = 1024
    voyage_timeout_seconds: float = Field(default=10, ge=1, le=30)
    embedding_job_batch_size: int = Field(default=10, ge=1, le=50)
    embedding_max_attempts: int = Field(default=4, ge=1, le=8)
    embedding_lease_seconds: int = Field(default=60, ge=35, le=600)
    memory_retrieval_limit: int = Field(default=6, ge=1, le=10)
    memory_fallback_limit: int = Field(default=100, ge=10, le=500)
    memory_similarity_threshold: float = Field(default=0.3, ge=0, le=1)
    memory_context_char_limit: int = Field(default=1200, ge=120, le=4000)
    provider_force_ipv4: bool = False

    @field_validator("voyage_dimensions", mode="before")
    @classmethod
    def parse_environment_dimensions(cls, value: object) -> object:
        # Literal[int] does not coerce dotenv strings like an ordinary int field.
        if isinstance(value, str) and value.isascii() and value.isdigit():
            return int(value)
        return value

    @property
    def semantic_memory_available(self) -> bool:
        return self.semantic_memory_enabled and bool(self.voyage_api_key.get_secret_value())
