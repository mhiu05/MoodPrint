"""The practice partner: the same Companion in a no-tools, persona-bound mode.

There is no second agent stack: the runtime picks this ``Agent`` for a roleplay conversation and
reuses its session, streaming, budget, urgency layer and persistence. Persona, scenario, goal and
difficulty are re-rendered into the instructions on *every* turn.
"""

import json
from typing import Final

from agents import Agent, RunContextWrapper
from moodprint_shared.config import AppConfig
from moodprint_shared.contracts.agent import AgentToolContext

from moodprint_agent.companion import ROLEPLAY_PARTNER_VERSION, load_prompt, model_settings
from moodprint_agent.roleplay.models import RoleplayContext
from moodprint_agent.roleplay.scenarios import PERSONAS

EXIT_ROLE_TEXT: Final = (
    "Mình dừng buổi diễn tập ở đây nhé. Mình là AI đang đóng vai, không phải người thật, và điều "
    "bạn vừa nói quan trọng hơn bài tập. Hãy nói ngay với một người lớn ở gần bạn mà bạn tin "
    "tưởng. Nếu bạn đang gặp nguy hiểm hoặc muốn làm hại bản thân, hãy gọi Tổng đài 111 "
    "(miễn phí, 24/24)."
)


def scenario_payload(role_play: RoleplayContext) -> dict[str, object]:
    payload: dict[str, object] = {
        "persona": PERSONAS[role_play.role],
        "scenario": role_play.scenario_title,
        "context": role_play.scenario_context,
        "user_goal": role_play.user_goal,
        "difficulty": role_play.difficulty,
        "user_age_band": role_play.age_band or "không rõ",
    }
    if role_play.case_summary:
        payload["case_summary_user_allowed"] = role_play.case_summary
    return payload


def render_partner_instructions(
    ctx: RunContextWrapper[AgentToolContext], agent: Agent[AgentToolContext]
) -> str:
    role_play = getattr(ctx.context, "roleplay", None)
    if not isinstance(role_play, RoleplayContext):
        raise ValueError("roleplay context is required for the partner")
    data = json.dumps(scenario_payload(role_play), ensure_ascii=False, separators=(",", ":"))
    # Escaping '<' keeps user-authored scenario text from closing the data delimiter.
    data = data.replace("<", "\\u003c")
    hint = getattr(ctx.context, "safety_hint", None)
    signal = f"\n<safety_signal>\n{hint}\n</safety_signal>" if hint else ""
    return f"{load_prompt(ROLEPLAY_PARTNER_VERSION)}\n<scenario_data>\n{data}\n</scenario_data>{signal}"


def build_partner(cfg: AppConfig) -> Agent[AgentToolContext]:
    return Agent[AgentToolContext](
        name="MoodPrint Roleplay Partner",
        instructions=render_partner_instructions,
        tools=[],  # a practice partner can read nothing and write nothing
        model=cfg.agent.companion_model,
        model_settings=model_settings(cfg),
        output_type=None,
    )
