from pathlib import Path


def test_secret_key_read_only_in_infrastructure():
    root = Path(__file__).resolve().parents[1] / "app"
    offenders = []
    for source in root.rglob("*.py"):
        if source == root / "main.py" or "infrastructure" in source.relative_to(root).parts:
            continue
        if "supabase_secret_key" in source.read_text(encoding="utf-8"):
            offenders.append(source.relative_to(root).as_posix())
    assert offenders == []


def test_runtime_does_not_read_privileged_migration_connection():
    root = Path(__file__).resolve().parents[1] / "app"
    assert all(
        "supabase_db_url" not in path.read_text(encoding="utf-8") for path in root.rglob("*.py")
    )
