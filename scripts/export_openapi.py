"""Generate API schemas without loading owner secrets or opening connections."""

import argparse
import json
from pathlib import Path

from app.main import create_app
from moodprint_shared.env import EnvSettings


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    app = create_app(
        EnvSettings(
            app_env="test",
            database_url="postgresql+asyncpg://moodprint_api:test@127.0.0.1:54322/postgres",
            supabase_url="http://127.0.0.1:54321",
            supabase_publishable_key="synthetic",
            supabase_secret_key="synthetic",
        )
    )
    schema = app.openapi()
    path = Path(__file__).resolve().parents[1] / "backend/openapi.json"
    if args.check:
        if not path.exists() or json.loads(path.read_text(encoding="utf-8")) != schema:
            print("OpenAPI snapshot differs; export and review before continuing.")
            return 1
    else:
        path.write_text(
            json.dumps(schema, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
