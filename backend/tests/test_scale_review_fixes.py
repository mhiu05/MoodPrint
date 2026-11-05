import asyncio
from types import SimpleNamespace
from uuid import uuid4

import pytest
from app.ai.accounting import budget_liability, reserve_accounting
from app.ai.dispatch import ProviderDispatchGate
from app.ai.provider import SdkProvider
from app.ai.schemas import AiOutput
from app.ai.search.service import WebSearchService
from app.core.config import Settings
from app.core.errors import DomainError
from app.infrastructure.database.models import AiUsage, User, now
from app.modules.users.lifecycle import process_deletions
from app.modules.users.models import DataJob
from sqlalchemy import text

from tests.fakes import make_test_model
from tests.test_budget_reservations import make_run


async def test_candidate_search_rejects_before_bypassing_the_model_dispatch_gate():
    settings = Settings(_env_file=None, ai_dispatch_gate_enabled=True)
    service = WebSearchService(SimpleNamespace(settings=settings))
    with pytest.raises(DomainError) as caught:
        await service.search("synthetic public query", None)
    assert caught.value.code == "AI_DISPATCH_UNSUPPORTED"


@pytest.mark.parametrize("operation", ["proactive", "journal"])
async def test_queued_call_rechecks_its_operation_fence_before_private_payload_dispatch(operation):
    provider = SdkProvider(Settings(_env_file=None, ai_dispatch_gate_enabled=True,
                                    ai_timeout_seconds=60))
    provider.dispatch_gate = ProviderDispatchGate(capacity=1, max_queue=2, background_capacity=1)
    model = make_test_model("Synthetic response")
    valid = True
    checks = []
    observations = []

    async def check():
        checks.append(valid)
        if not valid:
            raise DomainError(410, "WORKER_FENCED", "Synthetic authority changed")

    async def observe(event):
        observations.append(event.kind)
        # This is where journal _current(job,entry,consent,lease) is actually checked.
        if operation == "journal" and event.kind == "request_started" and not valid:
            raise DomainError(410, "JOURNAL_MEMORY_CHANGED", "Synthetic journal changed")

    async with provider.dispatch_gate.acquire(wait_seconds=2):
        if operation == "proactive":
            task = asyncio.create_task(provider.run_proactive(bot_id="may", slot="morning",
                input_item={"role": "user", "content": "PRIVATE-CANARY"}, output_type=AiOutput,
                teen=False, on_progress=check, model_override=model, usage_observer=observe))
        else:
            task = asyncio.create_task(provider.run_journal_memories("PRIVATE-JOURNAL-CANARY",
                usage_observer=observe, model_override=model))
        for _ in range(100):
            if provider.dispatch_gate.waiting:
                break
            await asyncio.sleep(0.01)
        assert provider.dispatch_gate.waiting == 1
        assert model.calls == []
        valid = False
    with pytest.raises(DomainError):
        await task
    assert model.calls == []
    assert provider.dispatch_gate.active == provider.dispatch_gate.waiting == 0
    await provider.aclose()


@pytest.mark.postgres
@pytest.mark.parametrize("state", ["uncertain", "settled"])
async def test_account_deletion_with_budget_off_retains_relevant_legacy_history(clients, state):
    app, actors = clients
    uid = actors[0][1]
    app.state.settings.ai_daily_budget_usd = 0
    async with app.state.database.sessions.begin() as db:
        run = await make_run(db, uid)
        await reserve_accounting(db, run.id, uid, uuid4(), "gpt-6-luna", "legacy")
        row = await db.get(AiUsage, run.id)
        row.state, row.requests_started, row.responses_received = state, 1, int(state == "settled")
        row.estimated_nano_usd = None if state == "uncertain" else 1000
        row.input_tokens = 100 if state == "settled" else 0
        run_id = run.id
        db.add(DataJob(user_id=uid, kind="deletion", scope="account", status="queued"))
        await db.execute(text("insert into auth.users(id) values (:id) on conflict (id) do nothing"), {"id": uid})
    await process_deletions(app)
    async with app.state.database.sessions() as db:
        assert (await db.get(User, uid)).status == "deleted"
        assert await db.get(AiUsage, run_id) is not None
        if state == "uncertain":
            with pytest.raises(DomainError):
                await budget_liability(db, now())
        else:
            assert await budget_liability(db, now()) >= 55_000
