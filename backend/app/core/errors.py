from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.contracts import ApiError, ErrorDetail


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
    ):
        self.status, self.code, self.message, self.retryable = status, code, message, retryable
        self.current_session_id, self.retry_after = current_session_id, retry_after
        super().__init__(code)


def install_errors(app: FastAPI) -> None:
    @app.exception_handler(DomainError)
    async def domain_error(request: Request, error: DomainError) -> JSONResponse:
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
        return JSONResponse(
            payload.model_dump(by_alias=True, exclude_none=True),
            status_code=error.status,
            headers=headers,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, error: RequestValidationError) -> JSONResponse:
        # Pydantic errors can contain submitted passwords/text. Never serialize their input.
        return await domain_error(
            request, DomainError(422, "VALIDATION_ERROR", "Dữ liệu chưa hợp lệ.")
        )

    @app.exception_handler(Exception)
    async def unexpected_error(request: Request, error: Exception) -> JSONResponse:
        return await domain_error(
            request,
            DomainError(500, "INTERNAL_ERROR", "Chưa hoàn tất yêu cầu. Vui lòng thử lại.", True),
        )
