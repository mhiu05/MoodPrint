"""One Companion, dynamic context instructions, explicit privacy defaults."""

import json
from importlib.resources import files

from agents import Agent, ModelSettings, RunContextWrapper
from moodprint_shared.config import AppConfig
from moodprint_shared.contracts.agent import AgentToolContext

from moodprint_agent.tools.registry import ToolRegistry

PROMPT_VERSION = "companion_v1"
_PROMPT = files("moodprint_agent").joinpath("prompts/companion_v1.md").read_text(encoding="utf-8")


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
    return f"{_PROMPT}\n<context_data>\n{data}\n</context_data>"


def build_companion(cfg: AppConfig, registry: ToolRegistry) -> Agent[AgentToolContext]:
    return Agent[AgentToolContext](
        name="MoodPrint Companion",
        instructions=render_instructions,
        tools=[tool for tool in registry.sdk_tools()],
        model=cfg.agent.companion_model,
        model_settings=ModelSettings(store=False, parallel_tool_calls=False),
        output_type=None,
    )
