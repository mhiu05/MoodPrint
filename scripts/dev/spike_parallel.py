"""S-04: probe two already-running loopback stacks using synthetic data only."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from urllib.parse import urlsplit
from uuid import uuid4

import asyncpg
import httpx
from supabase_worktree import ROOT, cli


async def probe(primary: Path, secondary: Path) -> None:
    statuses = []
    for workdir in (primary, secondary):
        result = await asyncio.to_thread(cli, workdir, "status", "-o", "json")
        if result.returncode:
            raise RuntimeError("Both local stacks must be healthy before S-04")
        status = json.loads(result.stdout)
        db = urlsplit(status["DB_URL"])
        api = urlsplit(status["API_URL"])
        if db.hostname not in {"127.0.0.1", "localhost", "::1"} or api.hostname not in {
            "127.0.0.1",
            "localhost",
            "::1",
        }:
            raise ValueError("S-04 accepts loopback endpoints only")
        statuses.append(status)
    if (
        statuses[0]["DB_URL"] == statuses[1]["DB_URL"]
        or statuses[0]["API_URL"] == statuses[1]["API_URL"]
    ):
        raise ValueError("S-04 requires distinct database and API ports")

    connections = []
    owner = uuid4()
    try:
        for index, status in enumerate(statuses):
            connection = await asyncpg.connect(status["DB_URL"], timeout=15)
            connections.append(connection)
            await connection.execute("insert into auth.users(id) values($1)", owner)
            await connection.execute(
                "insert into app.profiles(user_id,nickname) values($1,$2)",
                owner,
                f"Synthetic stack {index}",
            )
        for index, connection in enumerate(connections):
            nickname = await connection.fetchval(
                "select nickname from app.profiles where user_id=$1", owner
            )
            if nickname != f"Synthetic stack {index}":
                raise RuntimeError("Synthetic stack isolation failed")
        async with httpx.AsyncClient(timeout=15) as client:
            key_sets = []
            for status in statuses:
                response = await client.get(status["API_URL"] + "/auth/v1/.well-known/jwks.json")
                response.raise_for_status()
                keys = response.json()["keys"]
                if not keys or any(key.get("alg") != "ES256" for key in keys):
                    raise RuntimeError("Local Auth must publish ES256 verification keys")
                key_sets.append({key["kid"] for key in keys})
            if key_sets[0] & key_sets[1]:
                raise RuntimeError("Local stacks unexpectedly share signing keys")
        print("VERIFIED S-04: two stacks have separate API/DB ports, data and ES256 signing keys.")
    finally:
        for connection in connections:
            try:
                await connection.execute("delete from auth.users where id=$1", owner)
            finally:
                await connection.close()


if __name__ == "__main__":
    try:
        asyncio.run(probe(ROOT, ROOT / ".local/stacks/spike-parallel"))
    except Exception:
        raise SystemExit("S-04 failed; endpoint/credential details suppressed.") from None
