"""Content-free service states and safe public failure messages."""

from typing import Literal

from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AuthenticationError,
    BadRequestError,
    NotFoundError,
    PermissionDeniedError,
    RateLimitError,
)
from sqlalchemy.exc import SQLAlchemyError

AiStatus = Literal[
    "disabled", "configuration_missing", "configuration_invalid", "ready", "test_provider"
]

FAILURE_MESSAGES = {
    "AI_PROVIDER_CONFIGURATION": "Dịch vụ AI chưa kết nối được với nhà cung cấp. Vui lòng thử lại sau khi dịch vụ được kiểm tra.",
    "AI_PROVIDER_RATE_LIMIT": "Nhà cung cấp AI đang giới hạn lượt dùng. Bạn hãy thử lại sau ít phút.",
    "AI_PROVIDER_UNAVAILABLE": "Chưa kết nối được nhà cung cấp AI. Bạn có thể thử lại sau.",
    "AI_TIMEOUT": "Trợ lý chưa phản hồi kịp. Bạn có thể thử lại sau.",
    "AI_STORAGE_UNAVAILABLE": "Chưa đồng bộ được cuộc trò chuyện. Hãy tải lại để kiểm tra trước khi gửi tiếp.",
    "AI_RUN_FAILED": "Chưa hoàn tất phản hồi. Bạn có thể tải lại rồi thử lại.",
}


def public_failure(error: Exception) -> dict[str, str]:
    if isinstance(
        error, (AuthenticationError, PermissionDeniedError, NotFoundError, BadRequestError)
    ):
        code = "AI_PROVIDER_CONFIGURATION"
    elif isinstance(error, RateLimitError):
        code = "AI_PROVIDER_RATE_LIMIT"
    elif isinstance(error, (APITimeoutError, TimeoutError)):
        code = "AI_TIMEOUT"
    elif isinstance(error, (APIConnectionError, APIStatusError)):
        code = "AI_PROVIDER_UNAVAILABLE"
    elif isinstance(error, SQLAlchemyError):
        code = "AI_STORAGE_UNAVAILABLE"
    else:
        code = "AI_RUN_FAILED"
    return {"code": code, "message": FAILURE_MESSAGES[code]}
