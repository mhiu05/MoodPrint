"""Check the maintained technical docs offline without reading runtime configuration."""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
GUIDES = (
    "ARCHITECTURE.md",
    "README.md",
    "frontend/README.md",
    "deploy/README.md",
    "backend/evals/README.md",
    "backend/evals/matching/README.md",
)
LINK = re.compile(r"!?\[[^\]\n]*\]\((<[^>]+>|[^\s)]+)(?:\s+\"[^\"]*\")?\)")


def check() -> list[str]:
    errors: list[str] = []
    files = sorted((ROOT / "docs").rglob("*.md")) + [ROOT / name for name in GUIDES]
    links = 0
    for path in files:
        if not path.is_file():
            errors.append(f"Missing guide: {path.relative_to(ROOT)}")
            continue
        source = path.read_text(encoding="utf-8")
        if not source.strip():
            errors.append(f"Empty guide: {path.relative_to(ROOT)}")
        fenced = False
        for number, line in enumerate(source.splitlines(), 1):
            if line.lstrip().startswith(("```", "~~~")):
                fenced = not fenced
            if fenced:
                continue
            for match in LINK.finditer(line):
                target = match.group(1).strip("<>")
                parsed = urlsplit(target)
                if parsed.scheme or parsed.netloc or not parsed.path:
                    continue
                destination = (path.parent / unquote(parsed.path)).resolve()
                links += 1
                if not destination.exists():
                    errors.append(f"{path.relative_to(ROOT)}:{number}: missing {target}")

    api_doc = (ROOT / "docs/backend/api-reference.md").read_text(encoding="utf-8")
    documented = set(re.findall(r"^\| ([A-Z]+) \| `([^`]+)` \|", api_doc, re.MULTILINE))
    api = json.loads((ROOT / "backend/openapi.json").read_text(encoding="utf-8"))
    expected = {
        (method.upper(), path)
        for path, operations in api["paths"].items()
        for method in operations
        if method in {"get", "post", "put", "patch", "delete", "head", "options"}
    }
    for item in sorted(expected - documented):
        errors.append(f"API inventory missing: {item[0]} {item[1]}")
    for item in sorted(documented - expected):
        errors.append(f"API inventory obsolete: {item[0]} {item[1]}")

    config_doc = (ROOT / "docs/backend/configuration.md").read_text(encoding="utf-8")
    fields = set()
    for source in ("backend/app/core/config.py", "backend/app/ai/embedding_config.py"):
        tree = ast.parse((ROOT / source).read_text(encoding="utf-8"))
        for cls in (node for node in tree.body if isinstance(node, ast.ClassDef)):
            fields.update(
                node.target.id.upper()
                for node in cls.body
                if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name)
            )
    documented_fields = set(re.findall(r"^\| `([A-Z0-9_]+)` \|", config_doc, re.MULTILINE))
    for field in sorted(fields ^ documented_fields):
        errors.append(f"Configuration inventory drift: {field}")

    schema_doc = (ROOT / "docs/supabase/schema.md").read_text(encoding="utf-8")
    tables = set()
    for path in (ROOT / "backend/app").rglob("*.py"):
        tables.update(re.findall(r'__tablename__\s*=\s*[\'\"]([^\'\"]+)', path.read_text(encoding="utf-8")))
    for table in sorted(tables):
        if f"`{table}`" not in schema_doc:
            errors.append(f"Schema inventory missing: {table}")
    print(
        f"Checked {len(files)} Markdown files, {links} local links, "
        f"{len(expected)} API operations, {len(fields)} settings, {len(tables)} tables."
    )
    return errors


if __name__ == "__main__":
    failures = check()
    for failure in failures:
        print(f"FAIL: {failure}")
    print("FAIL" if failures else "PASS: technical documentation checks")
    raise SystemExit(bool(failures))
