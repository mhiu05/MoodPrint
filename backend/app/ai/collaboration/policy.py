"""Deny-by-default edge matrix and deterministic rules R1–R4 (phase-2/02 §3, phase-2/03 §1).

Everything here is a pure function of values the coordinator already authorized: no model,
no database, no transcript. A model never chooses whom to consult or what to forward.
"""

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Literal

from app.ai.collaboration.contracts import (
    AllowedContext,
    DenyReason,
    Edge,
    InputSchema,
    InterestTag,
    JournalExcerpt,
    Need,
    RuleId,
    TimeBudget,
    TimeOfDay,
)
from app.ai.proactive.safety import distress_screen
from app.contracts import BotId

POLICY_VERSION = "collaboration-v1"
SHARING_POLICY_VERSION = "sharing-v1"
MAX_DEPTH = 1


@dataclass(frozen=True)
class EdgeSpec:
    edge: Edge
    requester: BotId
    specialist: BotId
    rules: tuple[RuleId, ...]
    input_schema: InputSchema
    # The specialist reads the user's saved journal entries (only this edge).
    reads_journal: bool = False


EDGES: dict[Edge, EdgeSpec] = {
    "nhip_energy_for_rure": EdgeSpec(
        "nhip_energy_for_rure", "rure", "nhip", ("R1", "R2"), "energy-hint-in-v1", reads_journal=True
    ),
    "nhip_habit_for_may": EdgeSpec("nhip_habit_for_may", "may", "nhip", ("R3",), "tiny-habit-in-v1"),
    "rure_activity_for_guong": EdgeSpec(
        "rure_activity_for_guong", "guong", "rure", ("R4",), "interest-activity-in-v1"
    ),
}
# Cầu Nối has no edge in either direction: social discovery never sees mood, journal or chat.


def edge_for(requester: str, specialist: str) -> EdgeSpec | None:
    for spec in EDGES.values():
        if (spec.requester, spec.specialist) == (requester, specialist):
            return spec
    return None


# Backend-rendered collaboration lines (phase-2/04 §3). The model never writes or edits these.
TEMPLATES: dict[tuple[Edge, RuleId], str] = {
    ("nhip_energy_for_rure", "R2"): (
        "Nhịp đã gợi ý một hoạt động nhẹ nhàng. Rủ Rê đã dựa vào đó để chuẩn bị thử thách hôm nay."
    ),
    ("nhip_energy_for_rure", "R1"): (
        "Nhịp đã gợi ý mức năng lượng phù hợp với bạn. Rủ Rê đã dựa vào đó để chọn hoạt động này."
    ),
    ("nhip_habit_for_may", "R3"): "Nhịp đã gợi ý một thói quen nhỏ. Mây đã dựa vào đó để trả lời bạn.",
    ("rure_activity_for_guong", "R4"): (
        "Rủ Rê đã gợi ý một hoạt động. Gương đã dựa vào đó để trả lời bạn."
    ),
}

# Only operational reasons are stored as denied receipts; a never-enabled edge or a distress
# match leaves no trace at all (the database CHECK refuses them too).
RECORDED_DENIALS: frozenset[str] = frozenset(
    {"journal_consent_off", "no_data", "daily_cap", "budget", "time_budget", "capacity"}
)


def fold(text: str) -> str:
    """Lowercase, đ→d, accents removed (same folding as ``conversation.current_text``)."""
    lowered = text.lower().replace("đ", "d")
    return "".join(c for c in unicodedata.normalize("NFD", lowered) if not unicodedata.combining(c))


