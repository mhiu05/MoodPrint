"""Non-secret application defaults, independent of process environment."""

from dataclasses import dataclass, field
from typing import Final

OPENAI_MODEL: Final = "gpt-6-luna"


@dataclass(frozen=True, slots=True)
class AgentConfig:
    companion_model: str = OPENAI_MODEL
    compaction_model: str = OPENAI_MODEL
    vision_model: str = OPENAI_MODEL
    eval_model: str = OPENAI_MODEL
    max_turns: int = 8
    max_tool_calls_per_run: int = 6
    run_timeout_s: float = 90
    max_user_input_chars: int = 4000
    session_item_limit: int = 100
    messages_per_user_per_hour: int = 60
    heartbeat_interval_s: float = 15


@dataclass(frozen=True, slots=True)
class MemoryConfig:
    stale_days: int = 90
    search_limit: int = 5
    lexical_weight: float = 0.6
    similarity_weight: float = 0.3
    recency_weight: float = 0.1
    max_content_chars: int = 500
    candidate_ttl_days: int = 30


@dataclass(frozen=True, slots=True)
class EvidenceConfig:
    bucket: str = "incident-evidence"
    max_object_bytes: int = 2 * 1024**3
    user_quota_bytes: int = 5 * 1024**3
    pending_uploads_per_user: int = 10
    upload_rate_per_hour: int = 60
    download_url_ttl_s: int = 120
    upload_chunk_bytes: int = 6 * 1024**2
    pending_upload_ttl_hours: int = 48


@dataclass(frozen=True, slots=True)
class KnowledgeConfig:
    retriever: str = "fixture"
    top_k: int = 5
    timeout_s: float = 15


@dataclass(frozen=True, slots=True)
class ApiConfig:
    db_pool_size: int = 5
    db_max_overflow: int = 5
    jwks_cache_ttl_s: int = 600
    jwks_unknown_kid_refresh_s: int = 60
    jwt_algorithms: tuple[str, ...] = ("ES256",)
    default_page_size: int = 50
    max_page_size: int = 100
    reconcile_interval_s: float = 30
    stale_run_after_s: int = 180


@dataclass(frozen=True, slots=True)
class LoggingConfig:
    level: str = "INFO"


@dataclass(frozen=True, slots=True)
class AppConfig:
    agent: AgentConfig = field(default_factory=AgentConfig)
    memory: MemoryConfig = field(default_factory=MemoryConfig)
    evidence: EvidenceConfig = field(default_factory=EvidenceConfig)
    knowledge: KnowledgeConfig = field(default_factory=KnowledgeConfig)
    api: ApiConfig = field(default_factory=ApiConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)

    @property
    def openai_model(self) -> str:
        return OPENAI_MODEL
