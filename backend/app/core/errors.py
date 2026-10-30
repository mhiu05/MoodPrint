import re
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.contracts import ApiError, ErrorDetail
from app.infrastructure.database.errors import database_failure_category, sqlstate_of

_SAFE_TOKEN = re.compile(r"^[A-Za-z0-9_.]{1,48}$")


class DomainError(Exception):
    def __init__(
        self,
        status: int,
        code: str,
        message: str,
        retryable: bool = False,
        *,
        current_session_id: str | None = None,
        retry_after: int | None = None,
        clear_session: bool = False,
    ):
        self.status, self.code, self.message, self.retryable = status, code, message, retryable
        self.current_session_id, self.retry_after = current_session_id, retry_after
        # Ask the browser to drop its session cookies (an expired or ended guest trial).
        self.clear_session = clear_session
        super().__init__(code)


def _safe_token(value: object) -> str:
    if isinstance(value, str) and _SAFE_TOKEN.fullmatch(value):
        return value
    return "-"


def note_failure(request: Request, category: str, error_type: str, sqlstate: str | None) -> None:
    request.state.error_category = _safe_token(category)
    request.state.error_type = _safe_token(error_type)
    request.state.sqlstate = _safe_token(sqlstate) if sqlstate else "-"


def render_unexpected(request: Request, error: Exception) -> JSONResponse:
    category = database_failure_category(error)
    note_failure(request, category or "unexpected", type(error).__name__, sqlstate_of(error))
    if category in {"connection_limit", "pool_timeout"}:
        status, code, message, retryable, retry_after = (
            503,
            "DATABASE_BUSY",
            "MoodPrint đang hơi đông. Bạn hãy thử lại sau ít giây.",
            True,
            2,
        )
    elif category == "connection_unavailable":
        status, code, message, retryable, retry_after = (
            503,
            "DATABASE_UNAVAILABLE",
            "MoodPrint đang gặp chút gián đoạn. Bạn hãy thử lại sau ít phút.",
            True,
            5,
        )
    else:
        status, code, message, retryable, retry_after = (
            500,
            "INTERNAL_ERROR",
            "MoodPrint đang gặp chút gián đoạn. Bạn hãy thử lại.",
            False,
            None,
        )
    payload = ApiError(
        error=ErrorDetail(
            code=code,
            message=message,
            retryable=retryable,
            request_id=getattr(request.state, "request_id", str(uuid4())),
        )
    )
    headers = {"Cache-Control": "no-store"}
    if retry_after is not None:
        headers["Retry-After"] = str(retry_after)
    return JSONResponse(
        payload.model_dump(by_alias=True, exclude_none=True),
        status_code=status,
        headers=headers,
    )


def install_errors(app: FastAPI) -> None:
    @app.exception_handler(DomainError)
    async def domain_error(request: Request, error: DomainError) -> JSONResponse:
        note_failure(request, error.code, "DomainError", None)
        payload = ApiError(
            error=ErrorDetail(
                code=error.code,
                message=error.message,
                retryable=error.retryable,
                request_id=getattr(request.state, "request_id", str(uuid4())),
                current_session_id=error.current_session_id,
            )
        )
        headers = {"Cache-Control": "no-store"}
        if error.retry_after is not None:
            headers["Retry-After"] = str(error.retry_after)
        response = JSONResponse(
            payload.model_dump(by_alias=True, exclude_none=True),
            status_code=error.status,
            headers=headers,
        )
        if error.clear_session:
            for name, path in (
                ("moodprint_session", "/"),
                ("moodprint_csrf", "/"),
                ("moodprint_guest_intent", "/api/v1/auth"),
            ):
                response.delete_cookie(name, path=path)
        return response

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, error: RequestValidationError) -> JSONResponse:
        # Pydantic errors can contain submitted passwords/text. Never serialize their input.
        return await domain_error(
            request, DomainError(422, "VALIDATION_ERROR", "Dữ liệu chưa hợp lệ.")
        )

    @app.exception_handler(Exception)
    async def unexpected_error(request: Request, error: Exception) -> JSONResponse:
        return render_unexpected(request, error)
