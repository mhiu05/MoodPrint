from datetime import date, datetime
from typing import Literal, Protocol
from uuid import UUID

from pydantic import Field, model_validator

from .auth import AuthContext
from .base import FrozenDTO
from .paging import Page, PageQuery

CaseStatus = Literal["draft", "active", "monitoring", "closed"]
TimePrecision = Literal["exact", "day", "week", "unknown"]
EventProvenance = Literal["user_entered", "ai_extracted", "user_confirmed"]


class CaseQuery(PageQuery):
    status: CaseStatus | None = None
    q: str | None = None
    sort: Literal["updated", "title"] = "updated"


class EventCreate(FrozenDTO):
    id: UUID
    when: str = ""
    time_precision: TimePrecision = "unknown"
    place: str = ""
    description: str = Field(min_length=1)
    provenance: EventProvenance = "user_entered"
    evidence_ids: list[UUID] = Field(default_factory=list[UUID])
    needs_review: bool = False

    @model_validator(mode="after")
    def check_time(self) -> "EventCreate":
        if self.time_precision == "unknown":
            if self.when:
                raise ValueError("unknown time must be empty")
        elif self.time_precision in {"day", "week"}:
            date.fromisoformat(self.when)
        else:
            parsed = datetime.fromisoformat(self.when.replace("Z", "+00:00"))
            if "T" not in self.when or parsed.tzinfo is None:
                raise ValueError("exact time requires a timezone-aware ISO datetime")
        return self


class TimelineEvent(EventCreate):
    case_id: UUID


class PlanProgress(FrozenDTO):
    done: int = Field(ge=0)
    total: int = Field(ge=0)


class CaseSummary(FrozenDTO):
    id: UUID
    owner_id: UUID
    title: str
    status: CaseStatus
    category_tags: list[str] = Field(default_factory=list[str])
    plan_progress: PlanProgress | None = None
    version: int = Field(default=1, ge=1)
    created_at: datetime
    updated_at: datetime


class CaseDetail(CaseSummary):
    template: str
    perspective: Literal["self", "witness"]
    summary: str
    impact_tags: list[str] = Field(default_factory=list[str])
    people: str = ""
    place: str = ""
    occurred_at: str = ""
    tried: str = ""
    trusted_person: str = ""
    events: list[TimelineEvent] = Field(default_factory=list[TimelineEvent])
    evidence_ids: list[UUID] = Field(default_factory=list[UUID])
    linked_plan_id: UUID | None = None


class IncidentService(Protocol):
    async def list_cases(self, auth: AuthContext, query: CaseQuery) -> Page[CaseSummary]: ...
    async def get_case(self, auth: AuthContext, case_id: UUID) -> CaseDetail: ...
    async def add_event(
        self, auth: AuthContext, case_id: UUID, data: EventCreate
    ) -> TimelineEvent: ...
