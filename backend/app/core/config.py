from typing import Literal
from uuid import UUID

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", hide_input_in_errors=True)
    app_env: Literal["development", "test", "production"] = "development"
    database_url: SecretStr | None = None
    database_migration_url: SecretStr | None = None
    database_pool_mode: Literal["direct", "session", "transaction"] = "session"
    supabase_url: str = ""
    supabase_publishable_key: SecretStr = SecretStr("")
    frontend_origin: str = "http://127.0.0.1:5173"
    cookie_secure: bool = False
    openai_api_key: SecretStr = SecretStr("")
    openai_model: str = ""
    ai_enabled: bool = False
    ai_accounting_enabled: bool = False
    ai_local_test_user_ids: list[UUID] = Field(default_factory=list)
    stt_enabled: bool = False
    stt_model: str = ""
    sandbox_enabled: bool = False

    @model_validator(mode="after")
    def local_live_scope(self):
        if self.ai_local_test_user_ids and self.app_env != "development":
            raise ValueError("Local live AI actors are allowed only in development")
        return self

    def ai_available_for(self, user_id: UUID | None) -> bool:
        return self.ai_enabled or bool(
            self.app_env == "development" and user_id in self.ai_local_test_user_ids
        )

    @field_validator("database_url", "database_migration_url")
    @classmethod
    def postgres_only(cls, value: SecretStr | None) -> SecretStr | None:
        if value and value.get_secret_value():
            raw = value.get_secret_value()
            if not raw.startswith(("postgresql://", "postgres://", "postgresql+psycopg://")):
                raise ValueError("A PostgreSQL connection URL is required")
            try:
                target = make_url(raw)
                if (
                    not target.host
                    or not target.database
                    or any(token in target.database for token in ("://", "/", "\\"))
                ):
                    raise ValueError
                if target.port is not None and not 1 <= target.port <= 65535:
                    raise ValueError
            except Exception:
                raise ValueError(
                    "PostgreSQL URL must contain a valid host, port and database"
                ) from None
        return value

    @field_validator("supabase_url")
    @classmethod
    def secure_provider(cls, value: str) -> str:
        if value and not value.startswith("https://"):
            raise ValueError("Supabase Auth must use HTTPS")
        return value.rstrip("/")
