import sys

from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from app.core.config import Settings
from app.core.errors import DomainError


class Database:
    def __init__(self, settings: Settings):
        self.engine: AsyncEngine | None = None
        self.sessions: async_sessionmaker | None = None
        if settings.database_url and settings.database_url.get_secret_value():
            raw = settings.database_url.get_secret_value()
            url = raw.replace("postgres://", "postgresql+psycopg://", 1).replace(
                "postgresql://", "postgresql+psycopg://", 1
            )
            if sys.platform == "win32":
                # psycopg requires a selector loop; uvicorn's asyncio loop is configured in app CLI.
                pass
            self.engine = create_async_engine(
                url,
                pool_size=settings.database_pool_size,
                max_overflow=settings.database_pool_overflow,
                pool_timeout=settings.database_pool_timeout,
                pool_pre_ping=True,
                hide_parameters=True,
                connect_args={"prepare_threshold": None, "connect_timeout": 5},
            )
            self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)

    def require(self) -> async_sessionmaker:
        if self.sessions is None:
            raise DomainError(503, "DATABASE_UNAVAILABLE", "Kết nối dữ liệu chưa sẵn sàng.", True)
        return self.sessions
