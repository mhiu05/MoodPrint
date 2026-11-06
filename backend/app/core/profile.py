"""Technical switch that isolates the frozen product from the school safety release.

``APP_PROFILE=default`` is the frozen product. Tests keep using it. Staging sets
``school_safety``. That profile is not a demo mode: it forces legacy capabilities
off and is the value ``verify_actor`` and the route guard will read.
"""

from typing import Protocol

FORCED_OFF: tuple[str, ...] = (
    "ai_three_agent_experience_enabled",
    "ai_smart_orchestration_enabled",
    "ai_group_chat_enabled",
    "ai_collaboration_enabled",
    "ai_collaboration_defaults_enabled",
    "proactive_enabled",
    "proactive_worker_enabled",
    "ai_web_search_enabled",
    "ai_maps_search_enabled",
    "maps_search_worker_enabled",
    "ai_agent_skills_enabled",
    "activities_enabled",
    "semantic_memory_enabled",
    "journal_semantic_enabled",
    "journal_auto_memory_enabled",
    "product_tour_enabled",
)

# Path prefixes after ``/api/v1``. Compared by prefix in the route guard.
LEGACY_DENYLIST: tuple[str, ...] = (
    "/activities",
    "/admin",
    "/ai/groups",
    "/ai/inbox",
    "/ai/maps-searches",
    "/ai/proactive",
    "/ai/prompt-capabilities",
    "/ai/sharing",
    "/blocks",
    "/connection-requests",
    "/connections",
    "/feedback",
    "/journal",
    "/matching",
    "/memories",
    "/moods",
    "/profiles",
    "/proposals",
    "/reports",
    "/reveal-grants",
    "/reveal-requests",
    "/social",
    "/taxonomy",
)


class _Profiled(Protocol):
    app_profile: str


def is_school_safety(settings: _Profiled) -> bool:
    return settings.app_profile == "school_safety"
