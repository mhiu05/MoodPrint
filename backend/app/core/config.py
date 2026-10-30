from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url

from app.ai.embedding_config import EmbeddingSettings


class Settings(EmbeddingSettings, BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", hide_input_in_errors=True)
    app_env: Literal["development", "test", "production"] = "development"
    database_url: SecretStr | None = None
    database_migration_url: SecretStr | None = None
    database_pool_mode: Literal["direct", "session", "transaction"] = "session"
    supabase_url: str = ""
    supabase_publishable_key: SecretStr = SecretStr("")
    # Server-only private journal Storage credential. Never exported through session DTOs.
    journal_storage_key: SecretStr = SecretStr("")
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
    chat_history_enabled: bool = True
    chat_retention_days: int = Field(default=30, ge=1, le=90)
    ai_global_concurrency: int = Field(default=50, ge=1, le=100)
    ai_user_concurrency: int = Field(default=2, ge=1, le=5)
    ai_requests_per_minute: int = Field(default=20, ge=1, le=120)
    ai_timeout_seconds: float = Field(default=30, ge=1, le=120)
    database_pool_size: int = Field(default=8, ge=1, le=50)
    database_pool_overflow: int = Field(default=4, ge=0, le=50)
    database_pool_timeout: float = Field(default=10, ge=1, le=60)
    session_idle_hours: int = Field(default=12, ge=1, le=72)
    session_max_days: int = Field(default=7, ge=1, le=30)
    static_dir: str = ""
    # Matching scorer: v1 (rollback), v2 (rules-v2) or shadow (serve v1, log v2 overlap).
    matching_scorer: Literal["v1", "v2", "shadow"] = "v1"
    # Shared activities master switch and per-kind rollout (rollback = remove a kind).
    activities_enabled: bool = False
    activity_kinds: list[Literal["icebreaker", "coop_quiz", "focus"]] = [
        "icebreaker",
        "coop_quiz",
        "focus",
    ]
    # Short focus phases for automated tests only; ignored unless APP_ENV=test.
    focus_test_plan_seconds: int | None = Field(default=None, ge=5, le=600)
    # Staff moderation queue; the admin routes return 404 while this is off.
    moderation_admin_enabled: bool = False
    # Cost protection (DR-12): per-user turns per Asia/Bangkok day and a global daily
    # estimated-spend ceiling in USD (0 disables; needs AI_ACCOUNTING_ENABLED=true).
    ai_daily_turns_per_user: int = Field(default=60, ge=1, le=1000)
    ai_daily_budget_usd: float = Field(default=0, ge=0)
    # Guest trial and feedback rollout. Every flag defaults off; none of them can disable guest
    # expiry, cleanup, orphan reconciliation or liability settlement (those always run).
    guest_auth_enabled: bool = False
    guest_paid_enabled: bool = False
    guest_semantic_enabled: bool = False
    feedback_enabled: bool = False
    feedback_admin_enabled: bool = False
    product_tour_enabled: bool = False
    # Deployment revision stamped on feedback by the server; a client can never supply it.
    release_version: str = Field(default="unknown", pattern=r"^[A-Za-z0-9._+-]{1,64}$")
    # Owner-approved daily guest spend (D02). Unset or zero means paid guest work is unavailable,
    # never unlimited; pricing must also be known or paid dispatch stays closed.
    guest_daily_budget_usd: Decimal | None = Field(default=None, ge=0)
    guest_pricing_json: dict[str, Any] = Field(default_factory=dict)
    guest_abuse_hmac_key: SecretStr = SecretStr("")
    guest_captcha_site_key: str = ""
    guest_ai_turns: int = Field(default=25, ge=1, le=1000)
    guest_ai_per_minute: int = Field(default=6, ge=1, le=120)
    guest_ai_concurrency: int = Field(default=1, ge=1, le=5)
    guest_ai_global_concurrency: int = Field(default=10, ge=1, le=100)
    guest_voice_clips: int = Field(default=6, ge=1, le=100)
    guest_voice_seconds: int = Field(default=180, ge=1, le=3600)
    guest_voice_per_minute: int = Field(default=2, ge=1, le=60)
    guest_voice_concurrency: int = Field(default=1, ge=1, le=5)
    guest_voice_global_concurrency: int = Field(default=3, ge=1, le=100)

    @field_validator("guest_abuse_hmac_key")
    @classmethod
    def strong_abuse_key(cls, value: SecretStr) -> SecretStr:
        # Keys the rotating network/identity digests; a weak key makes the counters guessable.
        if value.get_secret_value() and len(value.get_secret_value()) < 32:
            raise ValueError("GUEST_ABUSE_HMAC_KEY must hold at least 32 characters")
        return value

    @model_validator(mode="after")
    def guest_capacity_within_global(self):
        if self.guest_ai_global_concurrency > self.ai_global_concurrency:
            if "guest_ai_global_concurrency" in self.model_fields_set:
                raise ValueError("GUEST_AI_GLOBAL_CONCURRENCY cannot exceed AI_GLOBAL_CONCURRENCY")
            # Existing deployments that only lowered the global cap keep working: the unset
            # guest default is clamped instead of rejected.
            self.guest_ai_global_concurrency = self.ai_global_concurrency
        return self

    @model_validator(mode="after")
    def local_live_scope(self):
        if self.ai_local_test_user_ids and self.app_env != "development":
            raise ValueError("Local live AI actors are allowed only in development")
        if self.app_env == "production":
            # Fail closed instead of serving production with development defaults.
            if not self.frontend_origin.startswith("https://"):
                raise ValueError("FRONTEND_ORIGIN must be https in production")
            if not self.supabase_url.startswith("https://"):
                raise ValueError("SUPABASE_URL must be https in production")
            if not self.supabase_publishable_key.get_secret_value():
                raise ValueError("SUPABASE_PUBLISHABLE_KEY is required in production")
            if not self.database_url or not self.database_url.get_secret_value():
                raise ValueError("DATABASE_URL is required in production")
            if self.ai_enabled and (
                not self.openai_api_key.get_secret_value() or not self.openai_model
            ):
                raise ValueError("OPENAI_API_KEY and OPENAI_MODEL are required when AI_ENABLED")
            if self.stt_enabled and (
                not self.openai_api_key.get_secret_value() or not self.stt_model
            ):
                raise ValueError("OPENAI_API_KEY and STT_MODEL are required when STT_ENABLED")
            if self.semantic_memory_enabled and not self.voyage_api_key.get_secret_value():
                raise ValueError("VOYAGE_API_KEY is required when SEMANTIC_MEMORY_ENABLED")
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