# R1: the current message asks for something suited to the user's state today.
_PERSONAL = re.compile(
    r"nhe nhang|hop voi (?:minh|toi|em|to)|dang met|it nang luong|hop tam trang|het nang luong"
)
# R3: a habit need the user just named (folded). "ngủ" alone is never used: "ngu" is ambiguous.
_NEEDS: tuple[tuple[Need, re.Pattern[str]], ...] = (
    ("sleep", re.compile(r"\bmat ngu\b|\bkho ngu\b|\bthieu ngu\b|\bgiac ngu\b|ngu khong ngon|khong ngu duoc")),
    ("stress", re.compile(r"\bcang thang\b|\bap luc\b|\bstress")),
    ("focus", re.compile(r"\btap trung\b|\bxao nhang\b")),
    ("energy", re.compile(r"\bue oai\b|thieu nang luong")),
)
# R4: the user asks what to try/do; the interest comes from a closed taxonomy.
_WANTS_ACTIVITY = re.compile(r"muon thu|nen thu|thu lam|lam gi|goi y (?:hoat dong|viec|mot)|bat dau tu dau")
# Accented forms where folding would collide ("vẽ"/"về", "hát"/"hạt", "đàn"/"dan").
_INTERESTS: tuple[tuple[InterestTag, re.Pattern[str], bool], ...] = (
    ("drawing", re.compile(r"\bvẽ\b|hội họa|tô màu|ký họa|phác thảo"), True),
    ("reading", re.compile(r"\bdoc sach\b|\btieu thuyet\b|\bdoc truyen\b"), False),
    ("music", re.compile(r"âm nhạc|\bhát\b|\bđàn\b|guitar|piano|nghe nhạc"), True),
    ("cooking", re.compile(r"\bnau an\b|\blam banh\b|\bnau\b"), False),
    ("sport", re.compile(r"\bthe thao\b|\bbong da\b|\bchay bo\b|\bboi loi\b|\bcau long\b|\byoga\b|\bgym\b"), False),
    ("nature", re.compile(r"\bthien nhien\b|\btrong cay\b|\bleo nui\b|\bcam trai\b|\bdi bo\b"), False),
    ("games", re.compile(r"\btro choi\b|\bgame\b|\bco vua\b"), False),
    ("writing", re.compile(r"\bviet lach\b|\blam tho\b|\bsang tac\b|\bviet truyen\b|\bviet\b"), False),
    ("languages", re.compile(r"\bngoai ngu\b|\btieng (?:anh|nhat|han|trung|phap)\b|\bhoc tieng\b"), False),
    ("technology", re.compile(r"\blap trinh\b|\bcong nghe\b|\bcode\b|\bmay tinh\b"), False),
)
_MINUTES = re.compile(r"\b(5|10|15)\s*phut\b")


def need_of(folded: str) -> Need | None:
    return next((need for need, pattern in _NEEDS if pattern.search(folded)), None)


def interest_of(text: str) -> InterestTag | None:
    accented, folded = unicodedata.normalize("NFC", text.lower()), fold(text)
    return next(
        (tag for tag, pattern, raw in _INTERESTS if pattern.search(accented if raw else folded)), None
    )


def time_budget_of(folded: str) -> TimeBudget:
    match = _MINUTES.search(folded)
    return int(match.group(1)) if match else 10  # type: ignore[return-value]


def time_of_day(hour: int) -> TimeOfDay:
    if 5 <= hour < 11:
        return "morning"
    if 11 <= hour < 17:
        return "afternoon"
    if 17 <= hour < 22:
        return "evening"
    return "night"


@dataclass(frozen=True)
class Signals:
    """Values already authorized for the primary turn. ``text`` is only the current message."""

    origin: Literal["chat", "proactive"]
    bot_id: str
    intent: str = "conversation"
    text: str = ""
    local_hour: int = 12
    slot: str | None = None
    depth: int = 0
    already_consulted: bool = False


@dataclass(frozen=True)
class Match:
    """A rule whose content conditions hold. Carries only closed values, never user text."""

    rule_id: RuleId
    edge: Edge
    need: Need | None = None
    interest_tag: InterestTag | None = None
    time_budget_minutes: TimeBudget | None = None
    time_of_day: TimeOfDay | None = None


def match_rule(signals: Signals) -> Match | None:
    """First matching rule wins (R1..R4); at most one specialist per turn. No I/O."""
    folded = fold(signals.text)
    if signals.origin == "proactive":
        if signals.bot_id == "rure" and signals.slot == "morning":
            return Match("R2", "nhip_energy_for_rure")
        return None
    if signals.bot_id == "rure" and signals.intent == "activity" and _PERSONAL.search(folded):
        return Match("R1", "nhip_energy_for_rure")
    # Deviation (recorded): conversation_intent() classifies the canonical UC-3 message
    # "mấy hôm nay mất ngủ" as 'conversation', so R3 also accepts it; it never fires when the
    # user asked only to be listened to, or for analysis.
    if signals.bot_id == "may" and signals.intent in ("support", "practical", "conversation"):
        need = need_of(folded)
        if need is not None:
            return Match("R3", "nhip_habit_for_may", need=need, time_of_day=time_of_day(signals.local_hour))
    if signals.bot_id == "guong" and signals.intent == "reflection" and _WANTS_ACTIVITY.search(folded):
        tag = interest_of(signals.text)
        if tag is not None:
            return Match("R4", "rure_activity_for_guong", interest_tag=tag,
                         time_budget_minutes=time_budget_of(folded))
    return None


