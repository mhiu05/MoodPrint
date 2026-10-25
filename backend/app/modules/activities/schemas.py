"""Activity API contracts (06 section 8). Views are always projected for one viewer."""

from datetime import datetime
from typing import Literal

from pydantic import Field

from app.contracts import DTO, VersionInput

KindName = Literal["icebreaker", "coop_quiz", "focus"]


class ActivityDefinitionDTO(DTO):
    kind: KindName
    definition_version: str
    title: str
    description: str
    estimated_minutes: int
    rounds: int | None = None
    focus_plans: list[list[int]] | None = None
    max_cycles: int | None = None


class FocusOptions(DTO):
    plan: list[int] = Field(default_factory=lambda: [25, 5], min_length=2, max_length=2)
    cycles: int = Field(default=1, ge=1, le=4)


class InviteInput(DTO):
    kind: KindName
    options: FocusOptions | None = None


class ResponseInput(VersionInput):
    round: int = Field(ge=1, le=10)
    choice: int | None = Field(default=None, ge=0, le=3)
    text: str | None = Field(default=None, max_length=140)
    skipped: bool = False


class ReadyInput(VersionInput):
    round: int = Field(ge=1, le=10)


class FeedbackInput(DTO):
    rating: Literal["liked", "neutral", "not_for_me"]


class ActivityItemView(DTO):
    id: str
    prompt: str
    options: list[str]
    allow_text: bool = False


class AnswerView(DTO):
    choice: int | None = None
    text: str | None = None
    skipped: bool = False


class RevealView(DTO):
    me: AnswerView | None = Field(default=None, serialization_alias="self")
    # "hidden" when the viewer skipped (reciprocal reveal); "skipped" when the peer did.
    peer: AnswerView | Literal["hidden", "skipped"] | None = None
    correct_index: int | None = None
    explanation: str | None = None
    points: int | None = None


class CurrentView(DTO):
    item: ActivityItemView
    self_response: AnswerView | None = None
    peer_submitted: bool = False
    reveal: RevealView | None = None


class HistoryRound(DTO):
    round: int
    item: ActivityItemView
    reveal: RevealView


class SelfView(DTO):
    accepted: bool
    ready_round: int
    joined: bool | None = None
    feedback_given: bool = False


class PeerView(DTO):
    accepted: bool
    ready_round: int
    joined: bool | None = None


class ProgressView(DTO):
    round: int
    total_rounds: int | None = None
    phase: str


class ScoreView(DTO):
    team: int
    max: int
    rounds: list[int]


class TimerView(DTO):
    phase: str
    cycle: int
    cycles: int
    plan: list[int]
    phase_ends_at: datetime | None = None
    paused_remaining_sec: int | None = None
    paused_by_self: bool | None = None
    self_present: bool
    peer_present: bool


class SummaryView(DTO):
    answered_together: int | None = None
    team_score: int | None = None
    max_score: int | None = None
    focus_minutes_self: int | None = None
    focus_minutes_peer: int | None = None
    focus_minutes_together: int | None = None


class ActivitySessionView(DTO):
    id: str
    connection_id: str
    kind: KindName
    definition_version: str
    state: str
    end_reason: str | None = None
    version: int
    role: Literal["inviter", "invitee"]
    created_at: datetime
    started_at: datetime | None = None
    ended_at: datetime | None = None
    expires_at: datetime | None = None
    server_time: datetime
    me: SelfView = Field(serialization_alias="self")
    peer: PeerView
    progress: ProgressView
    current: CurrentView | None = None
    history: list[HistoryRound] = Field(default_factory=list)
    score: ScoreView | None = None
    timer: TimerView | None = None
    summary: SummaryView | None = None
