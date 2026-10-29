"""Every paid guest dispatch needs an approved budget, a quota claim, a reservation and a live trial."""

import asyncio
import io
import json
import wave
from datetime import timedelta
from uuid import uuid4

import pytest
from sqlalchemy import func, select, update

from tests.guest_helpers import add_guest, db_now, enable_paid_fixture

pytestmark = pytest.mark.postgres
LIFETIME = timedelta(seconds=7200)
UPPER_AI = 3 * (100 * 2 + 1200 * 5)  # synthetic fixture bound from PAID_PRICING


def wav(seconds=0.2, rate=8000) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(rate)
        audio.writeframes(b"\x00\x00" * int(rate * seconds))
    return buffer.getvalue()


async def ledger(app):
    from app.modules.guests.models import GuestBudgetDay, GuestCostReservation, GuestOperationLink

    async with app.state.database.sessions() as db:
        return (
            (await db.scalars(select(GuestBudgetDay))).all(),
            (await db.scalars(select(GuestCostReservation))).all(),
            await db.scalar(select(func.count()).select_from(GuestOperationLink)),
        )


async def open_chat(app, guest, model):
    from tests.fakes import make_test_model  # noqa: F401

    app.state.ai.model_override = model
    ai = await guest.client.put(
        "/api/v1/consents/AI",
        json={"enabled": True, "expectedVersion": 1, "policyVersion": "v1"},
        headers={"Idempotency-Key": str(uuid4())},
    )
    assert ai.status_code == 200, ai.text
    return await guest.client.post(
        "/api/v1/ai/conversations", json={"botId": "may"}, headers={"Idempotency-Key": str(uuid4())}
    )


async def send(app, guest, conversation, key=None):
    return await guest.client.post(
        f"/api/v1/ai/conversations/{conversation['conversationId']}/messages",
        json={
            "text": "xin chào",
            "clientMessageId": key or str(uuid4()),
            "expectedConversationVersion": conversation["version"],
        },
        headers={"Idempotency-Key": str(uuid4())},
    )


class CountingTranscriber:
    def __init__(self):
        self.calls = 0

    async def transcribe(self, data: bytes) -> str:
        self.calls += 1
        return "bản chữ"


async def test_guest_paid_work_is_closed_by_default(clients):
    from tests.fakes import make_test_model

    app, _ = clients
    model = make_test_model("không bao giờ được gọi")
    guest = await add_guest(app, consents=True)
    app.state.ai.model_override = model
    transcriber = CountingTranscriber()
    app.state.transcriber = transcriber
    # AI consent, VOICE consent and a working test provider are not enough: no approved budget.
    created = await guest.client.post(
        "/api/v1/ai/conversations", json={"botId": "may"}, headers={"Idempotency-Key": str(uuid4())}
    )
    assert created.status_code == 503 and created.json()["error"]["code"] == "GUEST_PAID_UNAVAILABLE"
    voice = await guest.client.post(
        "/api/v1/voice/transcriptions",
        content=wav(),
        headers={"Content-Type": "audio/wav", "Idempotency-Key": str(uuid4())},
    )
    assert voice.status_code == 503 and voice.json()["error"]["code"] == "GUEST_PAID_UNAVAILABLE"
    assert model.calls == [] and transcriber.calls == 0
    days, reservations, links = await ledger(app)
    assert days == [] and reservations == [] and links == 0
    features = (await guest.client.get("/api/v1/session")).json()["features"]
    assert features["ai"] is False and features["voice"] is False
    # Each paid flag combination that lacks any one ingredient stays closed.
    from decimal import Decimal

    for patch in (
        {"guest_paid_enabled": True},  # no budget, no prices
        {"guest_paid_enabled": True, "guest_daily_budget_usd": Decimal("0.01")},  # no prices
    ):
        for name, value in patch.items():
            setattr(app.state.settings, name, value)
        again = await guest.client.post(
            "/api/v1/ai/conversations", json={"botId": "may"}, headers={"Idempotency-Key": str(uuid4())}
        )
        assert again.status_code == 503
    assert model.calls == []


