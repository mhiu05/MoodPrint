"""Server-enforced policy for V3 orchestration (03 §4). Pure: no model, no database, no transcript.

A plan proposed by a model is never proof of anything. ``validate`` takes the plan and the live
grants read under the owner lock and returns the only decision the runtime acts on: which
specialists may be consulted (``Agent.as_tool``) or handed over to, and why others were not.
"""

from dataclasses import dataclass, field
from typing import Literal

from app.ai.orchestration.plan import OrchestrationPlan

POLICY_VERSION = "orchestration-v1"
SPECIALISTS: tuple[str, ...] = ("nhatky", "hoatdong")
EDGES: dict[tuple[str, str], str] = {
    ("consult", "nhatky"): "dieuphoi_consult_nhatky",
    ("consult", "hoatdong"): "dieuphoi_consult_hoatdong",
    ("handoff", "nhatky"): "dieuphoi_handoff_nhatky",
    ("handoff", "hoatdong"): "dieuphoi_handoff_hoatdong",
}
# What each edge may carry; anything else a plan asks for is dropped.
ALLOWED_DATA: dict[str, frozenset[str]] = {
    "dieuphoi_consult_nhatky": frozenset({"journal_entries", "mood_scores"}),
    "dieuphoi_consult_hoatdong": frozenset({"conversation_goal", "time_budget", "energy_hint"}),
    "dieuphoi_handoff_nhatky": frozenset({"latest_message", "journal_entries"}),
    "dieuphoi_handoff_hoatdong": frozenset({"latest_message"}),
}
READS_JOURNAL = frozenset({"dieuphoi_consult_nhatky"})
MIN_HANDOFF_CONFIDENCE = 0.55


@dataclass(frozen=True)
class Grants:
    """Live permission state read under the owner lock."""

    feature: bool
    eligible: bool
    edges: dict[str, int] = field(default_factory=dict)  # enabled edge -> permission version
    journal_context: bool = False


@dataclass(frozen=True)
class Signals:
    """Facts about the current message, computed by code (never by the planner)."""

    distress: bool
    journal_refused: bool


@dataclass(frozen=True)
class Counters:
    steps_today: int
    daily_cap: int
    budget_ratio: float | None
    budget_share: float
    seconds_remaining: float
    specialist_timeout: float
    capacity: bool = True
    max_specialists: int = 2
    min_primary_seconds: float = 8.0


@dataclass(frozen=True)
class Decision:
    workflow: Literal["direct", "consult", "handoff"]
    consult: tuple[str, ...] = ()
    handoff: str | None = None
    # specialist -> recordable reason (never 'distress' or a journal refusal)
    denied: dict[str, str] = field(default_factory=dict)
    versions: dict[str, int] = field(default_factory=dict)
    allowed_data: dict[str, frozenset[str]] = field(default_factory=dict)

    @property
    def delegates(self) -> bool:
        return self.workflow != "direct"


DIRECT = Decision("direct")


def _open(kind: str, specialist: str, grants: Grants, signals: Signals) -> str | None:
    """None when the edge is usable now, else the recordable reason ('' = silent refusal)."""
    edge = EDGES[(kind, specialist)]
    if edge not in grants.edges:
        return "edge_disabled"
    if edge in READS_JOURNAL:
        if signals.journal_refused:
            return ""
        if not grants.journal_context:
            return "journal_consent_off"
    return None


def available(grants: Grants, signals: Signals) -> dict[str, list[str]]:
    """Options the planner may choose from (closed values only)."""
    if not (grants.feature and grants.eligible) or signals.distress:
        return {"consult": [], "handoff": []}
    return {
        kind: [name for name in SPECIALISTS if _open(kind, name, grants, signals) is None]
        for kind in ("consult", "handoff")
    }


def _cost(count: int, counters: Counters) -> str | None:
    if counters.steps_today + count > counters.daily_cap:
        return "daily_cap"
    if counters.budget_ratio is not None and counters.budget_ratio >= counters.budget_share:
        return "budget"
    if counters.seconds_remaining - counters.specialist_timeout < counters.min_primary_seconds:
        return "time_budget"
    if not counters.capacity:
        return "capacity"
    return None


def validate(plan: OrchestrationPlan, grants: Grants, counters: Counters, signals: Signals) -> Decision:
    """Structure, then safety, then consent, then cost. The order is deliberate."""
    if not (grants.feature and grants.eligible) or signals.distress or plan.workflow == "direct":
        return DIRECT
    denied: dict[str, str] = {}
    if plan.workflow == "handoff":
        target = plan.handoff_target
        assert target is not None
        reason = _open("handoff", target, grants, signals)
        if reason is None and plan.confidence < MIN_HANDOFF_CONFIDENCE:
            reason = "low_confidence"
        if reason is None:
            reason = _cost(1, counters)
        if reason is not None:
            return Decision("direct", denied={target: reason} if reason else {})
        edge = EDGES[("handoff", target)]
        return Decision("handoff", handoff=target, versions={target: grants.edges[edge]},
                        allowed_data={target: ALLOWED_DATA[edge] & (set(plan.data_categories) | {"latest_message"})})
    approved: list[str] = []
    for specialist in plan.specialists[: counters.max_specialists]:
        reason = _open("consult", specialist, grants, signals)
        if reason is None:
            approved.append(specialist)
        elif reason:
            denied[specialist] = reason
    if approved and (reason := _cost(len(approved), counters)) is not None:
        # Over the daily cap by one: keep the first specialist only; any other limit stops all.
        if reason == "daily_cap" and _cost(1, counters) is None:
            denied[approved.pop()] = reason
        else:
            denied.update({name: reason for name in approved})
            approved = []
    if not approved:
        return Decision("direct", denied=denied)
    versions = {name: grants.edges[EDGES[("consult", name)]] for name in approved}
    allowed = {name: ALLOWED_DATA[EDGES[("consult", name)]] for name in approved}
    return Decision("consult", consult=tuple(approved), denied=denied, versions=versions, allowed_data=allowed)
