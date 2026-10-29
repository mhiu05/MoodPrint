"""Personal features are always permitted; social sharing remains explicit."""

PERSONAL_PURPOSES = frozenset({"AI", "MEM", "VOICE"})


def consent_enabled(purpose: str, enabled: bool) -> bool:
    return purpose in PERSONAL_PURPOSES or enabled
