"""P2-02: per-edge sharing opt-in — default off, versioned, idempotent, revocation cancels runs."""

import asyncio
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select

from tests.conftest import add_actor
from tests.test_proactive_api import settings_body

BASE = "/api/v1/ai/sharing"


def key():
    return {"Idempotency-Key": str(uuid4())}


def body(enabled=True, version=0, **extra):
    return {"enabled": enabled, "expectedVersion": version, "policyVersion": "sharing-v1", **extra}


def on(app, **overrides):
    from tests.fakes import make_test_model

    app.state.settings.ai_multi_message_enabled = True
    app.state.settings.ai_collaboration_enabled = True
    app.state.settings.proactive_enabled = True
    app.state.ai.model_override = make_test_model("ok")
    for name, value in overrides.items():
        setattr(app.state.settings, name, value)


def edge(view, name):
    return next(item for item in view["edges"] if item["edge"] == name)


async def journal_context(client, enabled=True):
    current = (await client.get("/api/v1/ai/proactive")).json()["settings"]["version"]
    response = await client.put("/api/v1/ai/proactive/settings",
                                json=settings_body(journalContextEnabled=enabled, expectedVersion=current),
                                headers=key())
    assert response.status_code == 200, response.text


async def test_new_account_has_every_edge_off_and_no_caunoi_edge(clients):
    app, [(client, _), _] = clients
    on(app)
    response = await client.get(BASE)
    assert response.status_code == 200, response.text
    view = response.json()
    assert view["available"] is True
    assert [(e["edge"], e["requester"], e["specialist"], e["enabled"], e["version"]) for e in view["edges"]] == [
        ("nhip_energy_for_rure", "rure", "nhip", False, 0),
        ("nhip_habit_for_may", "may", "nhip", False, 0),
        ("rure_activity_for_guong", "guong", "rure", False, 0),
    ]
    energy = edge(view, "nhip_energy_for_rure")
    assert energy["requires"] == ["journal_context"] and energy["available"] is False
    assert energy["reason"] == "journal_context_off"
    assert edge(view, "nhip_habit_for_may")["available"] is True
    assert all("caunoi" not in (e["requester"], e["specialist"]) for e in view["edges"])


async def test_enable_and_disable_one_edge_with_versions(clients):
    from app.ai.collaboration.models import AiSharingPermission

    app, [(client, uid), (other, other_uid)] = clients
    on(app)
    response = await client.put(f"{BASE}/nhip_habit_for_may", json=body(True, 0), headers=key())
    assert response.status_code == 200, response.text
    assert edge(response.json(), "nhip_habit_for_may") | {} == {
        **edge(response.json(), "nhip_habit_for_may"), "enabled": True, "version": 1}
    # Another account is unaffected.
    assert edge((await other.get(BASE)).json(), "nhip_habit_for_may")["enabled"] is False
    stale = await client.put(f"{BASE}/nhip_habit_for_may", json=body(False, 0), headers=key())
    assert stale.status_code == 409 and stale.json()["error"]["code"] == "STALE_VERSION"
    off = await client.put(f"{BASE}/nhip_habit_for_may", json=body(False, 1), headers=key())
    assert off.status_code == 200 and edge(off.json(), "nhip_habit_for_may")["version"] == 2
    async with app.state.database.sessions() as db:
        rows = (await db.scalars(select(AiSharingPermission))).all()
    assert [(r.user_id, r.edge, r.enabled, r.version, r.policy_version) for r in rows] == [
        (uid, "nhip_habit_for_may", False, 2, "sharing-v1")]
    assert other_uid not in {r.user_id for r in rows}


async def test_unknown_or_forbidden_edge_is_404(clients):
    app, [(client, _), _] = clients
    on(app)
    for name in ("caunoi_mood_for_rure", "nhip_energy_for_caunoi", "may_journal_for_nhip"):
        response = await client.put(f"{BASE}/{name}", json=body(), headers=key())
        assert response.status_code == 404, name


async def test_policy_version_and_extra_fields_are_rejected(clients):
    app, [(client, _), _] = clients
    on(app)
    assert (await client.put(f"{BASE}/nhip_habit_for_may", json=body(policyVersion="sharing-v0"),
                             headers=key())).status_code == 422
    assert (await client.put(f"{BASE}/nhip_habit_for_may", json=body(scope="all"), headers=key())).status_code == 422


async def test_idempotent_replay_returns_the_same_result(clients):
    app, [(client, _), _] = clients
    on(app)
    headers = key()
    first = await client.put(f"{BASE}/nhip_habit_for_may", json=body(True, 0), headers=headers)
    again = await client.put(f"{BASE}/nhip_habit_for_may", json=body(True, 0), headers=headers)
    assert first.status_code == again.status_code == 200
    assert edge(again.json(), "nhip_habit_for_may")["version"] == 1
    conflict = await client.put(f"{BASE}/nhip_habit_for_may", json=body(False, 0), headers=headers)
    assert conflict.status_code == 409


