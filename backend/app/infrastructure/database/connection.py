import math
import sys
import time
from collections import deque

from sqlalchemy.exc import TimeoutError as PoolTimeout
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from sqlalchemy.pool import AsyncAdaptedQueuePool

from app.core.config import Settings
from app.core.errors import DomainError


class TimedQueuePool(AsyncAdaptedQueuePool):
    """Acquire duration includes queue/create work in _do_get, not pre-ping or SQL.

    Keep a bounded recent window plus lifetime counts; never call a window percentile
    a whole-run distribution or include connection URLs/SQL/parameters in metrics.
    """
    def __init__(self, *args, **kwargs):
        self.acquire_samples: deque[float] = deque(maxlen=2048)
        self.acquire_count = self.acquire_timeouts = 0
        super().__init__(*args, **kwargs)

    def _do_get(self):
        started = time.monotonic()
        try:
            return super()._do_get()
        except PoolTimeout:
            self.acquire_timeouts += 1
            raise
        finally:
            self.acquire_count += 1
            self.acquire_samples.append((time.monotonic() - started) * 1000)

    def measurements(self):
        values = sorted(self.acquire_samples)
        return {"acquisitions": self.acquire_count, "timeouts": self.acquire_timeouts,
                "window_samples": len(values),
                "p95_ms": values[max(0, math.ceil(len(values)*0.95)-1)] if values else None,
                "max_ms": max(values) if values else None}


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
                **({"poolclass": TimedQueuePool} if settings.database_pool_metrics_enabled else {}),
            )
            self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)

    def pool_metrics(self) -> dict:
        pool = self.engine.pool if self.engine else None
        return pool.measurements() if isinstance(pool, TimedQueuePool) else {}

    def occupancy(self) -> tuple[int | None, int | None]:
        engine = self.engine
        if engine is None:
            return None, None
        try:
            pool = engine.pool
            checked_fn = getattr(pool, "checkedout", None)
            overflow_fn = getattr(pool, "overflow", None)
            if not callable(checked_fn) or not callable(overflow_fn):
                return None, None
            checked = checked_fn()
            overflow = overflow_fn()
        except Exception:
            return None, None
        if not isinstance(checked, int) or not isinstance(overflow, int):
            return None, None
        return checked, overflow

    def require(self) -> async_sessionmaker:
        if self.sessions is None:
            raise DomainError(503, "DATABASE_UNAVAILABLE", "Kết nối dữ liệu chưa sẵn sàng.", True)
        return self.sessions
