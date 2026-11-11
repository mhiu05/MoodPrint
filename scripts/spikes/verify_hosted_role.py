"""Manual S-05 probe for the approved hosted project; never part of hosted pytest.

Run only after local G0 and dashboard prerequisites have been verified:
    uv run python scripts/spikes/verify_hosted_role.py --manual-authorized

Creates two synthetic Auth users, exercises the production user_uow through a
two-connection runtime pool, and deletes both users in finally. No DDL or owner
environment writes. Imports perform no network requests and do not read .env.
"""

from __future__ import annotations

import argparse
import asyncio
import importlib.util
import json
import secrets
import subprocess
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from types import ModuleType
from uuid import UUID, uuid4

import httpx
from app.core.auth import JwtVerifier
from app.core.db import create_engine
from app.core.uow import user_uow
from safevoice_shared.config import AppConfig
from safevoice_shared.contracts.auth import AuthContext
from safevoice_shared.env import EnvSettings
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncEngine

ROOT = Path(__file__).resolve().parents[2]
REQUESTS = 50


class RoleProbeError(ValueError):
    """Only fixed checkpoint codes may leave the manual operation boundary."""


class _RollbackProbe(Exception):
    pass


@dataclass(frozen=True, slots=True)
class RoleProbeResult:
    requests: int
    users: int
    checked_connections: int


def _guardrails() -> ModuleType:
    # Scripts are deliberately not workspace packages. Load the existing shared
    # deployment guard without changing sys.path or duplicating project checks.
    spec = importlib.util.spec_from_file_location(
        "s05_hosted_safety", ROOT / "scripts/db/safety.py"
    )
    if spec is None or spec.loader is None:
        raise RoleProbeError("deployment_guard_unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def validate_runtime_target(values: Mapping[str, str]) -> str:
    """Validate both endpoints before any Auth or database connection is made."""
    runtime = values.get("DATABASE_URL", "")
    if not runtime:
        raise RoleProbeError("DATABASE_URL_missing")
    safety = _guardrails()
    try:
        safety.validate_hosted_target(
            values.get("SUPABASE_URL", ""), values.get("SUPABASE_DB_URL", "")
        )
        parsed = make_url(runtime)
        if not safety.is_generated_runtime_url(runtime) or not parsed.password:
            raise RoleProbeError("DATABASE_URL_must_use_generated_runtime_role")
        direct = parsed.host == f"db.{safety.PROJECT_REF}.supabase.co"
        pooler = (parsed.host or "").endswith(".pooler.supabase.com")
        expected_role = "safevoice_api" + (f".{safety.PROJECT_REF}" if pooler else "")
        if parsed.username != expected_role or not (direct or pooler):
            raise RoleProbeError("runtime_target_mismatch")
        if parsed.drivername not in {"postgres", "postgresql", "postgresql+asyncpg"}:
            raise RoleProbeError("runtime_driver_invalid")
        if parsed.database != "postgres":
            raise RoleProbeError("runtime_database_invalid")
        port = parsed.port or 5432
        if direct and port == 5432:
            return "direct"
        if pooler and port in {5432, 6543}:
            return "session_pooler" if port == 5432 else "transaction_pooler"
    except RoleProbeError:
        raise
    except Exception:
        # Invalid URL errors can include owner input; do not propagate them.
        raise RoleProbeError("hosted_target_invalid") from None
    raise RoleProbeError("runtime_port_invalid")


def _require_local_gate() -> None:
    try:
        receipt = json.loads((ROOT / ".local/phase0-gate.json").read_text(encoding="utf-8"))
        head = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, stderr=subprocess.DEVNULL
        ).strip()
        checks = receipt.get("checks", [])
        passed = (
            receipt.get("commit") == head
            and receipt.get("passed") is True
            and receipt.get("scope") == "local"
            and len(checks) == 8
            and all(check.get("returncode") == 0 for check in checks)
        )
    except Exception:
        passed = False
    if not passed:
        raise RoleProbeError("current_HEAD_local_gate_required")


