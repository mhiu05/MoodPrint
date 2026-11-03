"""Detached billing follows durable completion, even if cancellation wins its return."""

import asyncio
from datetime import timedelta
from uuid import uuid4

import pytest
from openai.types.responses.response_usage import ResponseUsage
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSessionTransaction

from app.ai import runtime as runtime_module
from app.ai.accounting import UsageSnapshot, budget_liability
from app.ai.models import AiMessageRecord
from app.ai.runtime import LiveRun
from app.core.security import Actor
from app.infrastructure.database.models import AiRun, AiUsage, Consent, User, now
from app.modules.guests.accounting import mark_guest_dispatched, settle_guest_operation
from app.modules.guests.models import GuestBudgetDay, GuestCostReservation
from tests.fakes import make_test_model
from tests.guest_helpers import add_guest
from tests.test_guest_global_budget import UPPER, capped_settings, reserve
from tests.test_guest_paid_dispatch import open_chat, send

pytestmark = pytest.mark.postgres


@pytest.mark.parametrize(
    ("boundary", "complete_usage", "already_uncertain", "foreign_worker", "expected"),
    [
        ("after_commit", True, False, False, 71_500),
        ("after_commit", False, False, False, UPPER),
        ("after_commit", True, True, False, UPPER),
        ("after_commit", True, False, True, UPPER),
        ("before_commit", True, False, False, UPPER),
    ],
)
async def test_cancellation_at_publication_settles_only_durable_known_usage(
    clients, monkeypatch, boundary, complete_usage, already_uncertain, foreign_worker, expected,
):
    app, _ = clients
    configured = capped_settings()
    for name in ("ai_daily_budget_usd", "ai_accounting_enabled", "openai_model", "guest_paid_enabled",
                 "guest_daily_budget_usd", "guest_pricing_json"):
        setattr(app.state.settings, name, getattr(configured, name))
    guest = await add_guest(app, consents=True)
    model = make_test_model("MUST NOT be published after cancellation")
    original_stream = model.stream_response

    async def priced(*args, **kwargs):
        async for event in original_stream(*args, **kwargs):
            if event.type == "response.completed":
                event.response.usage = ResponseUsage.model_validate({
                    "input_tokens": 100, "input_tokens_details": {"cached_tokens": 0, "cache_write_tokens": 0},
                    "output_tokens": 10, "output_tokens_details": {"reasoning_tokens": 0}, "total_tokens": 110,
                }) if complete_usage else None
            yield event

    model.stream_response = priced
    reached, hold = asyncio.Event(), asyncio.Event()
    armed = False
    original_snapshot = runtime_module.persist_snapshot
    original_exit = AsyncSessionTransaction.__aexit__

    async def snapshot(db, *args, terminal=False, **kwargs):
        nonlocal armed
        result = await original_snapshot(db, *args, terminal=terminal, **kwargs)
        if terminal and not armed:
            armed = True
            if boundary == "before_commit":
                reached.set()
                await hold.wait()  # Cancellation must roll back the publication transaction.
            else:
                db.info["hold_guest_publication_return"] = True
        return result

    async def transaction_exit(transaction, *args):
        result = await original_exit(transaction, *args)
        if transaction.session.info.pop("hold_guest_publication_return", False):
            # The real COMMIT is already visible to another PostgreSQL connection.
            # Hold only its return: drive has not published or changed local status.
            reached.set()
            await hold.wait()
        return result

    monkeypatch.setattr(runtime_module, "persist_snapshot", snapshot)
    monkeypatch.setattr(AsyncSessionTransaction, "__aexit__", transaction_exit)
    created = await open_chat(app, guest, model)
    assert created.status_code == 201, created.text
    accepted = await send(app, guest, created.json())
    assert accepted.status_code == 202, accepted.text
    await asyncio.wait_for(reached.wait(), 5)
    run = next(run for run in app.state.ai.runs.values() if run.actor.user_id == guest.user_id)
    conversation = app.state.ai.store.conversations[run.conversation_id]
    async with app.state.database.sessions() as db:
        durable = await db.get(AiRun, run.id)
        usage = await db.get(AiUsage, run.id)
        assert durable.status == ("completed" if boundary == "after_commit" else "running")
        if boundary == "after_commit":
            assert usage.state == ("settled" if complete_usage else "uncertain")
    if already_uncertain:
        async with app.state.database.sessions.begin() as db:
            await settle_guest_operation(db, run.reservation, None)
    if foreign_worker:
        async with app.state.database.sessions.begin() as db:
            (await db.get(AiUsage, run.id)).worker_id = uuid4()
    # Shutdown, expiry or another cancellation can still arrive after COMMIT,
    # before drive records local completion. The monitor formerly did this too.
    run.task.cancel()
    await asyncio.wait_for(asyncio.shield(run.task), 5)
    assert len(model.calls) == 1
    assert run.final_v2 is None
    assert all(event.type != "final" for event in run.events)
    assert all(message.actor != "bot" for message in conversation.messages)
    async with app.state.database.sessions() as db:
        reservation = await db.get(GuestCostReservation, run.reservation.id)
        day = (await db.scalars(select(GuestBudgetDay))).one()
        assert reservation.state == ("settled" if expected == 71_500 else "uncertain")
        assert reservation.charged_nano_usd == expected
        assert day.spent_nano_usd == expected and day.reserved_nano_usd == 0
        assert await budget_liability(db, now()) == expected
        assert (await db.get(AiRun, run.id)).status == (
            "completed" if boundary == "after_commit" else "cancelled"
        )
    # Retrying cleanup must neither double-charge nor reduce an earlier uncertainty.
    await app.state.ai.settle_guest(run, "cancelled")
    async with app.state.database.sessions() as db:
        assert await budget_liability(db, now()) == expected


