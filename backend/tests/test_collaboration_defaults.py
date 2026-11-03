"""Defaults overlay and rollback proofs, using only synthetic accounts/models."""

from pathlib import Path

import pytest
from sqlalchemy import select

from app.ai.collaboration.models import LEGACY_EDGES, V3_EDGES, AiSharingPermission
from app.infrastructure.database.models import User
from tests.collaboration_helpers import setup
from tests.test_sharing_api import BASE, body, key

pytestmark = pytest.mark.postgres
MIGRATION_PATH = Path(__file__).resolve().parents[1] / "alembic/versions/0028_collaboration_defaults.py"


@pytest.mark.parametrize("family", ["legacy", "v3"])
@pytest.mark.parametrize("stored", [None, False, True])
async def test_defaults_overlay_preserves_old_rows_and_rolls_back(clients, family, stored):
    from app.ai.collaboration.grants import GrantToken, effective_grants

    app, [(client, uid), _] = clients
    await setup(app, client, edges=(), journal=False)
    settings = app.state.settings
    settings.ai_enabled = True
    settings.ai_collaboration_defaults_enabled = True
    settings.ai_three_agent_experience_enabled = family == "v3"
    settings.ai_smart_orchestration_enabled = family == "v3"
    names = V3_EDGES if family == "v3" else LEGACY_EDGES
    async with app.state.database.sessions.begin() as db:
        if stored is not None:
            db.add_all(AiSharingPermission(user_id=uid, edge=name, enabled=stored, version=2) for name in names)
    async with app.state.database.sessions() as db:
        user = await db.get(User, uid)
        grants = await effective_grants(db, settings, user, family=family)
        assert grants.edges == dict.fromkeys(names, GrantToken("collaboration-defaults-v1", 2))
        assert not grants.journal_context
        settings.ai_collaboration_defaults_enabled = False
        legacy = await effective_grants(db, settings, user, family=family)
        assert legacy.edges == (dict.fromkeys(names, GrantToken("sharing-v1", 2)) if stored else {})
        rows = (await db.scalars(select(AiSharingPermission).where(AiSharingPermission.user_id == uid))).all()
        assert [(r.enabled, r.version) for r in rows] == ([(stored, 2)] * len(names) if stored is not None else [])


async def test_effective_read_and_retired_write_never_change_hidden_preference(clients):
    app, [(client, uid), _] = clients
    await setup(app, client, edges=(), journal=False)
    app.state.settings.ai_enabled = True
    app.state.settings.ai_collaboration_defaults_enabled = True
    view = (await client.get(BASE)).json()
    assert view["policyMode"] == "collaboration-defaults-v1" and view["policyEpoch"] == 2
    assert all(e["enabled"] for e in view["edges"])
    assert next(e for e in view["edges"] if e["edge"] == LEGACY_EDGES[0])["reason"] == "journal_context_off"
    response = await client.put(f"{BASE}/{LEGACY_EDGES[1]}", json=body(False, 2), headers=key())
    assert response.status_code == 410 and response.json()["error"]["code"] == "SHARING_SETTINGS_RETIRED"
    async with app.state.database.sessions() as db:
        assert (await db.scalars(select(AiSharingPermission))).all() == []


@pytest.mark.parametrize("family", ["legacy", "v3"])
@pytest.mark.parametrize("gate", ["guest", "under18", "unknown_age", "no_declaration", "suspended", "deleting",
                                  "inactive", "ai_off", "consent_missing", "history_off", "cohort_off", "feature_off"])
