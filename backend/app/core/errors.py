from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.contracts import ApiError, ErrorDetail


class DomainError(Exception):
    def __init__(self, status: int, code: str, message: str, retryable: bool = False):
        self.status, self.code, self.message, self.retryable = status, code, message, retryable
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
            )
        )
        return JSONResponse(
            payload.model_dump(by_alias=True),
            status_code=error.status,
            headers={"Cache-Control": "no-store"},
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
