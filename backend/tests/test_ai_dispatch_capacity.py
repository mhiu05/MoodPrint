import asyncio

import pytest
from app.core.errors import DomainError


async def test_dispatch_queue_is_finite_cancel_safe_and_leak_free():
    from app.ai.dispatch import ProviderDispatchGate

    gate = ProviderDispatchGate(capacity=2, max_queue=1, background_capacity=1)
    entered = asyncio.Event()
    release = asyncio.Event()

    async def work():
        async with gate.acquire(wait_seconds=2):
            entered.set()
            await release.wait()

    tasks = [asyncio.create_task(work()) for _ in range(2)]
    await entered.wait()
    await asyncio.sleep(0)
    queued = asyncio.create_task(work())
    await asyncio.sleep(0)
    with pytest.raises(DomainError) as caught:
        async with gate.acquire(wait_seconds=1):
            pytest.fail("Queue overflow must not dispatch")
    assert caught.value.code == "AI_OVERLOADED"
    queued.cancel()
    await asyncio.gather(queued, return_exceptions=True)
    release.set()
    await asyncio.gather(*tasks)
    assert gate.active == 0 and gate.waiting == 0 and gate.peak == 2


async def test_fifty_parent_jobs_with_children_respect_physical_dispatch_cap():
    from app.ai.dispatch import ProviderDispatchGate

    gate = ProviderDispatchGate(capacity=8, max_queue=150, background_capacity=2)

    async def call(background=False):
        async with gate.acquire(wait_seconds=5, background=background):
            await asyncio.sleep(0.001)

    async def parent():
        await call()
        await asyncio.gather(call(), call())

    await asyncio.gather(*[parent() for _ in range(50)], *[call(True) for _ in range(10)])
    assert gate.peak <= 8 and gate.active == 0 and gate.waiting == 0
    assert gate.calls == 160


async def test_dispatch_wait_deadline_and_background_share():
    from app.ai.dispatch import ProviderDispatchGate

    gate = ProviderDispatchGate(capacity=2, max_queue=4, background_capacity=1)
    async with gate.acquire(wait_seconds=1, background=True):
        with pytest.raises(DomainError):
            async with gate.acquire(wait_seconds=0.01, background=True):
                pytest.fail("Background lane exceeded its share")
        async with gate.acquire(wait_seconds=0.1):
            assert gate.active == 2
    assert gate.active == gate.waiting == 0


@pytest.mark.postgres
async def test_candidate_parent_admission_does_not_count_specialist_rows_as_parents(clients):
    from app.ai.persistence import admission
    from app.infrastructure.database.models import User

    from tests.test_budget_reservations import make_run

    app, actors = clients
    settings = app.state.settings
    settings.ai_dispatch_gate_enabled = True
    settings.ai_global_concurrency = 2
    async with app.state.database.sessions.begin() as db:
        parent = await make_run(db, actors[0][1])
        parent.status = "running"
        child = await make_run(db, actors[0][1], origin="agent", parent=parent.id)
        child.status = "running"
    async with app.state.database.sessions.begin() as db:
        user = await db.get(User, actors[1][1])
        await admission(db, user, settings)
