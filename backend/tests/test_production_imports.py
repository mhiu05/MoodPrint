"""Production code must never import test fakes or evaluation harnesses."""

import ast
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / "app"


def test_app_never_imports_tests_or_evals():
    offenders = []
    for path in APP.rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            names = (
                [alias.name for alias in node.names]
                if isinstance(node, ast.Import)
                else [node.module or ""]
                if isinstance(node, ast.ImportFrom) and node.level == 0
                else []
            )
            offenders += [
                f"{path.relative_to(APP)}:{name}"
                for name in names
                if name.split(".")[0] in ("tests", "evals")
            ]
    assert offenders == []