@pytest.mark.parametrize("durable_status", ["completed", "failed", "cancelled"])
async def test_guest_settlement_without_usage_metadata_still_requires_durable_completion(
    clients, durable_status,
):
    app, _ = clients
    guest = await add_guest(app)
    settings = app.state.settings
    settings.ai_accounting_enabled = False
    settings.ai_daily_budget_usd = 0
    settings.guest_pricing_json = capped_settings().guest_pricing_json
    reservation = await reserve(app, guest, settings)
    run = LiveRun(
        actor=Actor(guest.user_id, guest.session_id, 1, "guest"),
        conversation_id=uuid4(), data_version=1, id=uuid4(),
        reservation=reservation, dispatched=True,
        usage=UsageSnapshot(requests_started=1, responses_received=1, input_tokens=100, output_tokens=10),
    )
    async with app.state.database.sessions.begin() as db:
        await mark_guest_dispatched(db, reservation.id)
        db.add(AiRun(id=run.id, user_id=guest.user_id, bot_id="may",
                     conversation_id=run.conversation_id, status=durable_status))
    await app.state.ai.settle_guest(run, "cancelled")
    expected = 71_500 if durable_status == "completed" else UPPER
    async with app.state.database.sessions() as db:
        assert await db.get(AiUsage, run.id) is None
        row = await db.get(GuestCostReservation, reservation.id)
        assert row.state == ("settled" if durable_status == "completed" else "uncertain")
        assert row.charged_nano_usd == expected
        assert await budget_liability(db, now()) == expected


