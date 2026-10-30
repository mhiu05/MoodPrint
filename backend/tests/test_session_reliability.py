import logging

import httpx
from sqlalchemy.exc import OperationalError, ProgrammingError
from sqlalchemy.exc import TimeoutError as PoolTimeout

from app.core.config import Settings
from app.infrastructure.database.budget import has_deployment_headroom
from app.infrastructure.database.errors import database_failure_category
from app.main import create_app


class _DriverError(Exception):
    def __init__(self, message: str, sqlstate: str | None):
        super().__init__(message)
        self.sqlstate = sqlstate


CANARY = "SECRET-CANARY-postgresql://user:password@db.example/postgres token=abc journal-text"


def _app(release: str = "abc123") -> object:
    return create_app(Settings(_env_file=None, release_sha=release))


async def _raise(app, error: Exception):
    @app.get("/api/v1/test-db-failure")
    async def fail():
        raise error

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        return await client.get("/api/v1/test-db-failure")


def test_recommended_pool_fits_the_approved_role_and_the_old_default_does_not():
    assert has_deployment_headroom(5, 2, role_limit=20) is True
    assert has_deployment_headroom(5, 5, role_limit=20) is False
    assert has_deployment_headroom(8, 4, role_limit=10) is False
    assert has_deployment_headroom(8, 4, role_limit=20) is False


def test_classifier_prefers_sqlstate_and_does_not_hide_programming_errors():
    limited = OperationalError("select 1", {}, _DriverError("too many connections for role", "53300"))
    unnamed = OperationalError("select 1", {}, _DriverError(CANARY + " too many connections for role", None))
    down = OperationalError("select 1", {}, _DriverError("could not connect to server", None))
    programming = ProgrammingError("select 1", {}, _DriverError(CANARY, "42601"))
    deadlock = OperationalError("select 1", {}, _DriverError("deadlock detected", "40P01"))
    assert database_failure_category(limited) == "connection_limit"
    assert database_failure_category(unnamed) == "connection_limit"
    assert database_failure_category(down) == "connection_unavailable"
    assert database_failure_category(PoolTimeout("QueuePool limit of size 5 overflow 2 reached")) == "pool_timeout"
    assert database_failure_category(programming) is None
    assert database_failure_category(deadlock) is None
    assert database_failure_category(RuntimeError(CANARY)) is None


async def test_connection_limit_is_retryable_503_without_leaking_the_driver_text(caplog):
    caplog.set_level(logging.INFO)
    error = OperationalError("select secret", {"url": CANARY}, _DriverError(CANARY + " too many connections for role", "53300"))
    response = await _raise(_app(), error)
    body = response.json()["error"]
    assert response.status_code == 503
    assert response.headers["Retry-After"] == "2"
    assert body["code"] == "DATABASE_BUSY"
    assert body["retryable"] is True
    assert body["message"] == "MoodPrint đang hơi đông. Bạn hãy thử lại sau ít giây."
    assert CANARY not in response.text
    assert CANARY not in caplog.text
    assert "request_completed" in caplog.text
    assert "route=/api/v1/test-db-failure" in caplog.text
    assert "category=connection_limit" in caplog.text
    assert "sqlstate=53300" in caplog.text
    assert "release=abc123" in caplog.text


async def test_pool_timeout_and_unknown_errors_stay_distinct(caplog):
    caplog.set_level(logging.INFO)
    busy = await _raise(_app(), PoolTimeout(CANARY))
    assert busy.status_code == 503
    assert busy.json()["error"]["code"] == "DATABASE_BUSY"
    assert CANARY not in busy.text and CANARY not in caplog.text

    caplog.clear()
    unknown = await _raise(_app(), RuntimeError(CANARY))
    body = unknown.json()["error"]
    assert unknown.status_code == 500
    assert body["code"] == "INTERNAL_ERROR"
    assert body["retryable"] is False
    assert CANARY not in unknown.text and CANARY not in caplog.text
    assert "category=unexpected" in caplog.text


async def test_auth_errors_are_not_relabelled_as_database_outages():
    from app.core.errors import DomainError

    app = _app()

    @app.get("/api/v1/test-auth")
    async def denied():
        raise DomainError(401, "SESSION_EXPIRED", "Phiên đã kết thúc. Vui lòng đăng nhập lại.")

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/test-auth")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "SESSION_EXPIRED"
    assert response.json()["error"]["retryable"] is False


def test_oversized_pool_logs_a_headroom_warning(caplog):
    caplog.set_level(logging.WARNING)
    create_app(Settings(_env_file=None, database_pool_size=8, database_pool_overflow=4))
    assert "database_pool_exceeds_headroom" in caplog.text
    assert "size=8" in caplog.text and "overflow=4" in caplog.text


def test_release_sha_rejects_unsafe_values():
    assert Settings(_env_file=None, release_sha="").release_sha == "unknown"
    assert Settings(_env_file=None, release_sha="sha\nSECRET").release_sha == "unknown"
    assert Settings(_env_file=None, release_sha="57b3f7f").release_sha == "57b3f7f"
