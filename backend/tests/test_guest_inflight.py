"""Final authorization at every private boundary: transactions, response bytes and dispatch."""

import asyncio
import json
from contextlib import asynccontextmanager
from datetime import date, timedelta
from types import SimpleNamespace

import pytest
from sqlalchemy import func, select, text

from tests.guest_helpers import add_guest, db_now

pytestmark = pytest.mark.postgres
LIFETIME = timedelta(seconds=7200)


@pytest.mark.parametrize("branch", ["existing", "recovery", "new"])
@pytest.mark.parametrize("cross_deadline", [False, True])
async def test_guest_auth_response_queued_past_deadline_is_withheld(clients, branch, cross_deadline):
    import time
    from uuid import uuid4

    from starlette.middleware import Middleware

    from app.modules.guests.output import GuestOutputMiddleware
    from tests.guest_helpers import (
        FakeGuestProvider,
        enable_guest_entry,
        open_intent,
        post_guest,
        public_client,
    )

    app, _ = clients
    enable_guest_entry(app)
    provider = FakeGuestProvider(app)
    browser = public_client(app)
    key = str(uuid4())
    await open_intent(browser)
    original_deadline = None
    if branch != 'new':
        initial = await post_guest(browser, key)
        assert initial.status_code == 201, initial.text
        original_deadline = initial.json()['guestExpiresAt']
        if branch == 'recovery':
            browser.cookies.delete('moodprint_session')
            browser.cookies.delete('moodprint_csrf')
    queued, resume = asyncio.Event(), asyncio.Event()
    offset = 0.0
    captured = {}

    class HoldResponse:
        def __init__(self, app):
            self.app = app

        async def __call__(self, scope, receive, send):
            async def held(message):
                if (scope.get('path') == '/api/v1/auth/guest'
                        and message['type'] == 'http.response.start'):
                    captured['bound'] = scope.get('state', {}).get('guest_output')
                    queued.set()
                    await resume.wait()  # Serialized response/cookies wait inside final guard.
                await send(message)
            await self.app(scope, receive, held)

    index = next(i for i, entry in enumerate(app.user_middleware) if entry.cls is GuestOutputMiddleware)
    app.user_middleware[index] = Middleware(GuestOutputMiddleware, clock=lambda: time.monotonic() + offset)
    app.user_middleware.insert(index + 1, Middleware(HoldResponse))
    app.middleware_stack = None
    pending = asyncio.create_task(post_guest(browser, key))
    try:
        await asyncio.wait_for(queued.wait(), 5)
        # Test-only elapsed monotonic time, with the real immutable DB grant untouched.
        # New grants have7200s; existing/recovery retain the same original T.
        if cross_deadline:
            offset = 7201.0
    finally:
        resume.set()
    response = await asyncio.wait_for(pending, 5)
    if cross_deadline:
        assert response.status_code == 401, response.text
        assert response.json()['error']['code'] == 'GUEST_EXPIRED'
        assert 'userId' not in response.text and 'guestExpiresAt' not in response.text
        assert all('max-age=0' in value.lower() for value in response.headers.get_list('set-cookie'))
    else:
        assert response.status_code == (201 if branch == 'new' else 200), response.text
        assert response.json()['accountKind'] == 'guest'
        if original_deadline:
            assert response.json()['guestExpiresAt'] == original_deadline
    assert captured['bound'] is not None
    assert len(provider.signups) == 1


async def mood_rows(app):
    from app.infrastructure.database.models import Idempotency, Mood

    async with app.state.database.sessions() as db:
        return (
            await db.scalar(select(func.count()).select_from(Mood)),
            await db.scalar(select(func.count()).select_from(Idempotency)),
        )


