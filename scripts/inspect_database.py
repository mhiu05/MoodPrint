"""Bounded read-only probes. Never print URLs, credentials or raw provider errors."""

import argparse
import asyncio
import json
import socket
import ssl
import struct
import sys
from pathlib import Path
from urllib.parse import urlparse

import httpx
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from app.core.config import Settings  # noqa: E402
from app.core.revisions import READY_REVISIONS  # noqa: E402


def error_details(error):
    original = getattr(error, "orig", error)
    state = getattr(original, "sqlstate", None)
    message = str(original).lower()
    categories = {
        "authentication": ("password authentication failed",),
        "dns": ("could not translate host", "getaddrinfo", "name or service not known"),
        "timeout": ("timeout", "timed out"),
        "network": ("network is unreachable", "network unreachable", "no route"),
        "tls": ("certificate", "ssl", "tls"),
        "refused": ("connection refused", "actively refused"),
        "pooler_identity": ("tenant or user not found",),
    }
    category = next(
        (key for key, hints in categories.items() if any(hint in message for hint in hints)),
        "unclassified",
    )
    if state == "42501":
        category = "permission"
    elif state and state.startswith("28"):
        category = "authentication"
    elif isinstance(error, TimeoutError):
        category = "timeout"
    elif isinstance(original, socket.gaierror):
        category = "dns"
    return {"errorType": type(error).__name__, "sqlState": state, "errorCategory": category}


async def network_probe(host, port):
    result = {}
    writer = None
    try:
        async with asyncio.timeout(5):
            addresses = await asyncio.get_running_loop().getaddrinfo(
                host, port, type=socket.SOCK_STREAM
            )
        result["dns"] = {
            "status": "resolved",
            "families": sorted(
                {"IPv6" if row[0] == socket.AF_INET6 else "IPv4" for row in addresses}
            ),
        }
    except Exception as error:
        return {"dns": {"status": "failed", **error_details(error)}}
    try:
        async with asyncio.timeout(6):
            reader, writer = await asyncio.open_connection(host, port)
            result["tcp"] = {
                "status": "connected",
                "family": "IPv6"
                if writer.get_extra_info("socket").family == socket.AF_INET6
                else "IPv4",
            }
            # PostgreSQL SSLRequest, with no username/password or application data.
            writer.write(struct.pack("!II", 8, 80877103))
            await writer.drain()
            if await reader.readexactly(1) != b"S":
                result["tls"] = {"status": "refused"}
            else:
                result["tls"] = {"status": "supported", "certificateVerified": False}
                await writer.start_tls(ssl.create_default_context(), server_hostname=host)
                tls = writer.get_extra_info("ssl_object")
                result["tls"] = {
                    "status": "verified",
                    "certificateVerified": True,
                    "protocol": tls.version(),
                }
    except Exception as error:
        stage = "tls" if "tcp" in result else "tcp"
        result[stage] = {**result.get(stage, {}), "status": "failed", **error_details(error)}
    finally:
        if writer:
            writer.close()
    return result


