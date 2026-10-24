"""Validate configuration without printing credentials or making network calls."""

import json
import sys
from pathlib import Path

from pydantic import ValidationError

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / "backend"))
from app.core.config import Settings  # noqa: E402

try:
    config = Settings(_env_file=root / "backend" / ".env")
except ValidationError as error:
    print(
        json.dumps(
            {
                "valid": False,
                "invalidVariables": [
                    ".".join(map(str, item["loc"])).upper()
                    for item in error.errors(include_input=False)
                ],
            }
        )
    )
    sys.exit(1)


def present(value):
    return bool(value.get_secret_value() if hasattr(value, "get_secret_value") else value)


print(
    json.dumps(
        {
            "valid": True,
            "configured": {
                name.upper(): present(getattr(config, name))
                for name in (
                    "database_url",
                    "database_migration_url",
                    "supabase_url",
                    "supabase_publishable_key",
                    "openai_api_key",
                    "openai_model",
                )
            },
            "aiEnabled": config.ai_enabled,
            "sttEnabled": config.stt_enabled,
            "sandboxEnabled": config.sandbox_enabled,
            "networkAccessPerformed": False,
        },
        indent=2,
    )
)