async def test_waiting_mutation_rolls_back_at_deadline(clients, monkeypatch):
    """The decision to write is taken before T but the transaction only finishes after T."""
    from app.core import security
    from app.modules.mood import routes

    app, _ = clients
    guest = await add_guest(app, started_ago=LIFETIME - timedelta(seconds=3))
    before = await mood_rows(app)
    real = security.transaction
    reached_end = asyncio.Event()
    release = asyncio.Event()

    @asynccontextmanager
    async def slow(request, actor, **kwargs):
        async with real(request, actor, **kwargs) as (db, user):
            yield db, user
            # The body is done (mood and receipt flushed); the commit has not happened yet.
            reached_end.set()
            await release.wait()

    monkeypatch.setattr(routes, "transaction", slow)
    today = date.today().isoformat()
    pending = asyncio.create_task(
        guest.client.put(
            f"/api/v1/moods/{today}",
            json={"value": 4, "expectedVersion": 0, "note": "riêng tư"},
            headers={"Idempotency-Key": "mood-1"},
        )
    )
    await asyncio.wait_for(reached_end.wait(), 5)
    remaining = (guest.expires_at - await db_now(app)).total_seconds()
    await asyncio.sleep(max(0.0, remaining) + 0.3)  # real time crosses T while the write is held
    assert await db_now(app) >= guest.expires_at
    release.set()
    response = await asyncio.wait_for(pending, 5)
    assert response.status_code == 401 and response.json()["error"]["code"] == "GUEST_EXPIRED"
    assert await mood_rows(app) == before, "mutation and receipt roll back together at T"


async def test_predeadline_decision_then_commit_is_unreadable_after(clients):
    """A write fully decided before T is not undone, but nothing can read it once T passes."""
    app, _ = clients
    guest = await add_guest(app, started_ago=LIFETIME - timedelta(seconds=3))
    today = date.today().isoformat()
    saved = await guest.client.put(
        f"/api/v1/moods/{today}",
        json={"value": 3, "expectedVersion": 0},
        headers={"Idempotency-Key": "mood-early"},
    )
    assert saved.status_code in (200, 201), saved.text
    await asyncio.sleep(max(0.0, (guest.expires_at - await db_now(app)).total_seconds()) + 0.3)
    after = await guest.client.get("/api/v1/moods")
    assert after.status_code == 401 and after.json()["error"]["code"] == "GUEST_EXPIRED"
    assert "value" not in after.text


class Probe:
    """Drives GuestOutputMiddleware with a fake inner app and a controllable monotonic clock."""

    def __init__(self, *, deadline=None, body=b'{"secret":"private-canary"}', frames=None):
        from app.modules.guests.deadlines import GuestDeadline
        from app.modules.guests.output import GuestOutputMiddleware

        self.now = 100.0
        self.events: list[str] = []
        self.sent: list[dict] = []
        self.body, self.frames = body, frames or [body]
        self.release = asyncio.Event()
        guest = None
        if deadline is not None:
            guest = GuestDeadline(
                expires_at=None, remaining_seconds=deadline, monotonic_deadline=100.0 + deadline
            )
        self.guest = guest

        async def inner(scope, receive, send):
            if self.guest is not None:
                scope["state"]["guest_output"] = self.guest
            scope["state"]["request_id"] = "req-1"
            await send({"type": "http.response.start", "status": 200, "headers": [(b"x-a", b"1")]})
            for index, frame in enumerate(self.frames):
                self.events.append(f"build:{index}")
                await self.release.wait()  # a queue/serialization wait after the body exists
                await send(
                    {
                        "type": "http.response.body",
                        "body": frame,
                        "more_body": index < len(self.frames) - 1,
                    }
                )

        self.middleware = GuestOutputMiddleware(inner, clock=lambda: self.now)

    async def run(self, *, advance_to=None, advance_before_release=None):
        async def send(message):
            self.events.append(f"send:{message['type'].rsplit('.', 1)[-1]}")
            self.sent.append(message)

        async def receive():
            return {"type": "http.request", "body": b"", "more_body": False}

        task = asyncio.create_task(self.middleware({"type": "http", "state": {}}, receive, send))
        await asyncio.sleep(0.05)
        if advance_before_release is not None:
            self.now = advance_before_release
        self.release.set()
        await asyncio.wait_for(task, 2)
        return self

    @property
    def wire(self) -> bytes:
        return b"".join(m.get("body", b"") for m in self.sent if m["type"] == "http.response.body")

    @property
    def status(self):
        return next(m["status"] for m in self.sent if m["type"] == "http.response.start")