async def _check_clean_pool(engine: AsyncEngine) -> None:
    # Hold both connections together so the second checkout cannot simply reuse
    # the first connection. Each auth.uid check uses the same physical connection
    # as its preceding base-role check, without granting the login auth access.
    async with engine.connect() as first, engine.connect() as second:
        for connection in (first, second):
            async with connection.begin():
                row = (
                    await connection.execute(
                        text(
                            "select current_user, current_setting('request.jwt.claims',true), "
                            "rolsuper, rolbypassrls, rolinherit "
                            "from pg_roles where rolname=current_user"
                        )
                    )
                ).one()
                if row[0] != "safevoice_api" or any(row[index] for index in (2, 3, 4)):
                    raise RoleProbeError("runtime_role_unsafe")
                if row[1] not in {None, ""}:
                    raise RoleProbeError("claims_leaked_outside_transaction")
                await connection.execute(text("SET LOCAL ROLE authenticated"))
                if await connection.scalar(text("select auth.uid()")) is not None:
                    raise RoleProbeError("identity_leaked_on_reused_connection")
            if await connection.scalar(text("select current_user")) != "safevoice_api":
                raise RoleProbeError("role_leaked_after_commit")
            await connection.rollback()


async def _check_identity(session, auth: AuthContext) -> None:
    row = (
        await session.execute(
            text(
                "select current_user, auth.uid(), "
                "current_setting('request.jwt.claims',true)::jsonb ->> 'sub', "
                "current_setting('request.jwt.claims',true)::jsonb ->> 'role'"
            )
        )
    ).one()
    if tuple(row) != ("authenticated", auth.user_id, str(auth.user_id), "authenticated"):
        raise RoleProbeError("identity_not_applied")


async def verify_role_isolation(
    engine: AsyncEngine, identities: tuple[AuthContext, AuthContext]
) -> RoleProbeResult:
    """Bounded S-05 work reusable against the isolated local integration stack.

    Identities must belong to two freshly created synthetic users. Profiles are
    seeded through the real user transaction boundary; no privileged DML is used.
    Callers own user cleanup, including failures and interruption.
    """
    if len(identities) != 2 or identities[0].user_id == identities[1].user_id:
        raise RoleProbeError("two_distinct_synthetic_users_required")
    await _check_clean_pool(engine)
    for auth in identities:
        async with user_uow(engine, auth) as uow:
            await _check_identity(uow.session, auth)
            await uow.session.execute(
                text(
                    "insert into app.profiles(user_id,nickname) values(:id,:nickname) "
                    "on conflict(user_id) do nothing"
                ),
                {"id": auth.user_id, "nickname": "Synthetic role probe"},
            )

    async def request(index: int) -> None:
        auth = identities[index % 2]
        async with user_uow(engine, auth) as uow:
            await _check_identity(uow.session, auth)
            await uow.session.execute(text("select pg_sleep(0.005)"))
            # Intentionally omit owner WHERE: this SELECT must be filtered by
            # PostgreSQL RLS itself, even if a service forgot an owner predicate.
            owners = list(
                (await uow.session.execute(text("select user_id from app.profiles"))).scalars()
            )
            if owners != [auth.user_id]:
                raise RoleProbeError("owner_isolation_failed")
            await _check_identity(uow.session, auth)

    # TaskGroup waits for/cancels sibling requests on failure, so cleanup cannot
    # start while another request is still using the runtime pool.
    async with asyncio.TaskGroup() as group:
        for index in range(REQUESTS):
            group.create_task(request(index))
    await _check_clean_pool(engine)

    for auth in identities:
        async with user_uow(engine, auth) as uow:
            original = await uow.session.scalar(text("select nickname from app.profiles"))
        try:
            async with user_uow(engine, auth) as uow:
                await _check_identity(uow.session, auth)
                await uow.session.execute(
                    text("update app.profiles set nickname=:name where user_id=:id"),
                    {"name": "Synthetic rollback", "id": auth.user_id},
                )
                raise _RollbackProbe
        except _RollbackProbe:
            pass
        await _check_clean_pool(engine)
        async with user_uow(engine, auth) as uow:
            if await uow.session.scalar(text("select nickname from app.profiles")) != original:
                raise RoleProbeError("rollback_did_not_restore_profile")
    return RoleProbeResult(requests=REQUESTS, users=2, checked_connections=2)


