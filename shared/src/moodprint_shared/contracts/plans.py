from datetime import date, datetime
from typing import Literal, Protocol
from uuid import UUID

from pydantic import Field

from .auth import AuthContext
from .base import FrozenDTO

ItemStatus = Literal["not_started", "doing", "done"]


class PlanItem(FrozenDTO):
    id: UUID
    label: str = Field(min_length=1)
    status: ItemStatus = "not_started"
    notes: str = ""
    priority: Literal["high", "normal"] = "normal"
    reason: str = ""


class PlanUpsert(FrozenDTO):
    id: UUID
    goal: str = ""
    chosen_option_id: str = ""
    status: Literal["draft", "active", "paused", "completed"] = "draft"
    next_review_date: date | None = None
    outcome_notes: str = ""
    items: list[PlanItem] = Field(default_factory=list[PlanItem])


class ActionPlan(PlanUpsert):
    case_id: UUID
    owner_id: UUID
    version: int = Field(default=1, ge=1)
    created_at: datetime
    updated_at: datetime


class ActionPlanService(Protocol):
    async def get_for_case(self, auth: AuthContext, case_id: UUID) -> ActionPlan | None: ...
    async def upsert(
        self, auth: AuthContext, case_id: UUID, data: PlanUpsert, *, expected_version: int | None
    ) -> ActionPlan: ...
    async def set_item_status(
        self, auth: AuthContext, plan_id: UUID, item_id: UUID, status: ItemStatus
    ) -> ActionPlan: ...
