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

# Path prefixes after ``/api/v1``. The route guard matches the prefix or a child path.
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

# Routes the school safety release still serves. A new API route must be added
# here or to LEGACY_DENYLIST; the classification test fails when one is missing.
KEPT_PREFIXES: tuple[str, ...] = (
    "/ai/conversations",
    "/ai/preferences",
    "/ai/runs",
    "/auth",
    "/bots",
    "/consents",
    "/data-deletions",
    "/exports",
    "/health",
    "/public/experience",
    "/session",
    "/users/me",
    "/voice",
)

API_PREFIX = "/api/v1"


def resource_path(path: str) -> str | None:
    if path == API_PREFIX:
        return "/"
    marker = API_PREFIX + "/"
    if path.startswith(marker):
        return path[len(API_PREFIX):]
    return None


def _matches(resource: str, prefixes: tuple[str, ...]) -> bool:
    return any(resource == prefix or resource.startswith(prefix + "/") for prefix in prefixes)


def route_disposition(path: str) -> str:
    """deny, keep, conflict, unknown, or outside for non-API paths."""
    resource = resource_path(path)
    if resource is None:
        return "outside"
    denied = _matches(resource, LEGACY_DENYLIST)
    kept = _matches(resource, KEPT_PREFIXES)
    if denied and kept:
        return "conflict"
    if denied:
        return "deny"
    if kept:
        return "keep"
    return "unknown"


def legacy_route_denied(path: str) -> bool:
    return route_disposition(path) == "deny"


class _Profiled(Protocol):
    app_profile: str


def is_school_safety(settings: _Profiled) -> bool:
    return settings.app_profile == "school_safety"