async def test_each_paid_adapter_requires_reservation_and_final_lifetime(clients, monkeypatch):
    from app.modules.guests import accounting
    from tests.fakes import make_test_model

    app, _ = clients
    enable_paid_fixture(app)
    order: list[str] = []
    real_mark = accounting.mark_guest_dispatched

    async def marked(db, reservation_id):
        order.append("marker")
        await real_mark(db, reservation_id)

    monkeypatch.setattr(accounting, "mark_guest_dispatched", marked)
    monkeypatch.setattr("app.modules.voice.routes.mark_guest_dispatched", marked)

    # --- AI: the reservation marker precedes the provider call; the settled ledger follows it.
    model = make_test_model("Đã trả lời.")
    original = model.stream_response

    async def logged(*args, **kwargs):
        order.append("model")
        async for event in original(*args, **kwargs):
            yield event

    model.stream_response = logged
    guest = await add_guest(app, consents=True)
    conversation = (await open_chat(app, guest, model)).json()
    accepted = await send(app, guest, conversation)
    assert accepted.status_code == 202, accepted.text
    await guest.client.get(accepted.json()["eventsUrl"])
    for _ in range(40):
        _, reservations, _ = await ledger(app)
        if reservations and reservations[0].state in ("settled", "uncertain"):
            break
        await asyncio.sleep(0.1)
    assert order[:2] == ["marker", "model"], order
    days, reservations, links = await ledger(app)
    assert reservations[0].upper_nano_usd == UPPER_AI and reservations[0].state == "uncertain"
    assert days[0].spent_nano_usd == UPPER_AI and days[0].reserved_nano_usd == 0, "no usage -> bound charged once"
    assert len(model.calls) == 1

    # --- AI: an exhausted budget or quota refuses before any provider call, consuming nothing.
    tight = await add_guest(app, consents=True)
    tight_model = make_test_model("không gọi")
    conversation = (await open_chat(app, tight, tight_model)).json()
    from decimal import Decimal

    app.state.settings.guest_daily_budget_usd = Decimal("0.00001")  # 10_000 nano < one reservation
    refused = await send(app, tight, conversation)
    assert refused.status_code == 429 and refused.json()["error"]["code"] == "GUEST_BUDGET_EXHAUSTED"
    spent = await add_guest(app, consents=True, usage={"ai_turns": 25})
    app.state.settings.guest_daily_budget_usd = Decimal("0.01")
    spent_chat = (await open_chat(app, spent, tight_model)).json()
    over = await send(app, spent, spent_chat)
    assert over.status_code == 429 and over.json()["error"]["code"] == "GUEST_QUOTA_EXHAUSTED"
    assert tight_model.calls == []
    from app.modules.guests.models import GuestUsage

    async with app.state.database.sessions() as db:
        assert (await db.get(GuestUsage, tight.user_id)).ai_turns == 0, "a refused admission consumes nothing"

    # --- the wrapper never delegates when the guard refuses (final lifetime / marker failure).
    from app.ai.guest_model import GuestGuardedModel

    class Spy:
        calls = 0

        async def stream_response(self, *args, **kwargs):
            Spy.calls += 1
            yield None

    async def deny():
        raise RuntimeError("expired")

    with pytest.raises(RuntimeError):
        async for _ in GuestGuardedModel(Spy(), deny).stream_response():
            pass
    assert Spy.calls == 0

    # --- voice: marker before provider; exhausted budget -> no provider call; replay is refused.
    transcriber = CountingTranscriber()
    app.state.transcriber = transcriber
    speaker = await add_guest(app, consents=True)
    key = str(uuid4())
    headers = {"Content-Type": "audio/wav", "Idempotency-Key": key}
    order.clear()
    ok = await speaker.client.post("/api/v1/voice/transcriptions", content=wav(), headers=headers)
    assert ok.status_code == 200, ok.text
    assert order == ["marker"] and transcriber.calls == 1
    replay = await speaker.client.post("/api/v1/voice/transcriptions", content=wav(), headers=headers)
    assert replay.status_code == 409 and replay.json()["error"]["code"] == "VOICE_ALREADY_PROCESSED"
    assert transcriber.calls == 1, "a processed clip is never redispatched"
    app.state.settings.guest_daily_budget_usd = Decimal("0.00000001")
    blocked = await speaker.client.post(
        "/api/v1/voice/transcriptions",
        content=wav(),
        headers={"Content-Type": "audio/wav", "Idempotency-Key": str(uuid4())},
    )
    assert blocked.status_code == 429 and blocked.json()["error"]["code"] == "GUEST_BUDGET_EXHAUSTED"
    assert transcriber.calls == 1