async def test_private_output_guard_runs_after_queue_wait():
    # Body built before T; the wait pushes the clock past T; no private byte reaches the wire.
    late = await Probe(deadline=5).run(advance_before_release=105.0)
    assert b"private-canary" not in late.wire
    assert late.status == 401
    envelope = json.loads(late.wire)
    assert envelope["error"]["code"] == "GUEST_EXPIRED" and envelope["error"]["requestId"] == "req-1"
    cookies = [value for key, value in late.sent[0]["headers"] if key == b"set-cookie"]
    assert len(cookies) == 3 and all(b"Max-Age=0" in cookie for cookie in cookies)

    # One tick before T the very same frame is delivered untouched.
    early = await Probe(deadline=5).run(advance_before_release=104.999)
    assert early.status == 200 and early.wire == b'{"secret":"private-canary"}'

    # Public (non-guest) output is never touched, even with an old clock.
    public = await Probe().run(advance_before_release=10_000.0)
    assert public.status == 200 and public.wire == b'{"secret":"private-canary"}'


async def test_streaming_bytes_stop_at_the_deadline_without_late_content():
    # Headers already went out; the second frame is judged on its own and is suppressed.
    probe = Probe(deadline=5, frames=[b"data: one\n\n", b"data: two-private-canary\n\n"])

    async def run():
        async def send(message):
            probe.sent.append(message)
            probe.events.append(f"send:{message['type'].rsplit('.', 1)[-1]}")
            if message["type"] == "http.response.body" and message.get("body") == b"data: one\n\n":
                probe.now = 106.0  # time passes while the second frame is being prepared

        task = asyncio.create_task(
            probe.middleware({"type": "http", "state": {}}, lambda: None, send)
        )
        await asyncio.sleep(0.05)
        probe.release.set()
        await asyncio.wait_for(task, 2)

    await run()
    assert b"data: one" in probe.wire and b"two-private-canary" not in probe.wire
    assert probe.sent[-1] == {"type": "http.response.body", "body": b"", "more_body": False}


async def test_final_check_is_immediately_before_send_with_no_await_between():
    """The ordered log shows the check and the send as adjacent steps (no queue in between)."""
    probe = Probe(deadline=5)
    log: list[str] = []
    real_clock = probe.middleware.clock

    def logged_clock():
        log.append("check")
        return real_clock()

    probe.middleware.clock = logged_clock

    async def send(message):
        log.append(f"send:{message['type'].rsplit('.', 1)[-1]}")

    task = asyncio.create_task(
        probe.middleware({"type": "http", "state": {}}, lambda: None, send)
    )
    await asyncio.sleep(0.05)
    probe.release.set()
    await asyncio.wait_for(task, 2)
    body_at = log.index("send:body")
    assert log[body_at - 1] == "check", log


async def test_real_app_withholds_private_bytes_when_the_handler_outlives_the_trial(clients):
    """End to end through the ASGI stack: the response is built before T and finishes after."""
    from fastapi import Depends

    from app.core.security import Actor, require_actor

    app, _ = clients
    guest = await add_guest(app, started_ago=LIFETIME - timedelta(seconds=2))
    gate = asyncio.Event()

    async def slow(actor: Actor = Depends(require_actor)):
        await gate.wait()
        return {"secret": "private-canary"}

    app.add_api_route("/api/v1/_test/slow", slow, methods=["GET"])
    pending = asyncio.create_task(guest.client.get("/api/v1/_test/slow"))
    await asyncio.sleep(0.3)
    await asyncio.sleep(max(0.0, (guest.expires_at - await db_now(app)).total_seconds()) + 0.3)
    gate.set()
    response = await asyncio.wait_for(pending, 5)
    assert response.status_code == 401 and response.json()["error"]["code"] == "GUEST_EXPIRED"
    assert "private-canary" not in response.text
    # A registered request is unaffected by the guard.
    _, actors = clients
    assert (await actors[0][0].get("/api/v1/session")).status_code == 200


