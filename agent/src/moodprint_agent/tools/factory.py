"""Build the Phase 3 tool inventory. Adding or removing a tool changes ``tools_version``."""

from moodprint_shared.config import AppConfig

from moodprint_agent.tools.registry import ToolRegistry, ToolSpec


def tool_groups(cfg: AppConfig) -> list[list[ToolSpec]]:
    """Ordered groups; each task registers its own group here."""
    groups: list[list[ToolSpec]] = []
    return groups


def build_registry(cfg: AppConfig) -> ToolRegistry:
    """Pure function of config: needs no database, request or app state at startup."""
    registry = ToolRegistry()
    for group in tool_groups(cfg):
        registry.register_group(group)
    return registry