async def test_defaults_do_not_bypass_existing_gates(clients, family, gate):
    from datetime import timedelta
    from uuid import uuid4

    from app.ai.collaboration.grants import effective_grants
    from app.infrastructure.database.models import AgeDeclaration, Consent, now

    app, [(client, uid), _] = clients
    await setup(app, client, edges=(), journal=False)
    settings = app.state.settings
    settings.ai_enabled = settings.ai_collaboration_defaults_enabled = True
    settings.ai_three_agent_experience_enabled = settings.ai_smart_orchestration_enabled = family == "v3"
    async with app.state.database.sessions() as db:
        user = await db.get(User, uid)
        if gate == "guest":
            # The lifecycle column is immutable in storage; exercise the resolver without flushing.
            user.account_kind = "guest"
        elif gate in ("under18", "unknown_age"):
            user.age_band = "teen" if gate == "under18" else "unknown"
        elif gate == "no_declaration":
            await db.delete(await db.get(AgeDeclaration, uid))
            await db.flush()
        elif gate == "suspended":
            user.suspended_until = now() + timedelta(hours=1)
        elif gate == "deleting":
            user.deletion_pending = True
        elif gate == "inactive":
            user.status = "deleted"
        elif gate == "consent_missing":
            await db.delete(await db.get(Consent, (uid, "AI")))
            await db.flush()
        elif gate == "ai_off":
            settings.ai_enabled = False
        elif gate == "history_off":
            settings.chat_history_enabled = False
        elif gate == "feature_off":
            settings.ai_collaboration_enabled = settings.ai_smart_orchestration_enabled = False
        elif family == "v3":
            settings.ai_v3_rollout_user_ids = [uuid4()]
        else:
            settings.ai_collaboration_rollout_user_ids = [uuid4()]
        with db.no_autoflush:
            grants = await effective_grants(db, settings, user, family=family)
        assert grants.edges == {}


@pytest.mark.parametrize("scenario", ["r1", "r3", "r4", "journal_off", "refusal", "injection", "r2", "source_edit",
                                      "consult_both", "handoff", "taint", "handoff_scope"])
async def test_defaults_runtime_keeps_existing_privacy_proofs_without_put_sharing(clients, monkeypatch, scenario):
    """Reuse the full existing SDK projection/usage assertions with defaults-only setup."""
    from tests import test_collaboration_chat as chat
    from tests import test_collaboration_privacy as privacy
    from tests import test_collaboration_proactive as proactive
    from tests import test_collaboration_review_fixes as review
    from tests import test_orchestration_sdk as sdk
    from tests import test_v3_review_fixes as v3review
    from tests.orchestration_helpers import v3_setup
    from tests.test_chat_persistence import enable

    app, actors = clients
    async def defaults_setup(app, client, **kwargs):
        await setup(app, client, **{**kwargs, "edges": ()})
        app.state.settings.ai_enabled = app.state.settings.ai_collaboration_defaults_enabled = True
    async def defaults_v3_setup(app, client, **kwargs):
        await v3_setup(app, client, **{**kwargs, "edges": ()})
        app.state.settings.ai_enabled = app.state.settings.ai_collaboration_defaults_enabled = True
    async def defaults_proactive(app, uid, **kwargs):
        await proactive_original(app, uid, edge=False)
        client = next(client for client, actor_id in actors if actor_id == uid)
        await enable(client)
        app.state.settings.ai_enabled = app.state.settings.ai_collaboration_defaults_enabled = True
    proactive_original = proactive.opt_in
    for module in (chat, privacy, review):
        monkeypatch.setattr(module, "setup", defaults_setup)
    for module in (sdk, v3review):
        monkeypatch.setattr(module, "v3_setup", defaults_v3_setup)
    monkeypatch.setattr(proactive, "opt_in", defaults_proactive)
    cases = {
        "r1": chat.test_r1_rure_gets_only_the_energy_enum_never_the_journal,
        "r3": chat.test_r3_may_receives_a_labelled_suggestion_and_never_sends_user_words,
        "r4": chat.test_r4_guong_gets_an_activity_from_rure,
        "journal_off": chat.test_r1_with_journal_context_off_records_consent_denial,
        "refusal": review.test_r1_respects_a_refusal_to_read_the_journal_in_the_same_message,
        "injection": privacy.test_journal_injection_cannot_cross_to_the_requester,
        "r2": proactive.test_r2_morning_check_in_uses_only_the_energy_hint,
        "source_edit": proactive.test_entry_edited_before_publish_regenerates_from_fresh_data,
        "consult_both": sdk.test_consult_both_specialists_through_real_as_tool,
        "handoff": sdk.test_handoff_rebuilds_the_input_and_the_specialist_answers,
        "taint": v3review.test_h1_hoatdong_is_never_asked_after_nhatky_returned,
        "handoff_scope": v3review.test_h1_handoff_carries_no_free_text_and_journal_tool_needs_the_plan,
    }
    await cases[scenario](clients)
    async with app.state.database.sessions() as db:
        assert (await db.scalars(select(AiSharingPermission))).all() == []


