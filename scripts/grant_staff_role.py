"""Grant or revoke a moderation role on a LOCAL/TEST database only.

    cd backend && uv run --locked python ../scripts/grant_staff_role.py \
        --database-url-env TEST_DATABASE_URL --user-id <uuid> --role moderator

Hosted grants go through reviewed SQL with operator approval (11 section 4); this
script refuses any non-local host.
"""

import argparse
import asyncio
import os
import sys
from pathlib import Path
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}


def local_url(raw: str) -> str:
    url = make_url(raw)
    if url.host not in LOCAL_HOSTS:
        raise SystemExit("Refusing a non-local database: staff roles on hosted need reviewed SQL")
    return raw


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database-url-env", default="TEST_DATABASE_URL")
    parser.add_argument("--user-id", type=UUID, required=True)
    parser.add_argument("--role", choices=("moderator", "admin", "none"), required=True)
    parser.add_argument("--granted-by", default="local-operator")
    args = parser.parse_args()
    engine = create_async_engine(local_url(os.environ.get(args.database_url_env, "")))
    try:
        async with engine.begin() as connection:
            await connection.execute(
                text("delete from moodprint.staff_roles where user_id = :uid"),
                {"uid": args.user_id},
            )
            if args.role != "none":
                await connection.execute(
                    text(
                        "insert into moodprint.staff_roles(user_id, role, granted_by) "
                        "values (:uid, :role, :by)"
                    ),
                    {"uid": args.user_id, "role": args.role, "by": args.granted_by},
                )
    finally:
        await engine.dispose()
    print(f"role={args.role}")


if __name__ == "__main__":
    asyncio.run(main())
