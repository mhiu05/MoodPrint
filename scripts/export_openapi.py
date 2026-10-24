"""Export the actual FastAPI/Pydantic contract without network or credentials."""

import json
import os
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / "backend"))
# Contract generation must not inspect or depend on the developer's secrets.
os.environ.update(
    {
        "APP_ENV": "test",
        "DATABASE_URL": "",
        "DATABASE_MIGRATION_URL": "",
        "DATABASE_POOL_MODE": "session",
        "SUPABASE_URL": "",
        "SUPABASE_PUBLISHABLE_KEY": "",
        "OPENAI_API_KEY": "",
        "OPENAI_MODEL": "",
        "AI_ENABLED": "false",
        "STT_ENABLED": "false",
        "SANDBOX_ENABLED": "false",
        "COOKIE_SECURE": "false",
    }
)
from app.main import create_app  # noqa: E402

target = root / "backend" / "openapi.json"
target.write_text(
    json.dumps(create_app().openapi(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
)
print(target.relative_to(root))
