"""Roleplay context for one turn and the coach's structured feedback."""

from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict, Field

from moodprint_agent.roleplay.scenarios import Role


@dataclass(frozen=True, slots=True)
class RoleplayContext:
    """Everything the partner needs, rebuilt for every turn so the persona cannot drift."""

    role: Role
    scenario_key: str
    scenario_title: str
    scenario_context: str
    user_goal: str
    difficulty: int
    age_band: str | None = None
    case_summary: str | None = None  # only when the user opted in (use_case_context)
    safety_locked: bool = False  # a danger signal already ended the role for this session


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Rephrasing(_Frozen):
    original: str = Field(max_length=400)
    better: str = Field(max_length=400)
    why: str = Field(max_length=300)


class RoleplayFeedback(_Frozen):
    summary: str = Field(max_length=600)
    strengths: list[str] = Field(max_length=4)
    suggestions: list[str] = Field(max_length=4)
    rephrasings: list[Rephrasing] = Field(max_length=3)
    follow_ups: list[str] = Field(max_length=4)
    safety_note: str | None
