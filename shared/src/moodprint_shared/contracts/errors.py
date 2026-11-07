from typing import Any, ClassVar

from pydantic import Field, JsonValue

from .base import FrozenDTO


class DomainError(Exception):
    code: str = "internal_error"
    status_code: int = 500
    default_message: ClassVar[str] = "Đã có lỗi xảy ra."

    def __init__(
        self, message: str | None = None, *, details: dict[str, Any] | None = None
    ) -> None:
        self.message = message or self.default_message
        self.details = details or {}
        super().__init__(self.message)


class NotFound(DomainError):
    code = "not_found"
    status_code = 404
    default_message = "Không tìm thấy dữ liệu."


class Forbidden(DomainError):
    code = "forbidden"
    status_code = 403
    default_message = "Bạn không có quyền thực hiện thao tác này."


class VersionConflict(DomainError):
    code = "version_conflict"
    status_code = 409
    default_message = "Dữ liệu đã thay đổi."


class RunInProgress(DomainError):
    code = "run_in_progress"
    status_code = 409
    default_message = "Cuộc trò chuyện đang có lượt xử lý."


class KnowledgeTimeout(DomainError):
    code = "knowledge_timeout"
    status_code = 503
    default_message = "Tra cứu đã quá thời gian."


class KnowledgeUnavailable(DomainError):
    code = "knowledge_unavailable"
    status_code = 503
    default_message = "Chưa thể tra cứu tri thức."


class QuotaExceeded(DomainError):
    code = "quota_exceeded"
    status_code = 429
    default_message = "Đã vượt dung lượng cho phép."


class ErrorBody(FrozenDTO):
    code: str
    message: str
    request_id: str
    details: dict[str, JsonValue] = Field(default_factory=dict)


class ErrorEnvelope(FrozenDTO):
    error: ErrorBody