async def run_manual(values: Mapping[str, str], http: httpx.AsyncClient) -> RoleProbeResult:
    """Execute only after CLI authorization/local gate; HTTP is outside every UoW."""
    validate_runtime_target(values)
    if values.get("APP_ENV") == "test":
        raise RoleProbeError("hosted_manual_probe_forbids_APP_ENV_test")
    settings = EnvSettings(_env_file=None, **dict(values))
    cfg = AppConfig()
    cfg = replace(cfg, api=replace(cfg.api, db_pool_size=2, db_max_overflow=0))
    base = settings.supabase_url.rstrip("/")
    admin_headers = {
        "apikey": settings.supabase_secret_key.get_secret_value(),
        "Authorization": "Bearer " + settings.supabase_secret_key.get_secret_value(),
    }
    public_headers = {"apikey": settings.supabase_publishable_key}
    verifier = JwtVerifier(settings, cfg, http)
    users: list[UUID] = []
    contexts: list[AuthContext] = []
    engine: AsyncEngine | None = None
    try:
        for _ in range(2):
            email = f"role-probe+{uuid4()}@example.test"
            password = secrets.token_urlsafe(32)
            created = await http.post(
                base + "/auth/v1/admin/users",
                headers=admin_headers,
                json={"email": email, "password": password, "email_confirm": True},
            )
            if created.status_code not in {200, 201}:
                raise RoleProbeError("synthetic_user_creation_failed")
            user_id = UUID(created.json()["id"])
            users.append(user_id)
            signed = await http.post(
                base + "/auth/v1/token?grant_type=password",
                headers=public_headers,
                json={"email": email, "password": password},
            )
            if signed.status_code != 200:
                raise RoleProbeError("synthetic_sign_in_failed")
            context = await verifier.verify(signed.json()["access_token"])
            if context.user_id != user_id:
                raise RoleProbeError("synthetic_user_identity_mismatch")
            contexts.append(context)
        engine = create_engine(settings, cfg)
        async with asyncio.timeout(90):
            return await verify_role_isolation(engine, (contexts[0], contexts[1]))
    finally:
        # Dispose before Auth cleanup: no database transaction spans HTTP calls.
        if engine is not None:
            await engine.dispose()
        failures = 0
        for user_id in users:
            try:
                response = await http.delete(
                    base + f"/auth/v1/admin/users/{user_id}", headers=admin_headers
                )
                if response.status_code not in {200, 204, 404}:
                    failures += 1
            except httpx.HTTPError:
                failures += 1
        if failures:
            raise RoleProbeError("synthetic_cleanup_failed_inspect_role_probe_users")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manual-authorized",
        action="store_true",
        help="Confirm local G0 and dashboard prerequisites were verified before hosted work",
    )
    args = parser.parse_args(argv)
    if not args.manual_authorized:
        parser.error("--manual-authorized is required; this is never an automatic hosted test")
    try:
        values = _guardrails().load_hosted_env()
        mode = validate_runtime_target(values)
        _require_local_gate()

        async def execute() -> RoleProbeResult:
            async with httpx.AsyncClient(timeout=15, follow_redirects=False) as http:
                return await run_manual(values, http)

        result = asyncio.run(execute())
    except RoleProbeError as error:
        print(f"BLOCKED S-05: {error}")
        return 1
    except Exception:
        print("FAILED S-05; connection, credential and upstream details suppressed")
        return 1
    print(
        f"VERIFIED S-05 mode={mode} users={result.users} requests={result.requests} "
        f"checked_connections={result.checked_connections} cleanup=completed"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
