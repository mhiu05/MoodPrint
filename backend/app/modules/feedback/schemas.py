"""Feedback contracts (camelCase, unknown fields rejected, no identity or attachment fields)."""

from datetime import date, datetime
from typing import Literal, get_args
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from app.contracts import DTO

__all__ = [
    "CATEGORY_ORDER",
    "Category",
    "Context",
    "FeedbackAdminView",
    "FeedbackFilters",
    "FeedbackInput",
    "FeedbackPage",
    "FeedbackReceipt",
    "FeedbackStatusInput",
    "FeedbackSubmissionState",
    "FeedbackSummary",
    "Status",
]

Category = Literal[
    "ease_of_use",
    "ai_quality",
    "interface",
    "performance",
    "bug",
    "missing_feature",
    "privacy_trust",
    "other",
]
Context = Literal["general", "assistants", "mood", "memory", "privacy", "activities", "trial_end"]
Status = Literal["new", "reviewed", "planned", "resolved", "spam"]
AccountKind = Literal["guest", "registered"]

CATEGORY_ORDER: tuple[str, ...] = get_args(Category)
COMMENT_LIMIT = 1000
MAX_WINDOW_DAYS = 180


def _forbidden_character(ch: str) -> bool:
    code = ord(ch)
    if ch in "\t\n\r":
        return False
    # C0 controls (including NUL), DEL, C1 controls and lone surrogates (never valid UTF-8 text).
    return code < 0x20 or 0x7F <= code <= 0x9F or 0xD800 <= code <= 0xDFFF


class FeedbackInput(DTO):
    """A required 1-5 rating; categories, comment and context are optional and never identifying."""

    rating: int = Field(strict=True, ge=1, le=5)
    categories: list[Category] = Field(default_factory=list, max_length=len(CATEGORY_ORDER))
    comment: str | None = None
    context: Context = "general"
    disclosure_version: Literal["feedback-v1"]

    @field_validator("categories")
    @classmethod
    def distinct_in_canonical_order(cls, value: list[str]) -> list[str]:
        # A repeated code is a client bug: refuse it rather than silently deduplicating.
        if len(set(value)) != len(value):
            raise ValueError("Mỗi nhóm chỉ được chọn một lần.")
        return sorted(value, key=CATEGORY_ORDER.index)

    @field_validator("comment")
    @classmethod
    def normalized_comment(cls, value: str | None) -> str | None:
        if value is None:
            return None
        # The limit counts code points before trimming as well as after, so padding cannot hide an
        # oversized body and an emoji counts once.
        if len(value) > COMMENT_LIMIT:
            raise ValueError("Góp ý tối đa 1000 ký tự.")
        if any(_forbidden_character(ch) for ch in value):
            raise ValueError("Góp ý chứa ký tự không được hỗ trợ.")
        trimmed = value.strip()
        return trimmed or None


class FeedbackReceipt(DTO):
    feedback_id: UUID
    created_at: datetime
    status: Literal["received"] = "received"


class FeedbackSubmissionState(DTO):
    """Own receipt existence only; no content and no review status."""

    submitted: bool
    last_submitted_at: datetime | None


class FeedbackAdminView(DTO):
    id: UUID
    rating: int
    categories: list[Category]
    comment: str | None
    app_version: str
    context: Context
    account_kind: AccountKind
    disclosure_version: str
    created_at: datetime
    status: Status
    version: int
    reviewed_at: datetime | None


class FeedbackPage(DTO):
    items: list[FeedbackAdminView]
    next_cursor: str | None


class FeedbackStatusInput(DTO):
    status: Status
    expected_version: int = Field(ge=1, strict=True)


class FeedbackFilters(DTO):
    """Shared by the list and the summary so both always describe the same cohort."""

    from_date: date | None = None
    to_date: date | None = None
    app_version: str | None = Field(default=None, min_length=1, max_length=64)
    account_kind: AccountKind | None = None
    rating: int | None = Field(default=None, ge=1, le=5)
    status: Status | None = None
    category: Category | None = None
    include_spam: bool = False

    @model_validator(mode="after")
    def bounded_window(self) -> "FeedbackFilters":
        start, end = self.from_date, self.to_date
        if start and end:
            if start > end:
                raise ValueError("Ngày bắt đầu phải trước hoặc bằng ngày kết thúc.")
            if (end - start).days + 1 > MAX_WINDOW_DAYS:
                raise ValueError("Khoảng thời gian tối đa 180 ngày.")
        return self


class DateBucket(DTO):
    date: str
    count: int
    mean_rating: float | None


class VersionBucket(DTO):
    app_version: str
    count: int
    mean_rating: float | None


class AccountKindCounts(DTO):
    guest: int
    registered: int


class FeedbackSummary(DTO):
    count: int
    mean_rating: float | None
    rating_counts: dict[Literal["1", "2", "3", "4", "5"], int]
    category_counts: dict[Category, int]
    account_kind_counts: AccountKindCounts
    by_date: list[DateBucket]
    by_version: list[VersionBucket]
