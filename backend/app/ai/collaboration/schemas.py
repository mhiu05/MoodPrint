"""Public DTOs of the sharing settings API (phase-2/05 §2). Descriptions live in the frontend."""

from typing import Literal

from pydantic import Field

from app.ai.collaboration.contracts import Edge
from app.contracts import DTO, BotId

V3Edge = Literal[
    "dieuphoi_consult_nhatky", "dieuphoi_consult_hoatdong", "dieuphoi_handoff_nhatky", "dieuphoi_handoff_hoatdong",
]

SharingReason = Literal["feature_unavailable", "ineligible_account", "journal_context_off"]


class SharingEdgeView(DTO):
    edge: Edge | V3Edge
    # V3: 'consult' = the specialist helps Điều phối answer; 'handoff' = it answers you directly.
    kind: Literal["consult", "handoff"] = "consult"
    requester: BotId
    specialist: BotId
    enabled: bool
    version: int = Field(ge=0)
    requires: list[Literal["journal_context"]]
    available: bool
    reason: SharingReason | None = None


class SharingView(DTO):
    available: bool
    edges: list[SharingEdgeView]


class SharingInput(DTO):
    enabled: bool
    expected_version: int = Field(ge=0)
    policy_version: Literal["sharing-v1"]
