"""Validate configuration without printing credentials or making network calls."""

import argparse
import json
import sys
from pathlib import Path

from pydantic import ValidationError

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / "backend"))
from app.core.config import Settings  # noqa: E402

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--env-file", type=Path, default=root / "backend" / ".env")
args = parser.parse_args()

try:
    config = Settings(_env_file=args.env_file)
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

from app.ai.runtime import AiRuntime  # noqa: E402

ai_status = AiRuntime(config, None).status_for(None)

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
                    "voyage_api_key",
                )
            },
            "aiEnabled": config.ai_enabled,
            "aiConfigurationStatus": ai_status,
            "aiProviderCredentialValidated": False,
            "aiAccountingEnabled": config.ai_accounting_enabled,
            "aiDailyTurnsPerUser": config.ai_daily_turns_per_user,
            "activitiesEnabled": config.activities_enabled,
            "matchingScorer": config.matching_scorer,
            "sttEnabled": config.stt_enabled,
            "sandboxEnabled": config.sandbox_enabled,
            "historyCapability": config.chat_history_enabled,
            "historyRetentionDays": config.chat_retention_days,
            "semanticMemoryAvailable": config.semantic_memory_available,
            "networkAccessPerformed": False,
        },
        indent=2,
    )
)