async def test_dispatch_guard_denies_at_or_after_the_deadline(clients):
    from app.core.security import Actor
    from app.modules.guests.deadlines import guard_guest_dispatch

    app, actors = clients
    live = await add_guest(app)
    actor = Actor(live.user_id, live.session_id, 1, "guest")
    deadline = await guard_guest_dispatch(app.state.database, actor)
    assert deadline is not None and 6000 < deadline.remaining_seconds <= 7200
    assert deadline.remaining() > 0  # the synchronous comparison the caller makes before sending

    expired = await add_guest(app, started_ago=LIFETIME + timedelta(seconds=1))
    from app.core.errors import DomainError

    with pytest.raises(DomainError) as denied:
        await guard_guest_dispatch(
            app.state.database, Actor(expired.user_id, expired.session_id, 1, "guest")
        )
    assert denied.value.code == "GUEST_EXPIRED"
    # Registered actors are not bounded by this guard.
    assert (
        await guard_guest_dispatch(
            app.state.database, Actor(actors[0][1], actors[0][1], 1, "registered")
        )
        is None
    )


async def test_guest_transactions_bound_statements_to_the_remaining_grant(clients):
    from app.core.security import Actor, transaction

    app, _ = clients
    guest = await add_guest(app, started_ago=LIFETIME - timedelta(seconds=30))
    request = SimpleNamespace(app=app)
    actor = Actor(guest.user_id, guest.session_id, 1, "guest")
    async with transaction(request, actor, eligible=False) as (db, _user):
        milliseconds = await db.scalar(text("select current_setting('statement_timeout')"))
    setting = milliseconds.strip()
    value = int(setting[:-2]) if setting.endswith("ms") else int(setting.rstrip("s")) * 1000
    assert 0 < value <= 30_000, setting


async def start_guest_run(app, guest, model):
    """A live guest with AI consent opens a chat and sends one message; the model is held."""
    from uuid import uuid4

    from tests.guest_helpers import enable_paid_fixture

    enable_paid_fixture(app)
    app.state.ai.model_override = model
    ai = await guest.client.put(
        "/api/v1/consents/AI",
        json={"enabled": True, "expectedVersion": 1, "policyVersion": "v1"},
        headers={"Idempotency-Key": str(uuid4())},
    )
    assert ai.status_code == 200, ai.text
    created = await guest.client.post(
        "/api/v1/ai/conversations", json={"botId": "may"}, headers={"Idempotency-Key": str(uuid4())}
    )
    assert created.status_code == 201, created.text
    conversation = created.json()
    accepted = await guest.client.post(
        f"/api/v1/ai/conversations/{conversation['conversationId']}/messages",
        json={
            "text": "PRIVATE-INPUT-CANARY",
            "clientMessageId": str(uuid4()),
            "expectedConversationVersion": conversation["version"],
        },
        headers={"Idempotency-Key": str(uuid4())},
    )
    assert accepted.status_code == 202, accepted.text
    return conversation, accepted.json()


async def test_idle_sse_closes_at_deadline_and_the_late_result_is_discarded(clients):
    from app.ai.runtime import LiveRun
    from tests.fakes import ScriptedModel, message_output

    app, _ = clients
    guest = await add_guest(app, started_ago=LIFETIME - timedelta(seconds=3), consents=False)
    model = ScriptedModel(
        [[message_output(json.dumps({"text": "PRIVATE-FINAL-CANARY", "cards": []}))]], hold=True
    )
    _, run = await start_guest_run(app, guest, model)
    await asyncio.wait_for(model.started.wait(), 5)
    run_id = run["runId"] if "runId" in run else run["run_id"]

    stream = asyncio.create_task(guest.client.get(run["eventsUrl"]))
    await asyncio.sleep(max(0.0, (guest.expires_at - await db_now(app)).total_seconds()) + 0.2)
    # The model only now answers: this is late output and must never be published or sent.
    model.release.set()
    response = await asyncio.wait_for(stream, 8)
    body = response.text
    assert "PRIVATE-FINAL-CANARY" not in body and "PRIVATE-INPUT-CANARY" not in body
    assert "event: final" not in body
    assert response.status_code == 401 or "event: revoked" in body, body[-600:]
    await asyncio.sleep(0.5)
    live: LiveRun | None = app.state.ai.runs.get(__import__("uuid").UUID(run_id))
    assert live is None or not any(event.type == "final" for event in live.events)
    assert len(model.calls) == 1, "no second model dispatch after the deadline"


