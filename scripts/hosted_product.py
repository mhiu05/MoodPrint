"""Explicit synthetic product checks against the one owner-authorized hosted project.

Never invoked by pytest or the local E2E gate. No migrations, local bootstrap,
Auth settings, email, paid provider calls, or global maintenance are performed.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import secrets
import subprocess
import sys
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
from uuid import UUID, uuid4

import httpx
from dotenv import dotenv_values

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.db.safety import PROJECT_REF, ROOT  # noqa: E402
from scripts.e2e_stack import (  # noqa: E402
    OS_ENVIRONMENT,
    assert_port_free,
    stop_child,
    vite_config,
    wait_ready,
)

API_HOST = f"{PROJECT_REF}.supabase.co"
MANIFEST = ROOT / ".local/product-completion/hosted-users.json"
_manifest_lock = threading.RLock()


def validate_target(values: dict[str, str]) -> None:
    """Runtime role only; migration-role validation remains in scripts/db/safety.py."""
    try:
        api = urlsplit(values.get("SUPABASE_URL", ""))
        db = urlsplit(values.get("DATABASE_URL", ""))
        query = parse_qs(db.query, keep_blank_values=True)
        api_ok = (
            api.scheme == "https"
            and api.hostname == API_HOST
            and api.port in {None, 443}
            and not api.username
            and not api.password
            and api.path in {"", "/"}
            and not api.query
            and not api.fragment
        )
        pooler = (
            db.hostname == "aws-0-ap-northeast-2.pooler.supabase.com"
            and db.username == f"safevoice_api.{PROJECT_REF}"
        )
        direct = db.hostname == f"db.{PROJECT_REF}.supabase.co" and db.username == "safevoice_api"
        db_ok = (
            db.scheme == "postgresql+asyncpg"
            and (pooler or direct)
            and db.port in {None, 5432}
            and bool(db.password)
            and db.path == "/postgres"
            and not db.fragment
            and set(query) <= {"sslmode"}
            and query.get("sslmode", ["require"]) in (["require"], ["verify-full"])
        )
    except ValueError:
        api_ok = db_ok = False
    if not api_ok:
        raise ValueError("SUPABASE_URL must identify the exact audited hosted project")
    if not db_ok:
        raise ValueError("DATABASE_URL must use the audited hosted safevoice_api connection")
    for name in ("SUPABASE_PUBLISHABLE_KEY", "SUPABASE_SECRET_KEY"):
        if not values.get(name):
            raise ValueError(f"Missing {name}")
    if values.get("VITE_PUBLIC_SUPABASE_URL", values["SUPABASE_URL"]).rstrip("/") != values[
        "SUPABASE_URL"
    ].rstrip("/"):
        raise ValueError("Frontend Supabase target differs from the audited backend target")


def load_values() -> dict[str, str]:
    # Owner file is read only. Do not let inherited process secrets override it.
    values = {k: v for k, v in dotenv_values(ROOT / ".env", interpolate=False).items() if v}
    validate_target(values)
    return values


def build_environment(values: dict[str, str], inherited: dict[str, str]) -> dict[str, str]:
    validate_target(values)
    child = {k: v for k, v in inherited.items() if k.upper() in OS_ENVIRONMENT}
    child.update(
        {
            k: values[k]
            for k in (
                "SUPABASE_URL",
                "SUPABASE_PUBLISHABLE_KEY",
                "SUPABASE_SECRET_KEY",
                "DATABASE_URL",
            )
        }
    )
    child.update(
        {
            "APP_ENV": "development",
            "OPENAI_API_KEY": "",
            "APIFY_API_TOKEN": "",
            "VOYAGE_API_KEY": values.get("VOYAGE_API_KEY", ""),
            "OPENAI_AGENTS_DISABLE_TRACING": "1",
            "SAFEVOICE_HOSTED_PRODUCT": "1",
            "PYTHONUNBUFFERED": "1",
            "PYTHONIOENCODING": "utf-8",
            "SAFEVOICE_STACK_NAME": "hosted-product",
            "SAFEVOICE_PORT_OFFSET": "100",
            "CORS_ALLOWED_ORIGINS": "http://127.0.0.1:5183",
            "VITE_PUBLIC_SUPABASE_URL": values["SUPABASE_URL"],
            "VITE_PUBLIC_SUPABASE_PUBLISHABLE_KEY": values["SUPABASE_PUBLISHABLE_KEY"],
            "VITE_PUBLIC_API_BASE_URL": "http://127.0.0.1:8010",
            "E2E_BASE_URL": "http://127.0.0.1:5183",
            "E2E_API_URL": "http://127.0.0.1:8010",
        }
    )
    return child


class ProjectTransport(httpx.AsyncBaseTransport):
    """No redirects, proxies, model endpoints, or alternate Supabase projects."""

    def __init__(self):
        self.transport = httpx.AsyncHTTPTransport(trust_env=False)

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        if (
            request.url.scheme != "https"
            or request.url.host != API_HOST
            or request.url.port not in {None, 443}
            or not re.match(r"^/(auth|storage)/v1/", request.url.path)
        ):
            raise ValueError("HTTP request is outside the audited project")
        return await self.transport.handle_async_request(request)

    async def aclose(self):
        await self.transport.aclose()


def new_manifest() -> dict:
    run_id = uuid4().hex
    return {
        "version": 1,
        "project_ref": PROJECT_REF,
        "run_id": run_id,
        "users": [
            {
                "slot": slot,
                "id": None,
                "email": f"product+{run_id}-{slot}@example.test",
                "password": secrets.token_urlsafe(26) + "aA1!",
                "deleted": False,
            }
            for slot in ("a", "b")
        ],
        "storage_keys": [],
    }


def write_manifest(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2)
        handle.write("\n")
    temporary.replace(path)


def read_manifest(path: Path = MANIFEST, *, require_ready: bool = True) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if (
        data.get("version") != 1
        or data.get("project_ref") != PROJECT_REF
        or not re.fullmatch(r"[0-9a-f]{32}", data.get("run_id", ""))
        or not isinstance(data.get("users"), list)
        or len(data["users"]) != 2
    ):
        raise ValueError("Invalid synthetic hosted manifest")
    ids = []
    for user, slot in zip(data["users"], ("a", "b"), strict=True):
        if (
            user.get("slot") != slot
            or user.get("email") != f"product+{data['run_id']}-{slot}@example.test"
            or not user.get("password")
            or type(user.get("deleted")) is not bool
        ):
            raise ValueError("Invalid synthetic user manifest")
        if user.get("id"):
            ids.append(str(UUID(user["id"])))
        elif require_ready:
            raise ValueError(
                "Synthetic preparation incomplete; inspect local manifest before retry"
            )
    if len(ids) != len(set(ids)):
        raise ValueError("Synthetic user IDs must be unique")
    for key in data.get("storage_keys", []):
        require_storage_key(key, set(ids))
    return data


def require_storage_key(key: str, user_ids: set[str]) -> None:
    if (
        not isinstance(key, str)
        or ".." in key
        or "\\" in key
        or not any(key.startswith(f"users/{user_id}/") for user_id in user_ids)
        or not re.fullmatch(
            r"users/[0-9a-f-]{36}/(?:originals|derived)/[0-9a-f-]{36}/[a-zA-Z0-9_./-]+", key
        )
    ):
        raise ValueError("Storage key is outside the exact synthetic manifest owners")


def record_storage_key(path: Path, key: str) -> None:
    with _manifest_lock:
        data = read_manifest(path)
        require_storage_key(key, {u["id"] for u in data["users"]})
        if key not in data["storage_keys"]:
            data["storage_keys"].append(key)
            write_manifest(path, data)


def headers(values: dict[str, str], *, admin: bool = False) -> dict[str, str]:
    key = values["SUPABASE_SECRET_KEY" if admin else "SUPABASE_PUBLISHABLE_KEY"]
    return {"apikey": key, **({"Authorization": "Bearer " + key} if admin else {})}


async def prepare(values: dict[str, str], path: Path, http: httpx.AsyncClient) -> None:
    validate_target(values)
    if await asyncio.to_thread(path.exists):
        data = read_manifest(path)
        if any(u["deleted"] for u in data["users"]):
            raise ValueError(
                "This run was cleaned; retain its manifest and choose a new run explicitly"
            )
        return
    data = new_manifest()
    path.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive reservation prevents simultaneous prepare processes creating duplicates.
    with path.open("x", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2)
    for user in data["users"]:
        response = await http.post(
            values["SUPABASE_URL"].rstrip("/") + "/auth/v1/admin/users",
            headers=headers(values, admin=True),
            json={
                "email": user["email"],
                "password": user["password"],
                "email_confirm": True,
                "user_metadata": {
                    "nickname": f"Hosted synthetic {user['slot'].upper()}",
                    "age_band": "14-17",
                },
                "app_metadata": {"synthetic_product_run": data["run_id"]},
            },
        )
        if response.status_code not in {200, 201}:
            raise RuntimeError(
                "Synthetic Auth preparation failed; details suppressed; retain local manifest"
            )
        user["id"] = str(UUID(response.json()["id"]))
        write_manifest(path, data)


async def token_for(values: dict[str, str], user: dict, http: httpx.AsyncClient) -> str:
    response = await http.post(
        values["SUPABASE_URL"].rstrip("/") + "/auth/v1/token?grant_type=password",
        headers=headers(values),
        json={"email": user["email"], "password": user["password"]},
    )
    if response.status_code != 200 or response.json().get("user", {}).get("id") != user["id"]:
        raise RuntimeError("Synthetic sign-in failed; details suppressed")
    return response.json()["access_token"]


async def run_checks(values: dict[str, str], path: Path, *, cleanup: bool = False) -> None:
    from scripts.hosted_product_app import create_app

    data = read_manifest(path, require_ready=not cleanup)
    app = create_app(values, path, allow_incomplete=cleanup)
    async with httpx.AsyncClient(transport=ProjectTransport(), timeout=30) as upstream:
        async with app.router.lifespan_context(app):
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app), base_url="http://synthetic-api"
            ) as api:
                tokens = []
                for user in data["users"]:
                    if user["deleted"] or not user["id"]:
                        continue
                    if cleanup:
                        exists = await upstream.get(
                            values["SUPABASE_URL"].rstrip("/")
                            + "/auth/v1/admin/users/"
                            + user["id"],
                            headers=headers(values, admin=True),
                        )
                        if exists.status_code == 404:
                            user["deleted"] = True
                            write_manifest(path, data)
                            continue
                        if exists.status_code != 200 or exists.json().get("id") != user["id"]:
                            raise RuntimeError("Exact synthetic user check failed")
                    token = await token_for(values, user, upstream)
                    auth = {"Authorization": "Bearer " + token}
                    if cleanup:
                        # Account API queries/deletes only this exact synthetic owner, including Storage.
                        response = await api.request(
                            "DELETE", "/v1/me", headers=auth, json={"confirm": "DELETE"}
                        )
                        if response.status_code != 204:
                            raise RuntimeError(
                                f"Synthetic account cleanup failed (HTTP {response.status_code}); keep manifest"
                            )
                        user["deleted"] = True
                        write_manifest(path, data)
                    else:
                        response = await api.get("/v1/me", headers=auth)
                        if response.status_code != 200:
                            raise RuntimeError(
                                f"Synthetic profile check failed (HTTP {response.status_code})"
                            )
                        tokens.append(auth)
                if not cleanup:
                    created = await api.post(
                        "/v1/memories",
                        headers=tokens[0],
                        json={
                            "category": "preference",
                            "content": "Synthetic hosted product preference",
                        },
                    )
                    if created.status_code != 200:
                        raise RuntimeError(
                            f"Synthetic memory creation failed (HTTP {created.status_code})"
                        )
                    memory_id = str(UUID(created.json()["id"]))
                    foreign = await api.patch(
                        f"/v1/memories/{memory_id}",
                        headers=tokens[1],
                        json={"content": "Forbidden synthetic update"},
                    )
                    removed = await api.delete(f"/v1/memories/{memory_id}", headers=tokens[0])
                    if foreign.status_code != 404 or removed.status_code != 204:
                        raise RuntimeError("Synthetic memory isolation or deletion failed")
    # Keep exact paths as a receipt, including already-deleted object names. Never list a bucket.
    print(
        "VERIFIED synthetic cleanup"
        if cleanup
        else "VERIFIED real hosted Auth, profiles, memory lifecycle and cross-user isolation"
    )


@contextmanager
def running_hosted_stack(environment: dict[str, str]):
    output = ROOT / ".local/product-completion"
    output.mkdir(parents=True, exist_ok=True)
    for port in (8010, 5183):
        assert_port_free(port)
    npm = "npm.cmd" if os.name == "nt" else "npm"
    commands = [
        (
            [
                sys.executable,
                "-c",
                "import uvicorn; uvicorn.run('scripts.hosted_product_app:create_app', factory=True, host='127.0.0.1', port=8010, access_log=False)",
            ],
            ROOT,
            "api",
            "http://127.0.0.1:8010/ready",
        ),
        (
            [
                npm,
                "run",
                "dev",
                "--",
                "--config",
                str(vite_config(output)),
                "--mode",
                "test",
                "--host",
                "127.0.0.1",
                "--port",
                "5183",
                "--strictPort",
            ],
            ROOT / "frontend",
            "vite",
            "http://127.0.0.1:5183",
        ),
    ]
    processes, handles = [], []
    try:
        for command, cwd, name, ready in commands:
            handle = (output / f"hosted-{name}.log").open("w", encoding="utf-8")
            handles.append(handle)
            process = subprocess.Popen(
                command,
                cwd=cwd,
                env=environment,
                stdout=handle,
                stderr=subprocess.STDOUT,
                start_new_session=os.name != "nt",
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
            processes.append(process)
            wait_ready(ready, process)
        yield
    finally:
        for process in reversed(processes):
            stop_child(process)
        for handle in handles:
            handle.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    for name in ("prepare", "serve", "run", "cleanup"):
        action.add_argument("--" + name, action="store_true")
    args = parser.parse_args()
    try:
        values = load_values()
        if args.prepare:

            async def create():
                async with httpx.AsyncClient(transport=ProjectTransport(), timeout=30) as http:
                    await prepare(values, MANIFEST, http)

            asyncio.run(create())
            print(
                "Synthetic users ready; credentials retained only in .local/product-completion/hosted-users.json"
            )
        elif args.serve:
            read_manifest()
            # Reuse only process/port management; no local hooks, seed, reset, or bootstrap.
            environment = build_environment(values, dict(os.environ))
            with running_hosted_stack(environment):
                print(
                    "Hosted synthetic seam ready. Credentials are in the local manifest. Ctrl+C stops both children.",
                    flush=True,
                )
                while True:
                    time.sleep(1)
        else:
            asyncio.run(run_checks(values, MANIFEST, cleanup=args.cleanup))
        return 0
    except KeyboardInterrupt:
        return 130
    except Exception:
        print(
            "Hosted product operation failed; details suppressed to protect credentials. Retain the local manifest.",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