@pytest.mark.parametrize("policy", ["allowed", "expired", "revoked", "foreign_worker"])
async def test_policy_monitor_recognizes_committed_completion_without_bypassing_live_guards(
    clients, monkeypatch, policy,
):
    app, _ = clients
    configured = capped_settings()
    for name in ("ai_daily_budget_usd", "ai_accounting_enabled", "openai_model", "guest_paid_enabled",
                 "guest_daily_budget_usd", "guest_pricing_json"):
        setattr(app.state.settings, name, getattr(configured, name))
    guest = await add_guest(
        app, consents=True,
        started_ago=timedelta(seconds=7180) if policy == "expired" else timedelta(minutes=5),
    )
    model = make_test_model("COMMITTED-REPLY-CANARY")
    original_stream = model.stream_response

    async def priced(*args, **kwargs):
        async for event in original_stream(*args, **kwargs):
            if event.type == "response.completed":
                event.response.usage = ResponseUsage.model_validate({
                    "input_tokens": 100, "input_tokens_details": {"cached_tokens": 0, "cache_write_tokens": 0},
                    "output_tokens": 10, "output_tokens_details": {"reasoning_tokens": 0}, "total_tokens": 110,
                })
            yield event

    model.stream_response = priced
    committed, release, checked = asyncio.Event(), asyncio.Event(), asyncio.Event()
    original_snapshot = runtime_module.persist_snapshot
    original_exit = AsyncSessionTransaction.__aexit__
    original_check = app.state.ai.check
    armed = False

    async def snapshot(db, *args, terminal=False, **kwargs):
        nonlocal armed
        result = await original_snapshot(db, *args, terminal=terminal, **kwargs)
        if terminal and not armed:
            armed = True
            db.info["hold_monitor_publication_return"] = True
        return result

    async def transaction_exit(transaction, *args):
        result = await original_exit(transaction, *args)
        if transaction.session.info.pop("hold_monitor_publication_return", False):
            committed.set()
            await release.wait()
        return result

    async def observe_check(*args, **kwargs):
        try:
            return await original_check(*args, **kwargs)
        finally:
            if committed.is_set():
                checked.set()

    monkeypatch.setattr(runtime_module, "persist_snapshot", snapshot)
    monkeypatch.setattr(AsyncSessionTransaction, "__aexit__", transaction_exit)
    monkeypatch.setattr(app.state.ai, "check", observe_check)
    created = await open_chat(app, guest, model)
    assert created.status_code == 201, created.text
    accepted = await send(app, guest, created.json())
    assert accepted.status_code == 202, accepted.text
    await asyncio.wait_for(committed.wait(), 5)
    run = next(run for run in app.state.ai.runs.values() if run.actor.user_id == guest.user_id)
    conversation = app.state.ai.store.conversations[run.conversation_id]
    # First let the real monitor accept our committed completion while the
    # transaction return remains held. It must keep checking subsequent policy.
    await asyncio.wait_for(checked.wait(), 5)
    checked.clear()
    if policy in ("revoked", "foreign_worker"):
        async with app.state.database.sessions.begin() as db:
            if policy == "revoked":
                (await db.get(Consent, (guest.user_id, "AI"))).enabled = False
                (await db.get(User, guest.user_id)).data_version += 1
            else:
                (await db.get(AiUsage, run.id)).worker_id = uuid4()
    if policy == "expired":
        # This is the real original start+7200s bound. Admit with setup headroom,
        # then hold the committed return across T; no clock/grant mutation.
        await asyncio.wait_for(asyncio.shield(run.task), 25)
    elif policy in ("revoked", "foreign_worker"):
        await asyncio.wait_for(checked.wait(), 5)
        # Do not release the publisher until the subsequent policy check cancels
        # it: merely accepting completed once must never end policy monitoring.
        await asyncio.wait_for(asyncio.shield(run.task), 5)
    release.set()
    await asyncio.wait_for(asyncio.shield(run.task), 5)
    if policy == "allowed":
        assert run.final_v2 is not None
        assert any(event.type == "final" for event in run.events)
        assert any(message.actor == "bot" and "COMMITTED-REPLY-CANARY" in message.text
                   for message in conversation.messages)
        response = await guest.client.get(accepted.json()["eventsUrl"])
        assert "event: completed" in response.text and "COMMITTED-REPLY-CANARY" in response.text
    else:
        assert run.final_v2 is None
        assert all(event.type != "final" for event in run.events)
        assert all(message.actor != "bot" for message in conversation.messages)
    assert len(model.calls) == 1
    async with app.state.database.sessions() as db:
        assert (await db.get(AiRun, run.id)).status == "completed"
        assert (await db.scalars(select(AiMessageRecord).where(
            AiMessageRecord.run_id == run.id, AiMessageRecord.actor == "bot",
        ))).one().text == "COMMITTED-REPLY-CANARY"
        reservation = await db.get(GuestCostReservation, run.reservation.id)
        assert reservation.charged_nano_usd == (UPPER if policy == "foreign_worker" else 71_500)