@pytest.mark.parametrize("family", ["legacy", "v3"])
@pytest.mark.parametrize("change", ["epoch", "rollback", "feature"])
async def test_inflight_child_rejects_policy_or_epoch_change_before_publish(clients, family, change, caplog):
    import asyncio

    from tests.collaboration_helpers import (
        HABIT,
        finish,
        primary,
        receipts,
        specialist_model,
        start,
    )
    from tests.orchestration_helpers import (
        ACTIVITIES,
        call,
        plan,
        reply,
        roles,
        scripted,
        steps,
        v3_setup,
    )
    from tests.test_multi_message_persistence import conversation

    caplog.set_level("INFO", logger="moodprint")
    app, [(client, uid), _] = clients
    if family == "v3":
        await v3_setup(app, client, edges=(), journal=False)
        child = scripted(ACTIVITIES)
        child.hold = True
        roles(app, planner=scripted(plan(specialists=["hoatdong"])),
              dieuphoi=scripted([call("consult_hoatdong", {"task": "suggest_activities", "goal": "nghỉ nhẹ",
                  "time_budget_minutes": 30, "energy": "low", "count": 1})], reply("Thử nghỉ một chút nhé.")),
              hoatdong_consult=child)
        bot, prompt = "dieuphoi", "Lên vài hoạt động nhẹ nhàng cho cuối tuần"
    else:
        await setup(app, client, edges=(), journal=False)
        child = specialist_model(HABIT, hold=True)
        app.state.ai.specialist_model_override = child
        app.state.ai.model_override = primary("Thử nghỉ nhẹ nhé.")
        bot, prompt = "may", "Mình mất ngủ"
    settings = app.state.settings
    settings.ai_enabled = settings.ai_collaboration_defaults_enabled = True
    # Equal integers across old and new policies must not make rollback authorize stale output.
    names = V3_EDGES if family == "v3" else LEGACY_EDGES
    async with app.state.database.sessions.begin() as db:
        db.add_all(AiSharingPermission(user_id=uid, edge=name, enabled=True, version=2) for name in names)
    url = await conversation(client, bot)
    run = await start(app, client, url, prompt)
    await asyncio.wait_for(child.started.wait(), 10)
    if change == "epoch":
        settings.ai_collaboration_policy_epoch += 1
    elif change == "rollback":
        settings.ai_collaboration_defaults_enabled = False
    else:
        settings.ai_collaboration_enabled = settings.ai_smart_orchestration_enabled = False
    child.release.set()
    await finish(run)
    assert run.terminal_status == "failed", run.failure
    rows = await steps(app, run.id) if family == "v3" else await receipts(app, run.id)
    assert rows and all(not r.used_in_reply for r in rows)
    assert all(r.permission_policy == "collaboration-defaults-v1" for r in rows if getattr(r, "edge", None))
    view = (await client.get(url)).json()
    assert not any(m["actor"] == "bot" for m in view["messages"])
    if change != "feature":
        assert any(f"metric=collaboration_token_mismatch family={family}" in r.message for r in caplog.records)


async def test_continuation_revalidates_original_handoff_epoch_before_publish(clients):
    import asyncio

    from tests.collaboration_helpers import finish, start
    from tests.orchestration_helpers import call, plan, reply, roles, scripted, v3_setup
    from tests.test_multi_message_persistence import conversation

    app, [(client, uid), _] = clients
    await v3_setup(app, client, edges=(), journal=False)
    settings = app.state.settings
    settings.ai_enabled = settings.ai_collaboration_defaults_enabled = True
    roles(app, planner=scripted(plan(workflow="handoff", intent="talk_to_specialist", specialists=[],
                                    handoff_target="hoatdong", data_categories=["latest_message"])),
          dieuphoi=scripted([call("transfer_to_hoatdong", {"reason": "activity_planning"})]),
          hoatdong=scripted(reply("Cùng nghĩ một hoạt động nhé.")))
    url = await conversation(client, "dieuphoi")
    first = await finish(await start(app, client, url, "Cho mình nói chuyện trực tiếp với Hoạt động"))
    assert first.terminal_status == "completed", first.failure
    assert (await client.get(url)).json()["activeAgent"] == "hoatdong"
    child = scripted(reply("Thử đi dạo nhé."))
    child.hold = True
    app.state.ai.model_override = child
    roles(app, hoatdong=child)
    follow = await start(app, client, url, "Có hoạt động nào nữa không?")
    await asyncio.wait_for(child.started.wait(), 10)
    settings.ai_collaboration_policy_epoch += 1
    child.release.set()
    await finish(follow)
    assert follow.terminal_status == "failed", follow.failure
    view = (await client.get(url)).json()
    assert len([m for m in view["messages"] if m["actor"] == "bot"]) == 1


