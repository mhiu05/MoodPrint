"""Companion identities and capabilities: the three V3 agents and the five legacy companions.

Code paths branch on a capability, never on a companion's name, so Nhật ký can use the journal
and mood tools that Nhịp used without being a renamed Nhịp (its persona, prompts and data stay
separate). A legacy companion keeps its own conversations, memories and schedules; nothing here
merges histories between companions.
"""

from dataclasses import dataclass
from typing import Literal

LEGACY_IDS: tuple[str, ...] = ("may", "guong", "nhip", "rure", "caunoi")
V3_IDS: tuple[str, ...] = ("dieuphoi", "nhatky", "hoatdong")
ALL_IDS: tuple[str, ...] = LEGACY_IDS + V3_IDS
V3AgentId = Literal["dieuphoi", "nhatky", "hoatdong"]

# Which V3 agent took over a legacy companion's purpose (None: Cầu Nối became the separate
# social-discovery feature, not a companion).
REPLACED_BY: dict[str, str | None] = {
    "may": "dieuphoi", "guong": "dieuphoi", "nhip": "nhatky", "rure": "hoatdong", "caunoi": None,
}
DISPLAY_NAMES: dict[str, str] = {
    "may": "Mây", "guong": "Gương", "nhip": "Nhịp", "rure": "Rủ Rê", "caunoi": "Cầu Nối",
    "dieuphoi": "Điều phối", "nhatky": "Nhật ký", "hoatdong": "Hoạt động",
}


@dataclass(frozen=True)
class Capabilities:
    # Reads the owner's saved journal entries (search tool; morning check-in context).
    journal: bool = False
    # Reads mood scores for a user-selected date range.
    mood_scope: bool = False
    # May propose an approved memory (and read approved memories of its own scope).
    memory: bool = False
    # Proposes small challenges/activities (challenge kinds rotate in check-ins).
    challenges: bool = False
    # Default conversational stance used by the intent hint.
    stance: Literal["conversation", "reflection", "activity", "connection", "journal"] = "conversation"
    # Social discovery companion (Cầu Nối): no private data, pending-invitation check-ins.
    connection: bool = False


CAPABILITIES: dict[str, Capabilities] = {
    "may": Capabilities(memory=True),
    "guong": Capabilities(memory=True, stance="reflection"),
    "nhip": Capabilities(journal=True, mood_scope=True, memory=True, stance="journal"),
    "rure": Capabilities(challenges=True, stance="activity"),
    "caunoi": Capabilities(connection=True, stance="connection"),
    "dieuphoi": Capabilities(memory=True),
    "nhatky": Capabilities(journal=True, mood_scope=True, memory=True, stance="journal"),
    "hoatdong": Capabilities(challenges=True, stance="activity"),
}
# Companions whose approved memories exist and may be retrieved for their own scope (Rủ Rê's
# legacy rows included; Cầu Nối never). Proposing a new memory additionally needs ``memory``.
MEMORY_IDS: tuple[str, ...] = ("may", "guong", "nhip", "rure", "dieuphoi", "nhatky", "hoatdong")


def caps(bot_id: str) -> Capabilities:
    return CAPABILITIES.get(bot_id, Capabilities())


def is_legacy(bot_id: str) -> bool:
    return bot_id in LEGACY_IDS


def is_v3(bot_id: str) -> bool:
    return bot_id in V3_IDS


def sql_in(values: tuple[str, ...]) -> str:
    return "(" + ",".join(f"'{value}'" for value in values) + ")"


# Database CHECK expressions shared by the ORM and migration 0024.
BOT_CHECK = "bot_id in " + sql_in(ALL_IDS)
MEMORY_BOT_CHECK = "bot_id in " + sql_in(MEMORY_IDS)
