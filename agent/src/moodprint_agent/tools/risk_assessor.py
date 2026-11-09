"""Model-assisted urgency assessment and the hybrid policy (S-06 addendum, options B and C).

The model is a *second opinion that can only raise* the level the deterministic layer found:

* ``hybrid_assess`` returns ``max(deterministic, model)``. A model that says "none", is injected,
  times out or refuses can never lower an ``elevated``/``immediate`` verdict.
* A failed or refused model call never silently means "safe". The result carries
  ``classifier_unavailable`` / ``classifier_refused`` and falls back to a deliberately broad,
  high-recall cue list (``elevated`` when it matches) plus the deterministic verdict.
* Only the user's own messages are sent (never retrieved documents, memory or image text), JSON-encoded
  inside a data block, so nothing the model reads can come from a source other than the student.
* Output is a small enum schema. Free text from the model is never shown or stored.

It is opt-in (``risk_assessor`` on ``CompanionRuntime``). The student's text goes to the external
model, so this must not be enabled for real students without the owner's data-handling approval.
"""

import asyncio
import json
import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Final, Literal, Protocol, cast

from moodprint_shared.config import AppConfig
from openai import AsyncOpenAI, OpenAIError
from pydantic import BaseModel, ConfigDict

from moodprint_agent.companion import load_prompt
from moodprint_agent.tools.safety import (
    NONE,
    UrgencyAssessment,
    UrgencyLevel,
    assess_conversation,
    combine,
    fold,
)

RISK_ASSESSOR_VERSION: Final = "risk_assessor_v1"
CONTEXT_MESSAGES: Final = 4  # the newest message plus up to three earlier student messages
MAX_CHARS_PER_MESSAGE: Final = 1_500
ASSESSOR_OUTPUT_TOKENS: Final = 400
DEFAULT_TIMEOUT_S: Final = 6.0


class ModelRisk(BaseModel):
    model_config = ConfigDict(extra="forbid")
    level: Literal["none", "elevated", "immediate"]
    category: Literal[
        "self_harm", "threat", "violence", "image_coercion", "abuse", "third_party", "other", "none"
    ]
    confidence: Literal["low", "medium", "high"]