async def test_receipt_policy_migration_is_additive_and_reversible(clients):
    import importlib.util

    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    from sqlalchemy import text

    from app.ai.orchestration.models import AiOrchestrationStep
    from app.infrastructure.database.models import Base, now
    from tests.test_collaboration_migration import _seed

    app, [(_, uid), _] = clients
    receipt_id = await _seed(app, uid)
    async with app.state.database.sessions.begin() as db:
        from app.ai.collaboration.models import AiCollaboration
        receipt = await db.get(AiCollaboration, receipt_id)
        db.add(AiOrchestrationStep(user_id=uid, workflow_run_id=receipt.primary_run_id,
            kind="consult", requester_bot="dieuphoi", target_bot="hoatdong",
            edge="dieuphoi_consult_hoatdong", ordinal=0, status="denied", deny_reason="edge_disabled",
            permission_version=0, data_version=1, detail={}, finished_at=now()))
    spec = importlib.util.spec_from_file_location("defaults_migration", MIGRATION_PATH)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    assert migration.down_revision == "0027_maps_jobs"
    def migrate(connection, action):
        with Operations.context(MigrationContext.configure(connection, opts={"target_metadata": Base.metadata})):
            getattr(migration, action)()
    async with app.state.database.engine.begin() as connection:
        snapshot_sql = text("select to_jsonb(p) from moodprint.ai_sharing_permissions p where user_id = :uid")
        snapshot = (await connection.execute(snapshot_sql, {"uid": uid})).scalars().all()
        await connection.run_sync(lambda c: migrate(c, "downgrade"))
        await connection.run_sync(lambda c: migrate(c, "upgrade"))
        savepoint = await connection.begin_nested()
        for table in ("ai_collaborations", "ai_orchestration_steps"):
            values = (await connection.execute(text(f"select permission_policy from moodprint.{table}"))).scalars().all()
            assert values == ["sharing-v1"]
            # New receipts can opt into the new token while old receipts default to legacy.
            await connection.execute(text(f"update moodprint.{table} set permission_policy = :policy"),
                                     {"policy": "collaboration-defaults-v1"})
        assert (await connection.execute(snapshot_sql, {"uid": uid})).scalars().all() == snapshot
        with pytest.raises(RuntimeError, match="non-legacy receipts"):
            await connection.run_sync(lambda c: migrate(c, "downgrade"))
        await savepoint.rollback()
        await connection.run_sync(lambda c: migrate(c, "downgrade"))
        await connection.run_sync(lambda c: migrate(c, "upgrade"))
        assert (await connection.execute(snapshot_sql, {"uid": uid})).scalars().all() == snapshot


async def test_denied_v3_journal_step_keeps_defaults_token_without_reading_private_data(clients):
    from tests.collaboration_helpers import finish, start
    from tests.orchestration_helpers import plan, reply, roles, scripted, steps, v3_setup
    from tests.test_multi_message_persistence import conversation

    app, [(client, _), _] = clients
    await v3_setup(app, client, edges=(), journal=False)
    app.state.settings.ai_enabled = app.state.settings.ai_collaboration_defaults_enabled = True
    roles(app, planner=scripted(plan(specialists=["nhatky"])), dieuphoi=scripted(reply("Mình ở đây với bạn.")))
    url = await conversation(client, "dieuphoi")
    run = await finish(await start(app, client, url, "Giúp mình xem lại những điều mình đã ghi tuần rồi"))
    assert run.terminal_status == "completed", run.failure
    denied = [s for s in await steps(app, run.id) if s.kind == "consult"]
    assert len(denied) == 1
    assert (denied[0].status, denied[0].deny_reason, denied[0].permission_policy, denied[0].permission_version) == (
        "denied", "journal_consent_off", "collaboration-defaults-v1", 2)
    assert denied[0].child_run_id is None and not denied[0].used_in_reply