async def test_embedding_dispatch_needs_flag_price_budget_and_reservation(clients):
    from app.ai.embeddings import process_embedding_jobs
    from tests.test_guest_embeddings import PausedProvider, queue, semantic_guest

    app, _ = clients
    guest, settings, memory_id = await semantic_guest(app, started_ago=timedelta(minutes=1))
    await queue(app, settings, memory_id)
    provider = PausedProvider()
    provider.release.set()
    # Pricing removed: the job is cancelled and the provider is never called.
    settings.guest_pricing_json = {}
    assert await process_embedding_jobs(app.state.database, settings, provider) >= 0
    assert provider.calls == []
    from app.ai.embedding_models import EmbeddingJob

    async with app.state.database.sessions() as db:
        assert (await db.scalar(select(EmbeddingJob))).status == "cancelled"
    days, reservations, _ = await ledger(app)
    assert reservations == []

    # With the approved fixture a fresh job is reserved, dispatched once, settled and never replayed.
    second, settings2, memory2 = await semantic_guest(app, started_ago=timedelta(minutes=1))
    await queue(app, settings2, memory2)
    paid = PausedProvider()
    paid.release.set()
    await process_embedding_jobs(app.state.database, settings2, paid)
    # Every call was funded by its own reservation, dispatched once and settled at the known price.
    days, reservations, _ = await ledger(app)
    assert len(paid.calls) == len(reservations) >= 1
    assert {r.state for r in reservations} == {"settled"}
    assert days[0].spent_nano_usd == 11 * len(reservations) and days[0].reserved_nano_usd == 0


async def test_late_usage_settles_without_recreating_deleted_owner(clients):
    from app.infrastructure.database.models import AiUsage, User
    from app.modules.guests.lifecycle import purge_guest
    from app.modules.guests.models import GuestCleanupJob
    from tests.fakes import ScriptedModel, message_output

    app, _ = clients
    enable_paid_fixture(app)
    model = ScriptedModel([[message_output(json.dumps({"text": "muộn", "cards": []}))]], hold=True)
    guest = await add_guest(app, started_ago=timedelta(minutes=1), consents=True)
    conversation = (await open_chat(app, guest, model)).json()
    assert (await send(app, guest, conversation)).status_code == 202
    await asyncio.wait_for(model.started.wait(), 5)  # the reservation is marked dispatched

    # The trial ends and is purged while the provider call is still in flight.
    token = uuid4()
    async with app.state.database.sessions.begin() as db:
        await db.execute(update(User).where(User.id == guest.user_id).values(status="deleting"))
        await db.execute(
            update(GuestCleanupJob)
            .where(GuestCleanupJob.user_id == guest.user_id)
            .values(state="running", lease_token=token, lease_until=func.clock_timestamp() + timedelta(seconds=30))
        )
    async with app.state.database.sessions.begin() as db:
        assert await purge_guest(db, guest.user_id, token) == "removed"
    days, reservations, links = await ledger(app)
    assert days[0].spent_nano_usd == UPPER_AI and reservations[0].state == "uncertain" and links == 0

    # The late provider answer/observer must create nothing and charge nothing more.
    model.release.set()
    await asyncio.sleep(0.8)
    async with app.state.database.sessions() as db:
        assert await db.get(User, guest.user_id) is None
        assert await db.scalar(select(func.count()).select_from(AiUsage)) == 0
    days, reservations, links = await ledger(app)
    assert days[0].spent_nano_usd == UPPER_AI and days[0].reserved_nano_usd == 0 and links == 0
    assert await db_now(app) is not None
