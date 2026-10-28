"""Quarantine checks are test-only; provider work must never replay after a restore."""

import importlib
import sys
from datetime import timedelta
from pathlib import Path

import pytest

from tests.guest_helpers import LIFETIME, add_guest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))


def test_guest_load_rejects_unsafe_targets_and_topologies():
    load = importlib.import_module("load_guest_experience")
    for url in ("postgresql+psycopg://remote.invalid/load_test", "postgresql+psycopg://127.0.0.1/production", "postgresql+psycopg://127.0.0.1/load_test?host=remote.invalid", ""):
        with pytest.raises(ValueError):
            load.validate_target(url, workers=1, users=50)
    for workers, users in ((2, 50), (1, 49)):
        with pytest.raises(ValueError):
            load.validate_target("postgresql+psycopg://127.0.0.1/load_test", workers=workers, users=users)


@pytest.mark.postgres
async def test_restored_expired_guest_denied_before_quarantine_lift(clients):
    from tests.guest_restore_helpers import enforce_quarantine

    app, actors = clients
    guest = await add_guest(app, started_ago=LIFETIME + timedelta(seconds=2))
    assert (await guest.client.get("/api/v1/session")).status_code == 401
    result = await enforce_quarantine(app)
    assert result == {"expiredRemaining": 0, "anonymousRemaining": 0, "providerCallsReplayed": 0}
    assert (await guest.client.get("/api/v1/session")).status_code == 401
    assert (await actors[0][0].get("/api/v1/session")).status_code == 200