@pytest.mark.parametrize("family", ["legacy", "v3"])
async def test_off_on_off_epoch_rollback_never_reuses_a_different_policy_token(clients, family):
    from uuid import uuid4

    from app.ai.collaboration.coordinator import Consultation, still_authorized
    from app.ai.orchestration.workflow import Step, Workflow, live_grants
    from tests.orchestration_helpers import v3_setup

    app, [(client, uid), _] = clients
    if family == "v3":
        await v3_setup(app, client, edges=(), journal=False)
        edge = "dieuphoi_consult_hoatdong"
        def receipt(policy):
            return Step(uuid4(), "consult", "hoatdong", edge, 0, uuid4(), 2, permission_policy=policy)
        async def holds(db, user, item):
            return Workflow._grant_holds(None, await live_grants(db, app.state.settings, user), item)
    else:
        await setup(app, client, edges=(), journal=False)
        edge = "nhip_habit_for_may"
        def receipt(policy):
            return Consultation(uuid4(), uuid4(), edge, "R3", 2, 1, permission_policy=policy)
        async def holds(db, user, item):
            return await still_authorized(db, app.state.settings, user, item)
    settings = app.state.settings
    settings.ai_enabled = True
    async with app.state.database.sessions.begin() as db:
        db.add(AiSharingPermission(user_id=uid, edge=edge, enabled=True, version=2))
    old, defaults = receipt("sharing-v1"), receipt("collaboration-defaults-v1")
    async with app.state.database.sessions() as db:
        user = await db.get(User, uid)
        if family == "legacy":
            old.data_version = defaults.data_version = user.data_version
        assert await holds(db, user, old)
        settings.ai_collaboration_defaults_enabled = True
        assert not await holds(db, user, old)
        assert await holds(db, user, defaults)
        settings.ai_collaboration_policy_epoch += 1
        assert not await holds(db, user, defaults)
        settings.ai_collaboration_defaults_enabled = False
        assert not await holds(db, user, defaults)
        assert await holds(db, user, old)


async def test_preflight_reports_only_aggregate_old_values_without_writing(clients):
    from app.ai.collaboration.preflight import sharing_preflight_counts

    app, [(_, uid), _] = clients
    async with app.state.database.sessions.begin() as db:
        db.add_all([AiSharingPermission(user_id=uid, edge=LEGACY_EDGES[0], enabled=True),
                    AiSharingPermission(user_id=uid, edge=LEGACY_EDGES[1], enabled=False)])
    async with app.state.database.sessions() as db:
        assert await sharing_preflight_counts(db) == {
            "legacy": {"true": 1, "false": 1, "missing": 4},
            "v3": {"true": 0, "false": 0, "missing": 8},
        }
        assert not db.new and not db.dirty and not db.deleted


async def test_overlay_never_mutates_group_journal_history_or_personal_preferences(clients):
    from app.ai.collaboration.grants import effective_grants
    from app.ai.models import AiPreference
    from app.ai.orchestration.models import AiGroupMember
    from app.ai.proactive.models import AiProactiveSettings
    from tests.group_helpers import create_group, groups_setup

    app, [(client, uid), _] = clients
    await groups_setup(app, client, journal=False)
    await create_group(client)
    settings = app.state.settings
    settings.ai_enabled = settings.ai_collaboration_defaults_enabled = True
    async with app.state.database.sessions() as db:
        user = await db.get(User, uid)
        prefs = await db.get(AiPreference, uid)
        before = (prefs.history_enabled, prefs.semantic_memory_enabled, prefs.version)
        members = (await db.scalars(select(AiGroupMember))).all()
        snapshot = [(r.bot_id, r.journal_access, r.history_from_sequence, r.version) for r in members]
        for family in ("legacy", "v3"):
            await effective_grants(db, settings, user, family=family)
        assert [(r.bot_id, r.journal_access, r.history_from_sequence, r.version) for r in members] == snapshot
        assert all(not r.journal_access for r in members)
        assert (prefs.history_enabled, prefs.semantic_memory_enabled, prefs.version) == before
        journal = await db.get(AiProactiveSettings, uid)
        assert journal is None or not journal.journal_context_enabled
        assert not db.new and not db.dirty and not db.deleted
