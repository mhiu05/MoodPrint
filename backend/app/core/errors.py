from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from moodprint_shared.contracts.errors import DomainError
from starlette.exceptions import HTTPException


class ApiError(DomainError):
    def __init__(self, code: str, message: str, status_code: int, *, details=None):
        super().__init__(message, details=details)
        self.code = code
        self.status_code = status_code


def envelope(request: Request, code: str, message: str, status: int, details=None):
    request_id = getattr(request.state, "request_id", "")
    return JSONResponse(
        status_code=status,
        content={
            "error": {
                "code": code,
                "message": message,
                "requestId": request_id,
                "details": details or {},
            }
        },
        headers={"X-Request-ID": request_id},
    )


def register_handlers(app: FastAPI) -> None:
    @app.exception_handler(DomainError)
    async def domain_error(request: Request, error: DomainError):
        response = envelope(request, error.code, error.message, error.status_code, error.details)
        if error.code == "rate_limited":
            response.headers["Retry-After"] = "60"
        return response

    @app.exception_handler(HTTPException)
    async def http_error(request: Request, error: HTTPException):
        code = {401: "unauthenticated", 403: "forbidden", 404: "not_found"}.get(
            error.status_code, "invalid_request"
        )
        return envelope(request, code, "Không thể thực hiện yêu cầu này.", error.status_code)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, error: RequestValidationError):
        fields = [
            {"field": ".".join(map(str, e["loc"])), "type": e["type"]} for e in error.errors()
        ]
        return envelope(
            request, "validation_failed", "Vui lòng kiểm tra dữ liệu nhập.", 422, {"fields": fields}
        )

    @app.exception_handler(Exception)
    async def unexpected_error(request: Request, error: Exception):
        return envelope(request, "internal_error", "Có lỗi xảy ra. Vui lòng thử lại.", 500)