class AssessorFailed(Exception):
    """``code`` is one of timeout, refusal, upstream_error, unreadable_output."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True, slots=True)
class AssessorResult:
    risk: ModelRisk
    usage: dict[str, int]
    latency_ms: int


class RiskAssessor(Protocol):
    async def assess(self, messages: Sequence[str]) -> AssessorResult: ...


def render_input(messages: Sequence[str]) -> str:
    recent = [m[:MAX_CHARS_PER_MESSAGE] for m in messages[-CONTEXT_MESSAGES:]]
    data = json.dumps(
        {"student_messages_oldest_first": recent, "assess_message_index": len(recent) - 1},
        ensure_ascii=False,
    ).replace("<", "\\u003c")
    return f"<conversation_data>\n{data}\n</conversation_data>"


class OpenAIRiskAssessor:
    """One structured Responses call. Uses the fixed model id from configuration."""

    def __init__(
        self,
        client: AsyncOpenAI,
        cfg: AppConfig,
        *,
        timeout_s: float = DEFAULT_TIMEOUT_S,
        effort: str = "low",
    ) -> None:
        self._client, self._cfg = client, cfg
        self._timeout_s, self._effort = timeout_s, effort

    async def assess(self, messages: Sequence[str]) -> AssessorResult:
        if not messages:
            raise AssessorFailed("unreadable_output")
        started = asyncio.get_running_loop().time()
        try:
            async with asyncio.timeout(self._timeout_s):
                response = await self._client.responses.parse(
                    model=self._cfg.agent.companion_model,
                    instructions=load_prompt(RISK_ASSESSOR_VERSION),
                    input=render_input(messages),
                    text_format=ModelRisk,
                    store=False,
                    max_output_tokens=ASSESSOR_OUTPUT_TOKENS,
                    reasoning=cast(Any, {"effort": self._effort}),
                )
        except TimeoutError:
            raise AssessorFailed("timeout") from None
        except OpenAIError:
            raise AssessorFailed("upstream_error") from None
        for item in cast(list[Any], getattr(response, "output", None) or []):
            for part in cast(list[Any], getattr(item, "content", None) or []):
                if getattr(part, "type", "") == "refusal":
                    raise AssessorFailed("refusal")
        parsed = response.output_parsed
        if parsed is None:
            raise AssessorFailed("unreadable_output")
        usage = response.usage
        return AssessorResult(
            risk=parsed,
            usage={
                "input_tokens": usage.input_tokens if usage else 0,
                "output_tokens": usage.output_tokens if usage else 0,
                "total_tokens": usage.total_tokens if usage else 0,
            },
            latency_ms=int((asyncio.get_running_loop().time() - started) * 1000),
        )


# A deliberately broad net used only when the model could not be asked. It trades precision for
# recall: anything that even mentions death, harm, being threatened or private images is "elevated".
_WIDE_NET: Final = re.compile(
    r"\b(?:chet|tu tu|tu sat|nhay|treo co|cat tay|rach|thuoc ngu|day thung|bien mat|ket thuc|"
    r"muon di|giet|danh|dam|dap|doa|hanh hung|vay|chan|bam theo|theo doi|theo sau|dao|sung|gay|"
    r"nhot|khoa|ep|tong tien|doi tien|anh nhay cam|anh rieng tu|clip|video|so mo|xam hai|cham vao|"
    r"om|hon|may|nguy hiem|cuu|giup voi|khong muon song|het cach|thuoc|uong|nuot|mau|ngat|"
    r"bat tinh|khong tra loi|tuyet vong|so|hoang|kinh khung|bi danh|bi doa|bi ep|tam biet)\b"
)


def wide_net(messages: Sequence[str]) -> bool:
    return bool(messages) and bool(_WIDE_NET.search(fold(" . ".join(messages[-CONTEXT_MESSAGES:]))))


@dataclass(frozen=True, slots=True)
class HybridResult:
    assessment: UrgencyAssessment
    deterministic: UrgencyAssessment
    model: ModelRisk | None
    degraded: str | None  # None, or the failure code (timeout, refusal, upstream_error, …)
    model_called: bool
    usage: dict[str, int]
    latency_ms: int


def _as_assessment(risk: ModelRisk) -> UrgencyAssessment:
    if risk.level == "none":
        return NONE
    return UrgencyAssessment(cast(UrgencyLevel, risk.level), (f"model_{risk.category}",))


async def hybrid_assess(
    messages: Sequence[str], assessor: RiskAssessor | None, *, skip_when_immediate: bool = True
) -> HybridResult:
    """Deterministic floor first; the model may only raise it; a failure is never "safe"."""
    deterministic = assess_conversation(messages)
    empty_usage = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
    if assessor is None or (skip_when_immediate and deterministic.immediate):
        return HybridResult(deterministic, deterministic, None, None, False, empty_usage, 0)
    try:
        result = await assessor.assess(messages)
    except (AssessorFailed, Exception) as caught:  # CancelledError is a BaseException: not caught
        exc = caught if isinstance(caught, AssessorFailed) else AssessorFailed("internal_error")
        floor = deterministic
        if exc.code == "refusal":
            # A model that declines to read a student's message is itself a reason to look closer.
            floor = combine(floor, UrgencyAssessment("elevated", ("classifier_refusal",)))
        elif wide_net(messages):
            floor = combine(
                floor, UrgencyAssessment("elevated", (f"classifier_{exc.code}", "wide_net"))
            )
        return HybridResult(floor, deterministic, None, exc.code, True, empty_usage, 0)
    merged = combine(deterministic, _as_assessment(result.risk))
    return HybridResult(
        merged, deterministic, result.risk, None, True, result.usage, result.latency_ms
    )
