"""Credential setup must fail before mutations on unsafe input or identity."""

import importlib.util
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

import pytest
from dotenv import dotenv_values

DB = Path(__file__).parents[1]


def load_script(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


safety = load_script("credential_safety", DB / "safety.py")
with patch.dict(sys.modules, {"safety": safety}):
    provisioner = load_script("credential_provisioner", DB / "set_api_role_password.py")

PLACEHOLDER = dotenv_values(DB.parents[1] / ".env.example")["DATABASE_URL"]
ADMIN = (
    "postgresql://postgres.xhlshihobyxrgfqrdafh:synthetic%40password"
    "@aws-0-ap-northeast-2.pooler.supabase.com:5432/postgres"
)


@pytest.fixture
def setup(tmp_path, monkeypatch):
    env = {
        "SUPABASE_URL": "https://xhlshihobyxrgfqrdafh.supabase.co",
        "SUPABASE_DB_URL": ADMIN,
    }
    path = tmp_path / ".env"
    path.write_bytes(b"# owner\r\nOPENAI_API_KEY=synthetic-key\r\n")
    events = []
    identity = {"database": "postgres", "role": "postgres", "login": "postgres"}
    role = {
        "rolsuper": False,
        "rolcreatedb": False,
        "rolcreaterole": False,
        "rolreplication": False,
        "rolbypassrls": False,
        "rolinherit": False,
    }

    class Connection:
        @asynccontextmanager
        async def transaction(self):
            try:
                yield
            except Exception:
                events.append("rollback")
                raise
            else:
                events.append("commit")

        async def fetchrow(self, query):
            return identity if "current_database()" in query else role

        async def fetchval(self, query, password):
            return "'" + password + "'"

        async def execute(self, query):
            events.append("alter")

        async def close(self):
            events.append("close")

    async def connect(*args, **kwargs):
        events.append("connect")
        return Connection()

    monkeypatch.setattr(provisioner, "ROOT", tmp_path)
    monkeypatch.setattr(provisioner, "load_hosted_env", lambda: env)
    monkeypatch.setattr(provisioner.asyncpg, "connect", connect)
    return env, path, events, identity, role


async def test_template_placeholder_is_replaced_without_rotation(setup, capsys):
    env, path, events, _, _ = setup
    env["DATABASE_URL"] = PLACEHOLDER
    original = path.read_bytes()
    path.write_bytes(original + f"DATABASE_URL={PLACEHOLDER}\r\n".encode())
    await provisioner.provision(rotate=False)
    result = path.read_bytes()
    assert result.startswith(original)
    runtime = dotenv_values(path)["DATABASE_URL"]
    parsed = urlsplit(runtime)
    assert parsed.scheme == "postgresql+asyncpg"
    assert parsed.username == "moodprint_api.xhlshihobyxrgfqrdafh"
    assert parsed.hostname == "aws-0-ap-northeast-2.pooler.supabase.com"
    assert parsed.port == 5432 and parsed.path == "/postgres"
    assert parsed.password and len(parsed.password) >= 43
    assert parse_qs(parsed.query)["sslmode"] == ["require"]
    assert events == ["connect", "alter", "commit", "close"]
    assert parsed.password not in capsys.readouterr().out


@pytest.mark.parametrize("rotate", [False, True])
async def test_owner_credentials_are_preserved(setup, rotate):
    env, path, events, _, _ = setup
    env["DATABASE_URL"] = "postgresql://postgres:synthetic-owner@db.other/postgres"
    original = path.read_bytes()
    with pytest.raises(ValueError):
        await provisioner.provision(rotate=rotate)
    assert not events
    assert path.read_bytes() == original


@pytest.mark.parametrize(
    "admin",
    [
        ADMIN.replace("/postgres", "/other"),
        ADMIN.replace(":5432/", ":6543/"),
        ADMIN.replace("ap-northeast-2", "ap-southeast-1"),
        ADMIN.replace("xhlshihobyxrgfqrdafh", "otherproject"),
        ADMIN + "?host=db.other.supabase.co",
        ADMIN.replace("synthetic%40password", "synthetic%ZZpassword"),
    ],
)
async def test_invalid_target_rejected_before_connecting(setup, admin):
    env, _, events, _, _ = setup
    env["SUPABASE_DB_URL"] = admin
    with pytest.raises(ValueError):
        await provisioner.provision(rotate=False)
    assert not events


@pytest.mark.parametrize(
    "key,value", [("database", "other"), ("role", "other"), ("login", "other")]
)
async def test_server_identity_checked_before_mutation(setup, key, value):
    _, path, events, identity, _ = setup
    identity[key] = value
    original = path.read_bytes()
    with pytest.raises(ValueError, match="identity"):
        await provisioner.provision(rotate=False)
    assert "alter" not in events
    assert "close" in events
    assert path.read_bytes() == original


@pytest.mark.parametrize(
    "attribute",
    ["rolsuper", "rolcreatedb", "rolcreaterole", "rolreplication", "rolbypassrls", "rolinherit"],
)
async def test_privileged_runtime_role_is_not_provisioned(setup, attribute):
    _, _, events, _, role = setup
    role[attribute] = True
    with pytest.raises(ValueError, match="restricted"):
        await provisioner.provision(rotate=False)
    assert "alter" not in events


async def test_duplicate_env_entries_rejected_before_database_change(setup):
    _, path, events, _, _ = setup
    original = b"DATABASE_URL=\r\nDATABASE_URL=\r\n"
    path.write_bytes(original)
    with pytest.raises(ValueError, match="Duplicate"):
        await provisioner.provision(rotate=False)
    assert not events
    assert path.read_bytes() == original


async def test_file_write_failure_rolls_back_role_change(setup, monkeypatch):
    _, path, events, _, _ = setup
    original = path.read_bytes()
    write = provisioner.write_generated_database_url

    def fail_write(*args, **kwargs):
        if kwargs.get("dry_run"):
            return write(*args, **kwargs)
        raise OSError("synthetic write failure")

    monkeypatch.setattr(provisioner, "write_generated_database_url", fail_write)
    with pytest.raises(OSError):
        await provisioner.provision(rotate=False)
    assert events == ["connect", "alter", "rollback", "close"]
    assert path.read_bytes() == original
