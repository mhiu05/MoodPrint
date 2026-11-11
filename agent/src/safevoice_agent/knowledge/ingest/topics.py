"""Topic identifiers shared by validation, the API, and the benchmark."""

CORE_TOPICS: tuple[str, ...] = (
    "definition",
    "physical",
    "verbal-social",
    "exclusion",
    "cyber",
    "evidence",
    "help-seeking",
    "school-procedure-vn",
    "legal-vn",
    "bystander",
    "emotional-impact",
    "parents-teachers",
    "platform-reporting",
    "urgent-safety",
)
SYNTHETIC_TOPICS: frozenset[str] = frozenset((*CORE_TOPICS, "support"))
PRODUCTION_TOPICS: frozenset[str] = frozenset(CORE_TOPICS)
LICENCE_CLASSES: frozenset[str] = frozenset(
    {"open_reuse", "authored", "reference_only", "unverified"}
)
PUBLISHABLE: frozenset[str] = frozenset({"open_reuse", "authored"})
