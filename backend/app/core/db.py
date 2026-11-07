"""Runtime connections never use the privileged migration role."""

from moodprint_shared.config import AppConfig
from moodprint_shared.env import EnvSettings
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


def create_engine(settings: EnvSettings, cfg: AppConfig) -> AsyncEngine:
    url = make_url(settings.database_url.get_secret_value())
    if not url.username or url.username.split(".")[0] != "moodprint_api":
        raise ValueError("DATABASE_URL must use moodprint_api")
    return create_async_engine(
        url,
        pool_pre_ping=True,
        pool_size=cfg.api.db_pool_size,
        max_overflow=cfg.api.db_max_overflow,
        echo=False,
        hide_parameters=True,
        connect_args={"statement_cache_size": 0},
    )