@dataclass(frozen=True)
class Grants:
    """Live permission state read under the owner lock."""

    feature_enabled: bool
    eligible: bool
    enabled_edges: dict[str, int] = field(default_factory=dict)  # edge -> permission version
    journal_context_enabled: bool = False


@dataclass(frozen=True)
class Counters:
    collaborations_today: int = 0
    daily_cap: int = 10
    budget_ratio: float | None = None  # spent / daily budget; None when no budget is configured
    budget_share: float = 0.7
    seconds_remaining: float = 30.0
    specialist_timeout: float = 8.0
    min_primary_seconds: float = 15.0
    recent_entries: int = 0
    capacity_available: bool = True


@dataclass(frozen=True)
class Decision:
    allowed: bool
    reason: DenyReason
    match: Match | None = None
    permission_version: int = 0

    @property
    def recorded(self) -> bool:
        """Whether a denied decision leaves a content-free receipt."""
        return not self.allowed and self.reason in RECORDED_DENIALS


def evaluate(signals: Signals, match: Match | None, grants: Grants, counters: Counters) -> Decision:
    """Rule G of phase-2/02 §3 plus the matched rule's data condition. Order is deliberate:
    structural limits, then safety, then consent, then data, then cost."""
    if match is None:
        return Decision(False, "edge_disabled")
    if signals.depth >= MAX_DEPTH:
        return Decision(False, "depth", match)
    if signals.already_consulted:
        return Decision(False, "already_consulted", match)
    if signals.origin == "chat" and distress_screen([signals.text]):
        return Decision(False, "distress", match)
    if not grants.feature_enabled:
        return Decision(False, "feature_off", match)
    if not grants.eligible:
        return Decision(False, "ineligible_account", match)
    version = grants.enabled_edges.get(match.edge)
    if version is None or edge_for(EDGES[match.edge].requester, EDGES[match.edge].specialist) is None:
        return Decision(False, "edge_disabled", match)
    if EDGES[match.edge].reads_journal:
        if not grants.journal_context_enabled:
            return Decision(False, "journal_consent_off", match, version)
        if counters.recent_entries < 1:
            return Decision(False, "no_data", match, version)
    if counters.collaborations_today >= counters.daily_cap:
        return Decision(False, "daily_cap", match, version)
    if counters.budget_ratio is not None and counters.budget_ratio >= counters.budget_share:
        return Decision(False, "budget", match, version)
    if counters.seconds_remaining - counters.specialist_timeout < counters.min_primary_seconds:
        return Decision(False, "time_budget", match, version)
    if not counters.capacity_available:
        return Decision(False, "capacity", match, version)
    return Decision(True, "ok", match, version)


def allowed_context(match: Match, *, journal: tuple[JournalExcerpt, ...] = ()) -> AllowedContext:
    """The only builder of specialist input. It takes closed values and authorized excerpts —
    never a transcript, a message or a memory."""
    spec = EDGES[match.edge]
    if spec.edge == "nhip_energy_for_rure":
        return AllowedContext(schema=spec.input_schema, journal=journal)
    if journal:
        raise ValueError("only the energy edge may carry journal excerpts")
    if spec.edge == "nhip_habit_for_may":
        return AllowedContext(schema=spec.input_schema, need=match.need, time_of_day=match.time_of_day)
    return AllowedContext(
        schema=spec.input_schema, interest_tag=match.interest_tag,
        time_budget_minutes=match.time_budget_minutes,
    )


def summary_for(edge: str, rule_id: str) -> str | None:
    return TEMPLATES.get((edge, rule_id))  # type: ignore[arg-type]