async def inspect_target(secret, config):
    if not secret or not secret.get_secret_value():
        return {"status": "missing"}
    raw = (
        secret.get_secret_value()
        .replace("postgres://", "postgresql+psycopg://", 1)
        .replace("postgresql://", "postgresql+psycopg://", 1)
    )
    target = make_url(raw)
    auth_host = urlparse(config.supabase_url).hostname or ""
    project = auth_host.removesuffix(".supabase.co") if auth_host.endswith(".supabase.co") else None
    expected = bool(
        project
        and (
            target.host == f"db.{project}.supabase.co"
            or (
                (target.host or "").endswith(".pooler.supabase.com")
                and (target.username or "").endswith(f".{project}")
            )
        )
    )
    entry = {
        "status": "unverified",
        "local": target.host in ("localhost", "127.0.0.1", "::1"),
        "matchesAuthProject": expected,
        "tlsMode": target.query.get("sslmode", "prefer"),
        "network": await network_probe(target.host, target.port or 5432),
    }
    engine = create_async_engine(
        raw, hide_parameters=True, connect_args={"connect_timeout": 5, "prepare_threshold": None}
    )
    connected = False
    try:
        async with asyncio.timeout(12), engine.connect() as db, db.begin():
            connected = True
            await db.execute(text("SET TRANSACTION READ ONLY"))
            await db.execute(text("SET LOCAL statement_timeout = '5s'"))
            role = (
                (
                    await db.execute(
                        text(
                            "select current_database() as database, current_user as role, version() as postgres_version, "
                            "rolsuper as superuser, rolcreatedb as can_create_database, rolcreaterole as can_create_role, "
                            "rolbypassrls as bypass_rls from pg_roles where rolname=current_user"
                        )
                    )
                )
                .mappings()
                .one()
            )
            schema = await db.scalar(
                text("select exists(select 1 from pg_namespace where nspname='moodprint')")
            )
            history = await db.scalar(
                text("select to_regclass('moodprint.alembic_version') is not null")
            )
            entry.update(
                {
                    "status": "connected",
                    "authentication": "passed",
                    "identity": dict(role),
                    "schemaExists": schema,
                    "migrationHistoryExists": history,
                }
            )
            entry["authSessionAccess"] = await db.scalar(
                text(
                    "select has_schema_privilege(current_user,'auth','USAGE') and "
                    "has_column_privilege(current_user,(select c.oid from pg_class c join pg_namespace n on n.oid=c.relnamespace where n.nspname='auth' and c.relname='sessions'),'id','SELECT') and "
                    "has_column_privilege(current_user,(select c.oid from pg_class c join pg_namespace n on n.oid=c.relnamespace where n.nspname='auth' and c.relname='sessions'),'user_id','SELECT')"
                )
            )
            bridge = await db.scalar(
                text(
                    "select to_regprocedure('moodprint.is_provider_session_active(uuid,uuid)') is not null"
                )
            )
            entry["privateAuthBridgeExists"] = bridge
            entry["authSessionsRlsEnabled"] = await db.scalar(
                text("select c.relrowsecurity from pg_class c join pg_namespace n on n.oid=c.relnamespace where n.nspname='auth' and c.relname='sessions'")
            )
            entry["privateAuthBridgeExecutable"] = bool(
                bridge
                and await db.scalar(
                    text(
                        "select has_function_privilege(current_user,'moodprint.is_provider_session_active(uuid,uuid)','EXECUTE')"
                    )
                )
            )
            if history:
                entry["revisions"] = list(
                    (
                        await db.scalars(text("select version_num from moodprint.alembic_version"))
                    ).all()
                )
                entry["migrationReadiness"] = (
                    "head_matches"
                    if len(entry["revisions"]) == 1 and entry["revisions"][0] in READY_REVISIONS
                    else "revision_drift"
                )
                if entry["migrationReadiness"] == "head_matches" and not bridge:
                    entry["migrationReadiness"] = "auth_security_bootstrap_required"
            else:
                entry["migrationReadiness"] = (
                    "not_initialized" if not schema else "unversioned_schema_review_required"
                )
            entry["domainTables"] = list(
                (
                    await db.scalars(
                        text(
                            "select tablename from pg_tables where schemaname='moodprint' order by tablename"
                        )
                    )
                ).all()
            )
            if schema:
                entry["canCreateInDomainSchema"] = await db.scalar(
                    text("select has_schema_privilege(current_user,'moodprint','CREATE')")
                )
    except Exception as error:
        details = error_details(error)
        entry.update(
            {
                "status": "inspection_failed" if connected else "connection_failed",
                "authentication": "passed"
                if connected
                else "failed"
                if details["errorCategory"] == "authentication"
                else "not_verified",
                **details,
            }
        )
    finally:
        await engine.dispose()
    return entry


async def inspect():
    config = Settings(_env_file=ROOT / "backend/.env")
    result = {"readOnly": True, "ddlPerformed": False, "modelCalls": 0}
    fields = ("database_url", "database_migration_url")
    values = await asyncio.gather(*(inspect_target(getattr(config, f), config) for f in fields))
    result.update(zip(fields, values, strict=True))
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(
                f"{config.supabase_url}/auth/v1/settings",
                headers={"apikey": config.supabase_publishable_key.get_secret_value()},
            )
            result["authSettings"] = {
                "httpStatus": response.status_code,
                "emailProviderEnabled": response.json().get("external", {}).get("email")
                if response.status_code == 200
                else None,
            }
    except Exception as error:
        result["authSettings"] = {"status": "unavailable", "errorType": type(error).__name__}
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output", type=Path, help="Write the same sanitized JSON report to a local artifact"
    )
    args = parser.parse_args()
    try:
        report = asyncio.run(inspect(), loop_factory=asyncio.SelectorEventLoop)
        serialized = json.dumps(report, indent=2) + "\n"
        if args.output:
            args.output.write_text(serialized, encoding="utf-8")
        print(serialized, end="")
        sys.exit(
            0
            if all(
                report[f]["status"] == "connected"
                for f in ("database_url", "database_migration_url")
            )
            else 1
        )
    except Exception as error:
        print(json.dumps({"status": "configuration_invalid", "errorType": type(error).__name__}))
        sys.exit(1)
