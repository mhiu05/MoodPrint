"""Build the Phase 3 tool inventory. Adding or removing a tool changes ``tools_version``."""

from moodprint_shared.config import AppConfig

from moodprint_agent.tools.registry import ToolRegistry, ToolSpec


def tool_groups(cfg: AppConfig) -> list[list[ToolSpec]]:
    """Ordered groups; each task registers its own group here."""
    from moodprint_agent.tools.evidence import evidence_tools
    from moodprint_agent.tools.incident import incident_tools
    from moodprint_agent.tools.knowledge import knowledge_tools
    from moodprint_agent.tools.memory import memory_tools
    from moodprint_agent.tools.plan import plan_tools
    from moodprint_agent.tools.support import support_tools

    groups: list[list[ToolSpec]] = [
        knowledge_tools(),
        incident_tools(),
        evidence_tools(),
        plan_tools(),
        memory_tools(),
        support_tools(),
    ]
    return groups


def build_registry(cfg: AppConfig) -> ToolRegistry:
    """Pure function of config: needs no database, request or app state at startup."""
    registry = ToolRegistry()
    for group in tool_groups(cfg):
        registry.register_group(group)
    return registry
