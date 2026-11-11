"""Public representation of practice sessions. Nothing here is real-person data."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field
from safevoice_shared.contracts.base import FrozenDTO

Role = Literal["teacher", "parent", "trusted_adult"]


class RoleplayCreate(FrozenDTO):
    id: UUID
    role: Role
    scenario_key: str = Field(min_length=1, max_length=80)
    user_goal: str = Field(default="", max_length=300)
    difficulty: int = Field(default=1, ge=1, le=3)
    linked_case_id: UUID | None = None
    use_case_context: bool = False


class ScenarioRead(FrozenDTO):
    key: str
    role: Role
    title: str
    context: str
    default_goal: str


class RephrasingRead(FrozenDTO):
    original: str
    better: str
    why: str


class FeedbackRead(FrozenDTO):
    summary: str
    strengths: list[str]
    suggestions: list[str]
    rephrasings: list[RephrasingRead]
    follow_ups: list[str]
    safety_note: str | None


class RoleplayRead(FrozenDTO):
    id: UUID
    conversation_id: UUID
    role: Role
    scenario_key: str
    scenario_title: str
    scenario_context: str
    user_goal: str
    difficulty: int
    use_case_context: bool
    linked_case_id: UUID | None
    status: Literal["active", "completed", "abandoned"]
    turn_count: int
    max_turns: int
    safety_locked: bool
    feedback: FeedbackRead | None
    created_at: datetime
    completed_at: datetime | None
