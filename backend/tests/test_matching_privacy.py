"""T-MATCH-06: matching code can only read published profiles and social counters."""

import ast
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / "app"
SOURCES = [*sorted((APP / "modules/matching").glob("*.py")), APP / "modules/social/retrieval.py"]
PRIVATE_NAMES = {
    "Mood",
    "PrivateItem",
    "Memory",
    "MemoryProposal",
    "MemoryEmbedding",
    "EmbeddingJob",
    "AiConversation",
    "AiMessageRecord",
    "AiTurn",
    "AiRun",
    "IdentityField",
    "RevealAccess",
    "HumanMessage",
    "ActivitySession",
    "ActivityParticipant",
    "ActivityResponse",
}
PRIVATE_MODULES = (
    "app.ai",
    "app.modules.mood",
    "app.modules.moderation",
    "app.modules.activities",
    "app.modules.users",
    "app.modules.voice",
)


def test_matching_modules_never_import_private_models():
    offenders = []
    for path in SOURCES:
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.ImportFrom):
                module = node.module or ""
                names = {alias.name for alias in node.names}
            elif isinstance(node, ast.Import):
                module, names = "", {alias.name for alias in node.names}
            else:
                continue
            modules = {module, *names}
            if names & PRIVATE_NAMES or any(m.startswith(PRIVATE_MODULES) for m in modules):
                offenders.append(f"{path.name}: {module} {sorted(names)}")
    assert offenders == []
    assert len(SOURCES) >= 4  # scoring, scoring_v2, ranking, retrieval at least
