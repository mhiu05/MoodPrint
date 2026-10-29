"""Legacy personal switches must not prevent using the personal features."""

from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.ai.persistence import preference_view
from app.core.config import Settings
from app.core.errors import DomainError
from app.core.security import assert_purpose
from app.infrastructure.database.models import Consent


@pytest.mark.parametrize("purpose", ["AI", "MEM", "VOICE"])
async def test_legacy_disabled_personal_consent_allows_feature(purpose):
    user = SimpleNamespace(id=uuid4(), age_band="adult", social_restricted_until=None)
    rows = [Consent(user_id=user.id, purpose=p, enabled=False, version=1)
            for p in ("AI", "MEM", "VOICE", "MATCH")]
    db = SimpleNamespace(scalars=AsyncMock(return_value=SimpleNamespace(all=lambda: rows)))
    result = await assert_purpose(db, user, purpose)
    assert result[purpose].version == 1


async def test_social_publication_still_requires_its_own_permission():
    user = SimpleNamespace(id=uuid4(), age_band="adult", social_restricted_until=None)
    rows = [Consent(user_id=user.id, purpose="MATCH", enabled=False, version=1)]
    db = SimpleNamespace(scalars=AsyncMock(return_value=SimpleNamespace(all=lambda: rows)))
    with pytest.raises(DomainError) as failure:
        await assert_purpose(db, user, "MATCH")
    assert failure.value.code == "CONSENT_REQUIRED"


@pytest.mark.parametrize("legacy", [None, SimpleNamespace(
    history_enabled=False, semantic_memory_enabled=False, version=2, policy_version="ai-data-v1"
)])
def test_saved_history_is_available_without_a_user_switch(legacy):
    settings = Settings(_env_file=None)
    view = preference_view(legacy, settings)
    assert view.history_enabled is True
    assert view.history_available is True


def test_saved_history_respects_service_availability():
    view = preference_view(None, Settings(_env_file=None, chat_history_enabled=False))
    assert view.history_enabled is False
    assert view.history_available is False


@pytest.mark.postgres
async def test_legacy_personal_switches_cannot_disable_a_new_chat(clients):
    from app.ai.models import AiPreference
    from tests.fakes import make_test_model

    app, actors = clients
    client, user_id = actors[0]
    app.state.ai.model_override = make_test_model("Synthetic reply")
    async with app.state.database.sessions.begin() as db:
        db.add(AiPreference(user_id=user_id, history_enabled=False,
                            semantic_memory_enabled=False, version=1))
    for purpose in ("AI", "MEM", "VOICE"):
        response = await client.put(f"/api/v1/consents/{purpose}", headers={"Idempotency-Key": str(uuid4())},
                                    json={"enabled": False, "expectedVersion": 1, "policyVersion": "v1"})
        assert response.status_code == 200, response.text
        assert response.json()["consents"][purpose]["enabled"] is True
    created = await client.post("/api/v1/ai/conversations", json={"botId": "may"},
                                headers={"Idempotency-Key": str(uuid4())})
    assert created.status_code == 201, created.text
    assert created.json()["persistent"] is True


@pytest.mark.postgres
async def test_personal_history_switch_cannot_disable_saving(clients):
    _, actors = clients
    client, _ = actors[0]
    response = await client.put("/api/v1/ai/preferences", headers={"Idempotency-Key": str(uuid4())},
                                json={"historyEnabled": False, "semanticMemoryEnabled": False,
                                      "expectedVersion": 1, "policyVersion": "ai-data-v1"})
    assert response.status_code == 200, response.text
    assert response.json()["historyEnabled"] is True
