"""Ephemeral, server-bound mood evidence and deterministic analytical claims.

Nothing here is conversation memory. The public AiOutput/SSE schema is unchanged.
The model chooses a focus and an optional next step, never numerical claims.
"""

import json
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict

from app.ai.schemas import AiOutput
from app.core.errors import DomainError

EVIDENCE_POLICY = "mood-evidence-v1"


class MoodAnalysisPlan(BaseModel):
    """Private SDK output; only backend-authored claims reach the public response."""

    model_config = ConfigDict(extra="forbid")
    focus: Literal["overview", "recorded_days", "comparison", "limits"]
    next_step: Literal["none", "reflect", "record", "small_step"]
    detail: Literal["standard", "brief"] = "standard"
    include_mean: bool = True


@dataclass(frozen=True)
class MoodObservation:
    local_date: date
    value: int
    revision: int


@dataclass(frozen=True)
class EvidenceEnvelope:
    id: UUID
    owner_id: UUID
    run_id: UUID
    data_version: int
    from_date: date
    to_date: date
    retrieved_at: datetime
    expires_at: datetime
    observations: tuple[MoodObservation, ...]
    kind: Literal["mood_scores"] = "mood_scores"
    status: Literal["retrieved"] = "retrieved"
    reuse: Literal["current_run_only"] = "current_run_only"

    @classmethod
    def from_summary(cls, summary, run, *, expires_at: datetime):
        revisions = {row["localDate"]: row["version"] for row in summary["sourceVersions"]}
        return cls(
            id=uuid4(), owner_id=run.actor.user_id, run_id=run.id,
            data_version=run.data_version, from_date=run.mood_scope.from_date,
            to_date=run.mood_scope.to_date, retrieved_at=datetime.now(UTC),
            expires_at=expires_at,
            observations=tuple(
                MoodObservation(date.fromisoformat(row["localDate"]), row["value"], revisions[row["localDate"]])
                for row in summary["buckets"] if row["value"] is not None
            ),
        )

    @property
    def selected_days(self) -> int:
        return (self.to_date - self.from_date).days + 1

    @property
    def mean(self) -> float | None:
        return sum(row.value for row in self.observations) / len(self.observations) if self.observations else None

    def model_view(self) -> dict:
        days = {row.local_date.isoformat() for row in self.observations}
        return {
            "evidenceId": str(self.id), "kind": self.kind, "retrievalStatus": self.status,
            "authorizedRange": {"from": str(self.from_date), "to": str(self.to_date)},
            "retrievedAt": self.retrieved_at.isoformat(),
            "expiresAt": self.expires_at.isoformat(), "reuse": self.reuse,
            "statistics": {"recordedDays": len(days), "selectedDays": self.selected_days,
                           "missingDays": self.selected_days - len(days), "mean": self.mean},
            "capabilities": {"description": bool(days), "observation": len(days) >= 2,
                             "inference": False, "inferenceMethod": None},
            "sourceRevisions": [{"localDate": str(row.local_date), "revision": row.revision} for row in self.observations],
        }

    def assert_current(self, run) -> None:
        if (
            self.owner_id != run.actor.user_id or self.run_id != run.id
            or self.data_version != run.data_version or run.mood_scope is None
            or self.from_date != run.mood_scope.from_date or self.to_date != run.mood_scope.to_date
            or datetime.now(UTC) >= self.expires_at or run.cancel_requested or run.terminal
        ):
            raise DomainError(409, "EVIDENCE_INVALIDATED", "Dữ liệu của lượt này không còn được phép sử dụng.")


def render_mood_analysis(plan: MoodAnalysisPlan, run) -> AiOutput:
    evidence = run.mood_evidence
    if evidence is None:
        raise DomainError(409, "MOOD_EVIDENCE_REQUIRED", "Chưa đọc được thống kê cho lượt này. Bạn có thể chia sẻ lại khoảng ngày.")
    evidence.assert_current(run)
    rows = evidence.observations
    selected = evidence.selected_days
    count = len(rows)
    parts = [f"Trong khoảng {evidence.from_date:%d/%m/%Y}–{evidence.to_date:%d/%m/%Y}, bạn có {count}/{selected} ngày ghi tâm trạng."]
    if not rows:
        parts.append("Chưa có bản ghi trong khoảng đã chọn. Điều này không cho biết tâm trạng của bạn trong những ngày đó.")
    else:
        mean = format(evidence.mean, ".2f").rstrip("0").rstrip(".").replace(".", ",")
        if plan.include_mean:
            parts.append(f"Điểm trung bình của các ngày đã ghi là {mean}/5.")
        if plan.focus in ("overview", "recorded_days") and plan.detail == "standard":
            parts.append("Các điểm đã ghi: " + "; ".join(f"{row.local_date:%d/%m}: {row.value}/5" for row in rows) + ".")
        elif plan.focus == 'recorded_days':
            parts.append('Các lần ghi gần nhất: ' + '; '.join(f'{row.local_date:%d/%m}: {row.value}/5' for row in rows[-3:]) + '.')
        if len(rows) >= 2 and plan.focus != "recorded_days":
            first, last = rows[0], rows[-1]
            delta = last.value - first.value
            comparison = f"{'cao' if delta > 0 else 'thấp'} hơn {abs(delta)} điểm" if delta else "bằng nhau"
            parts.append(f"So với {first.local_date:%d/%m} ({first.value}/5), điểm {last.local_date:%d/%m} ({last.value}/5) {comparison}. Đây là so sánh hai lần ghi, chưa phải xu hướng của cả khoảng ngày.")
        elif len(rows) == 1:
            parts.append("Một lần ghi cho biết một thời điểm; chưa có lần ghi khác để so sánh.")
        if selected > count:
            parts.append(f"{selected - count} ngày chưa có bản ghi được để trống, không tính thành điểm thấp.")
        if plan.focus == "limits" or (len(rows) > 2 and plan.detail == "standard"):
            parts.append("Các điểm tự ghi mô tả những thời điểm đã ghi; chưa có phương pháp suy luận xu hướng được kiểm chứng và không cho biết nguyên nhân.")
    suggestions = {
        "none": "",
        "reflect": "Bạn có thể nhìn lại điều gì khác nhau giữa những lần đã ghi, nếu thấy hữu ích.",
        "record": "Bạn có thể ghi thêm khi muốn; không cần điền đoán những ngày đã bỏ qua.",
        "small_step": "Nếu muốn thử một bước nhẹ, hãy dành một lúc nghỉ rồi tự xem mình cảm thấy thế nào.",
    }
    if suggestions[plan.next_step]:
        parts.append(suggestions[plan.next_step])
    return AiOutput(text="\n\n".join(parts), cards=[])


