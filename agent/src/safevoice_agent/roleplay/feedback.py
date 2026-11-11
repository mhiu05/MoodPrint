"""The coach step: one structured call over the practice transcript, no tools and no session.

The coach only sees the roleplay transcript (and the scenario). Quotations it returns are checked
against what the user actually wrote, so feedback cannot invent a sentence the user never said.
"""

import asyncio
import json
from dataclasses import dataclass
from typing import Any, cast

from openai import AsyncOpenAI, OpenAIError
from safevoice_shared.config import AppConfig

from safevoice_agent.companion import ROLEPLAY_COACH_VERSION, load_prompt
from safevoice_agent.roleplay.models import Rephrasing, RoleplayContext, RoleplayFeedback
from safevoice_agent.roleplay.service import scenario_payload

COACH_OUTPUT_TOKENS = 2_000


class FeedbackFailed(Exception):
    def __init__(self, code: str, *, retryable: bool) -> None:
        super().__init__(code)
        self.code, self.retryable = code, retryable


@dataclass(frozen=True, slots=True)
class FeedbackOutput:
    feedback: RoleplayFeedback
    usage: dict[str, int]


def _norm(text: str) -> str:
    return " ".join(text.split()).casefold()


def ground_rephrasings(feedback: RoleplayFeedback, user_messages: list[str]) -> RoleplayFeedback:
    """Drop any 'original' that is not (a fragment of) something the user really said."""
    said = [_norm(message) for message in user_messages]
    kept: list[Rephrasing] = [
        item
        for item in feedback.rephrasings
        if (needle := _norm(item.original)) and any(needle in message for message in said)
    ]
    return feedback.model_copy(update={"rephrasings": kept})


class RoleplayCoach:
    def __init__(self, client: AsyncOpenAI, cfg: AppConfig) -> None:
        self._client, self._cfg = client, cfg

    async def feedback(
        self, role_play: RoleplayContext, transcript: list[tuple[str, str]]
    ) -> FeedbackOutput:
        """``transcript`` is ``(speaker, text)`` with speaker in {"user", "partner"}."""
        cfg = self._cfg.agent
        data = json.dumps(
            {
                "scenario": scenario_payload(role_play),
                "turns": [{"speaker": speaker, "text": text} for speaker, text in transcript],
            },
            ensure_ascii=False,
        ).replace("<", "\\u003c")
        try:
            async with asyncio.timeout(cfg.roleplay_feedback_timeout_s):
                response = await self._client.responses.parse(
                    model=cfg.companion_model,
                    instructions=load_prompt(ROLEPLAY_COACH_VERSION),
                    input=f"<transcript_data>\n{data}\n</transcript_data>",
                    text_format=RoleplayFeedback,
                    store=False,
                    max_output_tokens=COACH_OUTPUT_TOKENS,
                    reasoning=cast(Any, {"effort": cfg.coach_reasoning_effort}),
                )
        except TimeoutError:
            raise FeedbackFailed("feedback_timeout", retryable=True) from None
        except OpenAIError:
            raise FeedbackFailed("upstream_error", retryable=True) from None
        parsed = response.output_parsed
        if parsed is None:
            raise FeedbackFailed("unreadable_output", retryable=True)
        usage = response.usage
        user_lines = [text for speaker, text in transcript if speaker == "user"]
        return FeedbackOutput(
            feedback=ground_rephrasings(parsed, user_lines),
            usage={
                "input_tokens": usage.input_tokens if usage else 0,
                "output_tokens": usage.output_tokens if usage else 0,
                "total_tokens": usage.total_tokens if usage else 0,
            },
        )