async def test_energy_edge_requires_journal_context(clients):
    app, [(client, _), _] = clients
    on(app)
    refused = await client.put(f"{BASE}/nhip_energy_for_rure", json=body(True, 0), headers=key())
    assert refused.status_code == 409
    assert refused.json()["error"]["code"] == "SHARING_REQUIRES_JOURNAL_CONTEXT"
    await journal_context(client, True)
    view = (await client.get(BASE)).json()
    assert edge(view, "nhip_energy_for_rure")["available"] is True
    accepted = await client.put(f"{BASE}/nhip_energy_for_rure", json=body(True, 0), headers=key())
    assert accepted.status_code == 200 and edge(accepted.json(), "nhip_energy_for_rure")["enabled"] is True
    # Turning journal context off later keeps the opt-in but makes the edge unusable.
    await journal_context(client, False)
    energy = edge((await client.get(BASE)).json(), "nhip_energy_for_rure")
    assert energy["enabled"] is True and energy["available"] is False and energy["reason"] == "journal_context_off"


async def test_flag_off_reads_unavailable_refuses_enable_but_always_allows_disable(clients):
    app, [(client, _), _] = clients
    on(app)
    assert (await client.put(f"{BASE}/nhip_habit_for_may", json=body(True, 0), headers=key())).status_code == 200
    app.state.settings.ai_collaboration_enabled = False
    view = (await client.get(BASE)).json()
    assert view["available"] is False and all(not e["available"] for e in view["edges"])
    assert edge(view, "nhip_habit_for_may")["reason"] == "feature_unavailable"
    refused = await client.put(f"{BASE}/rure_activity_for_guong", json=body(True, 0), headers=key())
    assert refused.status_code == 503 and refused.json()["error"]["code"] == "COLLABORATION_UNAVAILABLE"
    # Revocation never depends on the feature flag.
    off = await client.put(f"{BASE}/nhip_habit_for_may", json=body(False, 1), headers=key())
    assert off.status_code == 200 and edge(off.json(), "nhip_habit_for_may")["enabled"] is False


async def test_rollout_cohort_limits_enabling(clients):
    app, [(client, uid), (other, _)] = clients
    on(app, ai_collaboration_rollout_user_ids=[uid])
    assert (await client.put(f"{BASE}/nhip_habit_for_may", json=body(), headers=key())).status_code == 200
    assert (await other.get(BASE)).json()["available"] is False
    assert (await other.put(f"{BASE}/nhip_habit_for_may", json=body(), headers=key())).status_code == 503


async def test_guest_cannot_read_or_enable(clients):
    from tests.guest_helpers import add_guest

    app, _ = clients
    on(app, guest_auth_enabled=True)
    guest = await add_guest(app)
    assert (await guest.client.get(BASE)).status_code == 403
    assert (await guest.client.put(f"{BASE}/nhip_habit_for_may", json=body(), headers=key())).status_code == 403


async def test_under_18_account_cannot_enable(clients):
    app, _ = clients
    on(app)
    teen, _uid = await add_actor(app, 7, age_band="teen")
    view = (await teen.get(BASE)).json()
    assert view["available"] is False and edge(view, "nhip_habit_for_may")["reason"] == "ineligible_account"
    refused = await teen.put(f"{BASE}/nhip_habit_for_may", json=body(), headers=key())
    assert refused.status_code == 403 and refused.json()["error"]["code"] == "ADULT_REQUIRED"


@pytest.mark.postgres
async def test_disabling_bumps_data_version_and_cancels_running_turns(clients):
    from app.infrastructure.database.models import AiRun, User
    from tests.fakes import ScriptedModel, message_output
    from tests.test_chat_persistence import enable
    from tests.test_multi_message_persistence import conversation

    app, [(client, uid), _] = clients
    await enable(client)
    on(app)
    assert (await client.put(f"{BASE}/nhip_habit_for_may", json=body(True, 0), headers=key())).status_code == 200
    async with app.state.database.sessions() as db:
        before = (await db.get(User, uid)).data_version
    model = ScriptedModel([[message_output('{"messages":[{"text":"ok","cards":[]}]}')]], hold=True)
    app.state.ai.model_override = model
    url = await conversation(client, "may")
    view = (await client.get(url)).json()
    accepted = await client.post(url + "/messages", headers=key(), json={
        "text": "Chào", "clientMessageId": str(uuid4()), "expectedConversationVersion": view["version"]})
    assert accepted.status_code == 202, accepted.text
    run = app.state.ai.runs[UUID(accepted.json()["runId"])]
    await asyncio.wait_for(model.started.wait(), 5)
    off = await client.put(f"{BASE}/nhip_habit_for_may", json=body(False, 1), headers=key())
    assert off.status_code == 200
    await asyncio.wait_for(asyncio.gather(run.task, return_exceptions=True), 10)
    assert run.terminal_status == "cancelled"
    async with app.state.database.sessions() as db:
        assert (await db.get(User, uid)).data_version == before + 1
        assert (await db.get(AiRun, run.id)).status == "cancelled"


async def test_enabling_does_not_touch_data_version(clients):
    from app.infrastructure.database.models import User

    app, [(client, uid), _] = clients
    on(app)
    async with app.state.database.sessions() as db:
        before = (await db.get(User, uid)).data_version
    assert (await client.put(f"{BASE}/rure_activity_for_guong", json=body(), headers=key())).status_code == 200
    async with app.state.database.sessions() as db:
        assert (await db.get(User, uid)).data_version == before