def source_instructions(context, bot_id: str = "nhip", *, mood_analysis: bool = True) -> str:
    # Static historical prompt evals have no domain runtime and retain frozen inputs.
    if not hasattr(context, "sources"):
        return ""
    sources = getattr(context, "sources", {})
    common = """
Runtime continuity policy: mood-evidence-v1. Backend has filtered context for privacy.
Treat short follow-ups as continuing the user's intent when safe context supports it.
Safe history is bounded; missing earlier messages do not prove something never happened.
Respect latest user corrections, resolved requests and existing constraints in safe history.
Assistant history is not verified source evidence. User statements are self-report.
Never turn conversational observations into long-term memory. Answer directly when possible,
without repeating disclaimers or asking for information already available. Do not introduce
unrelated data sources or tools when the user has not asked about them.
"""
    from app.ai.agents import caps

    if not caps(bot_id).mood_scope:
        memory = sources.get("memory")
        if memory is not None:
            common += "\nBackend memory state (not a grant): " + json.dumps({
                "authorization": memory.authorization, "evidence": memory.evidence,
            }) + "\nUnavailable/revoked memory cannot be recalled from old assistant statements.\n"
        return common
    mood = sources.get("mood")
    state = {
        "authorization": mood.authorization if mood else "no_current_authorization",
        "previous": mood.previous if mood else "missing_verified_evidence",
        "evidence": mood.evidence if mood else "tool_unavailable",
        "reuse": "not_authorized",
    }
    if not mood_analysis:
        return common + '\nBackend mood state (not a request to analyze): ' + json.dumps(state) + """
The current request is conversational or practical. An unused sharing scope does
not require analysis. No mood reading tool is supplied; do not claim stored mood
facts or reuse earlier statistics. Answer the current request using AiOutput.
Do not introduce date selection, statistics or permission explanations unless
the user actually asks about stored mood data.
"""
    return common + """
Runtime evidence policy: mood-evidence-v1. This backend state is authoritative:
""" + json.dumps(state) + """
Treat short follow-ups as continuing the user's intent. Safe history is bounded and may
exclude earlier analysis for privacy; its absence does not mean the analysis never happened.
previously_authorized means a previous turn had permission, NOT proof it read records.
Without current authorization, do not query or reuse old mood statistics or assistant claims.
When a mood follow-up needs data, explain briefly: quyền chia sẻ chỉ có hiệu lực cho lượt
đã gửi; lượt này cần chia sẻ lại khoảng ngày để đọc và kiểm tra. Do not say 'you never shared',
'I never analyzed', or 'no records' on the basis of missing authorization. Do not repeat
this explanation for unrelated conversation. Prose is never a grant. Historical assistant
statements are not evidence. User statements are self-report, not verified stored records.
Respect the latest correction, resolved requests and conversational constraints in safe
history. Do not infer a new memory or repeat questions already answered in available context.
Answer directly; calibrate uncertainty to the actual limitation; no obligatory question.
For a scoped mood turn, call read_mood_summary with {} before answering. Its evidence
capabilities replace the legacy insightAvailable flag. Description uses recorded facts;
observation compares actual records; inference requires a validated method (none enabled).
Sparse records can still be described and compared. Never infer missing-day mood or causality.
For scoped turns the private output is MoodAnalysisPlan, not AiOutput: choose focus and
next_step for the user's request. Backend renders all factual and numerical mood claims.
Set detail=brief for a short follow-up or a focused comparison. Set include_mean=false
when the user does not want the mean repeated. Other facts still come from backend
rendering; do not put free-form claims in the plan. Standard detail is the safe default.
Use next_step=none when advice is unwanted. No raw text, numbers, dates, or trend claims
belong in the plan. The public response remains AiOutput after server rendering.
"""
