"""Capture real runtime emissions, including structured arguments/extra fields."""

import asyncio
import json
import logging
import time
from uuid import UUID

import pytest

from tests.fakes import ScriptedModel, message_output
from tests.guest_helpers import add_guest
from tests.test_guest_inflight import start_guest_run

pytestmark = pytest.mark.postgres
PRIVATE = "PRIVATE-GUEST-LOG-SENTINEL"


@pytest.mark.parametrize('outcome', ['success', 'failure', 'cancellation', 'expiry'])
async def test_guest_run_logs_exclude_activity_identifiers(clients, caplog, outcome):
    from app.modules.guests.deadlines import GuestDeadline

    app, _ = clients
    guest = await add_guest(app)
    model = ScriptedModel([[message_output(json.dumps({'text': PRIVATE, 'cards': []}))]], hold=True)
    if outcome == 'failure':
        async def failure(*args, **kwargs):
            model.started.set()
            raise RuntimeError(PRIVATE)
            yield  # Make the failing provider method an async generator.
        model.stream_response = failure
    caplog.set_level(logging.INFO, logger='moodprint')
    conversation, accepted = await start_guest_run(app, guest, model)
    run_id = UUID(accepted['runId'])
    run = app.state.ai.runs[run_id]
    await asyncio.wait_for(model.started.wait(), 5)
    if outcome == 'cancellation':
        app.state.ai.request_cancel(run)
    elif outcome == 'expiry':
        run.deadline = GuestDeadline(guest.expires_at, 0, time.monotonic())
        model.release.set()
    else:
        model.release.set()
    await asyncio.wait_for(asyncio.shield(run.task), 5)
    if run.finalization_task:
        await run.finalization_task
    records = [record for record in caplog.records if record.name.startswith('moodprint')]
    assert any('ai_execution_end' in record.getMessage() for record in records)
    assert any('metric=ai_run_ended' in record.getMessage() for record in records)
    forbidden = [guest.user_id, guest.session_id, guest.provider_session_id, run_id,
        conversation['conversationId'], PRIVATE, 'PRIVATE-INPUT-CANARY']
    serialized = '\n'.join(record.getMessage() + repr(record.__dict__) for record in records)
    for value in forbidden:
        assert str(value) not in serialized, f'guest identifier/payload in log: {value}'
    assert 'duration_ms=' in serialized and 'model_requests=' in serialized
    assert 'input_tokens=' in serialized and 'output_tokens=' in serialized


async def test_registered_run_logging_preserves_observability(clients, caplog):
    from tests.test_ai_recovery import seed_unstarted_run

    caplog.set_level(logging.INFO, logger='moodprint')
    runtime, run, _, model = await seed_unstarted_run(clients)
    model.release.set()
    await asyncio.wait_for(asyncio.shield(run.task), 5)
    serialized = '\n'.join(record.getMessage() + repr(record.__dict__)
        for record in caplog.records if record.name.startswith('moodprint'))
    assert str(run.id) in serialized
    assert 'ai_execution_end' in serialized and 'duration_ms=' in serialized