@pytest.mark.parametrize("replay", [False, True])
async def test_queued_sse_final_is_dropped_at_expiry(clients, replay):
    """An actual completed run's final frame waits INSIDE the last output guard across T."""
    from starlette.middleware import Middleware

    from app.modules.guests.output import GuestOutputMiddleware
    from tests.fakes import ScriptedModel, message_output

    app, _ = clients
    queued, release = asyncio.Event(), asyncio.Event()

    class HoldFinal:
        def __init__(self, app):
            self.app = app

        async def __call__(self, scope, receive, send):
            async def held(message):
                if message["type"] == "http.response.body" and b"event: final" in message.get("body", b""):
                    queued.set()
                    await release.wait()
                await send(message)
            await self.app(scope, receive, held)

    index = next(i for i, entry in enumerate(app.user_middleware) if entry.cls is GuestOutputMiddleware)
    app.user_middleware.insert(index + 1, Middleware(HoldFinal))
    guest = await add_guest(app, started_ago=LIFETIME - timedelta(seconds=4))
    model = ScriptedModel([[message_output(json.dumps({"text": "QUEUED-FINAL-PRIVATE", "cards": []}))]])
    _, run = await start_guest_run(app, guest, model)
    # Wait for real validated output so the test exercises replay/queue, not a late model.
    live = next(iter(app.state.ai.runs.values()))
    await asyncio.wait_for(live.task, 2)
    assert any(event.type == "final" for event in live.events)
    stream = asyncio.create_task(guest.client.get(run["eventsUrl"], headers={"Last-Event-ID": "1"} if replay else {}))
    await asyncio.wait_for(queued.wait(), 2)
    await asyncio.sleep(max(0, (guest.expires_at - await db_now(app)).total_seconds()) + 0.1)
    release.set()
    result = await asyncio.wait_for(stream, 3)
    assert "QUEUED-FINAL-PRIVATE" not in result.text
    assert "event: final" not in result.text
    assert result.status_code in (200, 401)
    assert len(model.calls) == 1


async def test_ai_run_is_cancelled_at_the_deadline_without_waiting_for_the_monitor(clients):
    from tests.fakes import ScriptedModel, message_output

    app, _ = clients
    guest = await add_guest(app, started_ago=LIFETIME - timedelta(seconds=2))
    model = ScriptedModel([[message_output(json.dumps({"text": "late", "cards": []}))]], hold=True)
    _, run = await start_guest_run(app, guest, model)
    await asyncio.wait_for(model.started.wait(), 5)
    live = next(iter(app.state.ai.runs.values()))
    assert live.deadline is not None and 0 < live.deadline.remaining() <= 2.5
    await asyncio.sleep(max(0.0, live.deadline.remaining()) + 0.15)
    # Cancelled by the deadline task itself, well inside the 0.5 s policy-monitor cadence.
    assert live.terminal and live.terminal_status in ("cancelled", "failed")
    assert model.cancelled, "the held provider call is cancelled, not allowed to finish"
    assert not any(event.type == "final" for event in live.events)


def test_conversation_store_never_outlives_a_hard_deadline():
    from app.ai.store import ConversationStore
    from app.core.errors import DomainError

    clock = [10.0]
    store = ConversationStore(clock=lambda: clock[0], ttl_seconds=86_400)
    c = store.create("guest", "session", "may", hard_deadline=15.0)
    assert store.get(c.id, "guest", "session").bot_id == "may"
    clock[0] = 15.0
    with pytest.raises(DomainError) as expired:
        store.get(c.id, "guest", "session")
    assert expired.value.status == 410 and c.id not in store.conversations
    # Registered conversations keep the sliding idle policy untouched.
    clock[0] = 16.0
    registered = store.create("user", "session", "may")
    clock[0] = 100.0
    assert store.get(registered.id, "user", "session").user_id == "user"


async def test_expire_guest_clears_every_runtime_copy(clients):
    from tests.fakes import ScriptedModel, message_output

    app, _ = clients
    guest = await add_guest(app)
    model = ScriptedModel([[message_output(json.dumps({"text": "x", "cards": []}))]], hold=True)
    await start_guest_run(app, guest, model)
    await asyncio.wait_for(model.started.wait(), 5)
    runtime = app.state.ai
    assert runtime.runs and runtime.store.conversations
    runtime.expire_guest(guest.user_id)
    assert not runtime.runs and not runtime.store.conversations
    assert not [p for p in runtime.proposals.values() if p.user_id == guest.user_id]
    await asyncio.sleep(0.1)
    assert model.cancelled
