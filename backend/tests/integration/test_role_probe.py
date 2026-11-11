"""S-05 detects claim leaks on real local PostgreSQL and refuses unsafe targets.

Breaks caught: accepting a foreign runtime endpoint, creating Auth users before
credentials are checked, or reporting a role probe without verifying RLS and
transaction cleanup. Importing the manual script must never read owner secrets.
"""

import importlib.util
import sys
from pathlib import Path

import pytest
from app.core.uow import user_uow
from sqlalchemy import text


def load_probe():
    path = Path(__file__).resolve().parents[3] / "scripts/spikes/verify_hosted_role.py"
    assert path.exists(), "S-05 executable role probe has not been implemented"
    spec = importlib.util.spec_from_file_location("hosted_role_probe", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def probe():
    return load_probe()


def hosted_values() -> dict[str, str]:
    return {
        "SUPABASE_URL": "https://xhlshihobyxrgfqrdafh.supabase.co",
        "SUPABASE_DB_URL": "postgresql://postgres.xhlshihobyxrgfqrdafh:synthetic-admin@aws-0-ap-northeast-2.pooler.supabase.com:5432/postgres",
        "DATABASE_URL": "postgresql+asyncpg://safevoice_api.xhlshihobyxrgfqrdafh:synthetic-runtime@aws-0-ap-northeast-2.pooler.supabase.com:5432/postgres",
    }


def test_missing_runtime_credential_is_rejected_before_http() -> None:
    probe = load_probe()
    values = hosted_values()
    del values["DATABASE_URL"]
    with pytest.raises(ValueError, match="DATABASE_URL"):
        probe.validate_runtime_target(values)


@pytest.mark.parametrize(
    "runtime",
    [
        "postgresql+asyncpg://safevoice_api:synthetic-runtime@db.otherproject.supabase.co:5432/postgres",
        "postgresql+asyncpg://safevoice_api.otherproject:synthetic-runtime@aws-0-ap-northeast-2.pooler.supabase.com:5432/postgres",
        "postgresql+asyncpg://postgres.xhlshihobyxrgfqrdafh:synthetic-runtime@aws-0-ap-northeast-2.pooler.supabase.com:5432/postgres",
    ],
)
def test_foreign_or_privileged_runtime_is_rejected(probe, runtime: str) -> None:
    values = hosted_values()
    values["DATABASE_URL"] = runtime
    with pytest.raises(ValueError) as caught:
        probe.validate_runtime_target(values)
    assert "synthetic-runtime" not in str(caught.value)


@pytest.mark.parametrize(
    ("runtime", "mode"),
    [
        (
            "postgresql+asyncpg://safevoice_api.xhlshihobyxrgfqrdafh:synthetic-runtime@aws-0-ap-northeast-2.pooler.supabase.com:5432/postgres",
            "session_pooler",
        ),
        (
            "postgresql+asyncpg://safevoice_api.xhlshihobyxrgfqrdafh:synthetic-runtime@aws-0-ap-northeast-2.pooler.supabase.com:6543/postgres",
            "transaction_pooler",
        ),
        (
            "postgresql+asyncpg://safevoice_api:synthetic-runtime@db.xhlshihobyxrgfqrdafh.supabase.co:5432/postgres",
            "direct",
        ),
    ],
)
def test_approved_modes_remain_explicit(probe, runtime: str, mode: str) -> None:
    values = hosted_values()
    values["DATABASE_URL"] = runtime
    assert probe.validate_runtime_target(values) == mode


def test_cli_requires_manual_authorization_before_loading_owner_env(probe, capsys) -> None:
    with pytest.raises(SystemExit) as caught:
        probe.main([])
    assert caught.value.code == 2
    assert "--manual-authorized" in capsys.readouterr().err


@pytest.mark.integration
async def test_role_probe_checks_50_interleaved_requests_and_rolls_back(
    probe, db_engine, identities
) -> None:
    result = await probe.verify_role_isolation(db_engine, tuple(identities))
    assert result.requests == 50
    assert result.users == 2
    assert result.checked_connections == 2
    assert db_engine.pool.checkedout() == 0
    for auth in identities:
        async with user_uow(db_engine, auth) as uow:
            row = (
                await uow.session.execute(text("select user_id,nickname from app.profiles"))
            ).one()
            assert row.user_id == auth.user_id
            assert row.nickname == "Synthetic role probe"


@pytest.mark.integration
async def test_role_probe_rejects_mismatched_claims(probe, db_engine, identities) -> None:
    from dataclasses import replace

    incorrect = replace(identities[1], claims_json=identities[0].claims_json)
    with pytest.raises(probe.RoleProbeError, match="identity"):
        await probe.verify_role_isolation(db_engine, (identities[0], incorrect))
    assert db_engine.pool.checkedout() == 0
