"""Environment boundary. Test processes never read the owner's dotenv."""

import os
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Any, Literal
from urllib.parse import urlsplit

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[3]


class UnsafeTestEnvironment(ValueError):
    """Refuse test startup against any database outside loopback."""


class EnvSettings(BaseSettings):
    model_config = SettingsConfigDict(
        extra="ignore",
        alias_generator=str.upper,
        populate_by_name=True,
        hide_input_in_errors=True,
        case_sensitive=False,
    )
    app_env: Literal["development", "test", "production"] = "development"
    supabase_url: str = Field(min_length=1)
    supabase_publishable_key: str = Field(min_length=1)
    supabase_secret_key: SecretStr = Field(min_length=1)
    database_url: SecretStr = Field(min_length=1)
    supabase_db_url: SecretStr | None = None
    cors_allowed_origins: Annotated[list[str], NoDecode] = Field(default_factory=list)
    vite_public_supabase_url: str | None = None
    vite_public_supabase_publishable_key: str | None = None
    vite_public_api_base_url: str | None = None
    openai_api_key: SecretStr | None = None
    voyage_api_key: SecretStr | None = None
    apify_api_token: SecretStr | None = None
    auth_test_jwt_secret: SecretStr | None = None

    def __init__(self, **values: Any) -> None:
        environment = values.get(
            "app_env", values.get("APP_ENV", os.getenv("APP_ENV", "development"))
        )
        values["_env_file"] = (
            None if environment == "test" else values.get("_env_file", ROOT / ".env")
        )
        super().__init__(**values)
        if self.app_env == "test":
            try:
                hostname = urlsplit(self.database_url.get_secret_value()).hostname
            except ValueError:
                hostname = None
            if hostname not in {"localhost", "127.0.0.1", "::1"}:
                raise UnsafeTestEnvironment("DATABASE_URL must use loopback when APP_ENV=test")

    @field_validator("cors_allowed_origins", mode="before")
    @classmethod
    def parse_origins(cls, value: object) -> object:
        if isinstance(value, str):
            import json

            if value.lstrip().startswith("["):
                return json.loads(value)
            return [part.strip() for part in value.split(",") if part.strip()]
        return value

    @field_validator("cors_allowed_origins")
    @classmethod
    def validate_origins(cls, value: list[str]) -> list[str]:
        if any(
            origin == "*" or urlsplit(origin).scheme not in {"http", "https"} for origin in value
        ):
            raise ValueError("CORS_ALLOWED_ORIGINS must contain explicit HTTP origins")
        return value


@lru_cache(maxsize=1)
def get_settings() -> EnvSettings:
    return EnvSettings()
