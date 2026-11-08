"""One Companion, dynamic context instructions, explicit privacy defaults."""

import json
from importlib.resources import files
from typing import Final

from agents import Agent, ModelSettings, RunContextWrapper
from moodprint_shared.config import AppConfig
from moodprint_shared.contracts.agent import AgentToolContext
from openai.types.shared import Reasoning

from moodprint_agent.tools.registry import ToolRegistry

PROMPT_VERSION: Final = "companion_v3"
ROLEPLAY_PARTNER_VERSION: Final = "roleplay_partner_v1"
ROLEPLAY_COACH_VERSION: Final = "roleplay_coach_v1"
EVIDENCE_READER_VERSION: Final = "evidence_reader_v1"


def load_prompt(name: str) -> str:
    return files("moodprint_agent").joinpath(f"prompts/{name}.md").read_text(encoding="utf-8")


_PROMPT = load_prompt(PROMPT_VERSION)


def model_settings(cfg: AppConfig, *, effort: str | None = None) -> ModelSettings:
    """Never send temperature/top_p: the reasoning model rejects or ignores them."""
    return ModelSettings(
        store=False,
        parallel_tool_calls=False,
        max_tokens=cfg.agent.max_output_tokens,
        reasoning=Reasoning(effort=effort or cfg.agent.reasoning_effort),  # type: ignore[arg-type]
    )


def render_instructions(
    ctx: RunContextWrapper[AgentToolContext], agent: Agent[AgentToolContext]
) -> str:
    records: list[dict[str, object]] = []
    for section in ctx.context.context.sections:
        labels: list[str] = []
        for source in section.provenance:
            label = f"[{source.source_kind} {source.retrieved_at.date().isoformat()}]"
            if source.source_kind == "approved_memory":
                label = f"[đã duyệt {source.retrieved_at.date().isoformat()}]"
            if source.stale:
                label += " [cũ: cần xác nhận lại]"
            labels.append(label)
        records.append({"kind": section.kind, "labels": labels, "text": section.text})
    # Escaping '<' prevents untrusted text from closing the data delimiter.
    data = json.dumps(records, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")
    hint = getattr(ctx.context, "safety_hint", None)
    signal = f"\n<safety_signal>\n{hint}\n</safety_signal>" if hint else ""
    return f"{_PROMPT}\n<context_data>\n{data}\n</context_data>{signal}"


def build_companion(cfg: AppConfig, registry: ToolRegistry) -> Agent[AgentToolContext]:
    return Agent[AgentToolContext](
        name="MoodPrint Companion",
        instructions=render_instructions,
        tools=[tool for tool in registry.sdk_tools()],
        model=cfg.agent.companion_model,
        model_settings=model_settings(cfg),
        output_type=None,
    )
