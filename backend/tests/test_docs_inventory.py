"""Only public settings belong to the operator's configuration inventory."""

import importlib.util
from pathlib import Path

import pytest


@pytest.mark.parametrize("document_public", [True, False])
def test_private_settings_are_excluded_without_hiding_public_drift(tmp_path, monkeypatch, document_public):
    source = Path(__file__).resolve().parents[2] / "scripts/check_docs.py"
    spec = importlib.util.spec_from_file_location("docs_inventory", source)
    checker = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(checker)
    for name in checker.GUIDES:
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("Guide", encoding="utf-8")
    files = {
        "docs/backend/api-reference.md": "No operations",
        "docs/backend/configuration.md": "| `PUBLIC_FLAG` | `bool` | `True` |" if document_public else "No settings",
        "docs/supabase/schema.md": "No tables",
        "backend/openapi.json": '{"paths":{}}',
        "backend/app/core/config.py": "class Settings:\n    public_flag: bool = True\n    _clamped: list = []\n",
        "backend/app/ai/embedding_config.py": "class EmbeddingSettings:\n    pass\n",
    }
    for relative, content in files.items():
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    monkeypatch.setattr(checker, "ROOT", tmp_path)
    assert checker.check() == ([] if document_public else ["Configuration inventory drift: PUBLIC_FLAG"])
