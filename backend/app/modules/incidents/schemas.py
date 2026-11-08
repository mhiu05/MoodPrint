from typing import Literal
from uuid import UUID

from moodprint_shared.contracts.base import FrozenDTO
from moodprint_shared.contracts.incidents import CaseStatus, EventCreate
from pydantic import Field, model_validator

from app.core.errors import ApiError


class EventWrite(EventCreate):
    @model_validator(mode="before")
    @classmethod
    def reject_client_ai_provenance(cls, data):
        if isinstance(data, EventCreate):
            data = data.model_dump()
        if isinstance(data, dict) and data.get("provenance", "user_entered") != "user_entered":
            raise ApiError(
                "forbidden",
                "Mốc mô phỏng hoặc AI chưa được hỗ trợ trong hồ sơ thật.",
                403,
                details={"reason": "fixture_not_allowed"},
            )
        return data


class CaseCreate(FrozenDTO):
    id: UUID
    title: str = Field(default="", max_length=120)
    template: Literal[
        "TPL-VERBAL",
        "TPL-THREAT",
        "TPL-EXCLUSION",
        "TPL-PHYSICAL",
        "TPL-IMAGE",
        "TPL-IMPERSONATION",
        "TPL-WITNESS",
        "TPL-FREE",
    ] = "TPL-FREE"
    perspective: Literal["self", "witness"] = "self"
    summary: str = ""
    category_tags: list[str] = Field(default_factory=list)
    impact_tags: list[str] = Field(default_factory=list)
    status: Literal["draft", "active"] = "draft"
    people: str = ""
    place: str = ""
    occurred_at: str = ""
    tried: str = ""
    trusted_person: str = ""
    first_event: EventWrite | None = None
    evidence_ids: list[UUID] = Field(default_factory=list)


class CasePatch(FrozenDTO):
    version: int = Field(ge=1)
    title: str | None = Field(default=None, max_length=120)
    template: (
        Literal[
            "TPL-VERBAL",
            "TPL-THREAT",
            "TPL-EXCLUSION",
            "TPL-PHYSICAL",
            "TPL-IMAGE",
            "TPL-IMPERSONATION",
            "TPL-WITNESS",
            "TPL-FREE",
        ]
        | None
    ) = None
    perspective: Literal["self", "witness"] | None = None
    summary: str | None = None
    category_tags: list[str] | None = None
    impact_tags: list[str] | None = None
    status: CaseStatus | None = None
    people: str | None = None
    place: str | None = None
    occurred_at: str | None = None
    tried: str | None = None
    trusted_person: str | None = None

    @model_validator(mode="after")
    def reject_null(self):
        if any(getattr(self, key) is None for key in self.model_fields_set):
            raise ValueError("Case fields cannot be null")
        return self
