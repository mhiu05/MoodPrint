"""Phase 3 may use only the frozen KnowledgeRetriever Protocol, never Phase 2 internals."""

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
P3_DIRS = [
    ROOT / "agent" / "src" / "safevoice_agent",
    ROOT / "backend" / "app" / "agent_gateway",
    ROOT / "backend" / "app" / "modules" / "conversations",
    ROOT / "backend" / "app" / "modules" / "memory",
    ROOT / "backend" / "app" / "modules" / "analysis",
    ROOT / "backend" / "app" / "modules" / "roleplay",
]


def _imports(path: Path) -> set[str]:
    found: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            found.add(node.module)
    return found


def test_phase3_never_imports_phase2_knowledge_implementation() -> None:
    offenders: list[str] = []
    for base in P3_DIRS:
        for path in base.rglob("*.py"):
            if "knowledge" in path.relative_to(base).parts and base.name == "safevoice_agent":
                continue  # the Phase 2 package itself (not owned here)
            for name in _imports(path):
                if name.startswith(("safevoice_agent.knowledge", "app.modules.knowledge")):
                    offenders.append(f"{path.relative_to(ROOT)} -> {name}")
    assert offenders == []


def test_tools_depend_on_protocols_not_the_database_layer() -> None:
    forbidden = ("sqlalchemy", "asyncpg", "app.infrastructure", "app.core")
    tools = ROOT / "agent" / "src" / "safevoice_agent" / "tools"
    for path in tools.rglob("*.py"):
        for name in _imports(path):
            assert not name.startswith(forbidden), f"{path.name} imports {name}"
