import asyncio
import json
import logging
import time
from collections.abc import Awaitable, Callable
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any, Literal
from uuid import UUID, uuid4

from agents import FunctionTool, RunContextWrapper, function_tool
from agents.strict_schema import ensure_strict_json_schema
from sqlalchemy import select, update

from app.ai.accounting import UsageSnapshot, persist_snapshot, reserve_accounting
from app.ai.availability import AiStatus, public_failure
from app.ai.context import (
    JOURNAL_TURN_POLICY,
    MOOD_TURN_POLICY,
    ContextStamp,
    SourceState,
    build_history,
    model_messages,
)
from app.ai.conversation import CONVERSATION_POLICY
from app.ai.evidence import EVIDENCE_POLICY, EvidenceEnvelope
from app.ai.journal import (
    JOURNAL_EVIDENCE_POLICY,
    JournalEvidence,
    JournalSource,
    assert_journal_revisions,
    journal_read_refused,
)
from app.ai.models import AiMessageRecord
from app.ai.persistence import current_turn, owned_conversation
from app.ai.prompts import SELECTED_VARIANTS, prompt_version
from app.ai.schemas import AIEvent, AIMessage, AiOutput, MoodReadScope
from app.ai.store import ConversationStore
from app.ai.usage import UsageEvent
from app.core.errors import DomainError
from app.core.security import Actor, assert_purpose, lock_actor
from app.core.streams import StreamSlots
from app.infrastructure.database.models import AiRun, AiUsage, Consent, now
from app.modules.guests.deadlines import GuestDeadline, final_guest_authorization
from app.modules.guests.policy import guest_expired


@dataclass
class LiveRun:
    actor: Actor
    conversation_id: UUID
    data_version: int
    id: UUID
    mood_scope: MoodReadScope | None = None
    events: list[AIEvent] = field(default_factory=list)
    wake: asyncio.Event = field(default_factory=asyncio.Event)
    task: asyncio.Task | None = None
    terminal: bool = False
    version: int = 1
    tool_calls: int = 0
    started: float = field(default_factory=time.monotonic)
    drive_started: bool = False
    cancel_requested: bool = False
    terminal_status: str | None = None
    finalization_task: asyncio.Task | None = None
    terminal_persisted: bool = False
    reserved_output_bytes: int = 0
    usage: UsageSnapshot = field(default_factory=UsageSnapshot)
    failure: dict[str, str] | None = None
    persistent: bool = False
    first_progress_ms: int | None = None
    sources: dict[str, SourceState] = field(default_factory=dict)
    mood_evidence: EvidenceEnvelope | None = None
    journal_evidence: JournalEvidence | None = None
    journal_read_allowed: bool = True
    # Conservative guest bound; None for registered users (their policy is unchanged).
    deadline: GuestDeadline | None = None
    # Guest paid work: the quota claim, the detached reservation and the pre-dispatch guard.
    quota: Any = None
    reservation: Any = None
    dispatched: bool = False
    before_dispatch: Callable[[], Awaitable[None]] | None = None


@dataclass
class Proposal:
    user_id: UUID
    session_id: UUID
    bot_id: str
    text: str
    purpose: str
    data_version: int
    expires_at: float
    id: UUID = field(default_factory=uuid4)
    version: int = 1


class AiRuntime:
    def __init__(self, settings, database):
        from app.ai.provider import SdkProvider

        self.settings, self.database = settings, database
        self.worker_id = uuid4()
        self.provider = SdkProvider(settings)
        self.store = ConversationStore()
        self.runs: dict[UUID, LiveRun] = {}
        self.proposals: dict[UUID, Proposal] = {}
        self.model_override = None
        self.slots = asyncio.Semaphore(settings.ai_global_concurrency)
        self.finalizers: set[asyncio.Task] = set()
        self.pending_terminal: dict[UUID, LiveRun] = {}
        self.pending_inputs: dict[UUID, tuple[UUID, int]] = {}
        # Per-user SSE slots, reserved before any await (see app.core.streams).
        self.streams = StreamSlots(6)

    @property
    def available(self) -> bool:
        return self.status_for(None) in ("ready", "test_provider")

    def status_for(self, user_id: UUID | None) -> AiStatus:
        if self.model_override is not None:
            return "test_provider"
        enabled = self.settings.ai_available_for(user_id) if user_id else (
            self.settings.ai_enabled or bool(self.settings.ai_local_test_user_ids)
        )
        if not enabled:
            return "disabled"
        key, model = self.settings.openai_api_key.get_secret_value(), self.settings.openai_model
        if not key.strip() or not model.strip():
            return "configuration_missing"
        if any(char.isspace() for char in key + model):
            return "configuration_invalid"
        # Presence is not a remote credential/model validation; provider errors are
        # classified on an admitted turn, never by calling a billable health check.
        return "ready"

    def available_for(self, user_id: UUID) -> bool:
        return self.status_for(user_id) in ("ready", "test_provider")

    def sweep(self) -> None:
        self.store.sweep()
        for identity, run in list(self.runs.items()):
            if run.conversation_id not in self.store.conversations:
                self.request_cancel(run)
                run.events.clear()
                del self.runs[identity]
        for identity, proposal in list(self.proposals.items()):
            if proposal.expires_at <= time.monotonic():
                del self.proposals[identity]
        for run in list(self.pending_terminal.values()):
            self.finalize(run, run.terminal_status)

    def request_cancel(self, run: LiveRun) -> None:
        if run.terminal:
            return
        if not run.cancel_requested:
            run.cancel_requested = True
            if run.task and not run.task.done():
                run.task.cancel()
        # A Task cancelled before its first scheduler turn never enters finally.
        if not run.drive_started or not run.task or run.task.done():
            self.finalize(run, "cancelled")

    def finalize(self, run: LiveRun, status: str | None) -> asyncio.Task:
        if run.terminal_status is None:
            run.terminal_status = status or "failed"
            run.terminal = True
            logging.getLogger("moodprint").info("metric=ai_run_ended status=%s", run.terminal_status)
            run.version = 2
            remaining = self.store.conversations.get(run.conversation_id)
            if remaining and remaining.active_run_id == run.id:
                remaining.active_run_id = None
            if run.terminal_status == "cancelled":
                self.event(run, "cancelled", {})
            elif run.terminal_status == "failed":
                self.event(
                    run,
                    "failed",
                    run.failure or {
                        "code": "AI_RUN_FAILED",
                        "message": "Chưa hoàn tất phản hồi. Bạn có thể thử lại.",
                    },
                )
            run.wake.set()
        if run.finalization_task is None or (
            run.finalization_task.done() and not run.terminal_persisted
        ):
            run.finalization_task = asyncio.create_task(self.persist_terminal(run))
            self.finalizers.add(run.finalization_task)
            run.finalization_task.add_done_callback(self.finalizers.discard)
        return run.finalization_task

    async def persist_terminal(self, run: LiveRun) -> bool:
        try:
            async with self.database.require()() as db, db.begin():
                if self.settings.ai_accounting_enabled:
                    if not await persist_snapshot(db, run.id, self.worker_id, run.usage, terminal=True):
                        status = await db.scalar(select(AiRun.status).where(AiRun.id == run.id))
                        if status is None or status != "running":
                            run.terminal_status = status or run.terminal_status
                            run.terminal_persisted = True
                            self.pending_terminal.pop(run.id, None)
                            return True
                        raise RuntimeError("Worker lease expired; recovery must fence this run")
                updated = await db.scalar(
                    update(AiRun)
                    .where(AiRun.id == run.id, AiRun.status == "running")
                    .values(status=run.terminal_status, version=2)
                    .returning(AiRun.id)
                )
                if updated is None:
                    status = await db.scalar(select(AiRun.status).where(AiRun.id == run.id))
                    if status in ("completed", "failed", "cancelled", "interrupted"):
                        # A terminal outcome is immutable across competing writers.
                        run.terminal_status = status
                    elif status is not None:
                        raise RuntimeError("Run terminal state requires recovery")
                    # Purged metadata must not be recreated by an old finalizer.
            run.terminal_persisted = True
            self.pending_terminal.pop(run.id, None)
            return True
        except Exception as error:
            self.pending_terminal[run.id] = run
            logging.getLogger("moodprint").error(
                "ai_terminal_retry error_type=%s", type(error).__name__
            )
            return False

    async def stop(self, run: LiveRun) -> None:
        self.request_cancel(run)
        if run.task:
            await asyncio.shield(asyncio.gather(run.task, return_exceptions=True))
        # Shield the database cleanup from a second cancellation/disconnected caller.
        task = self.finalize(run, run.terminal_status or "cancelled")
        if not await asyncio.shield(task):
            raise DomainError(
                503, "CANCEL_PENDING", "Đã dừng phản hồi; trạng thái đang chờ đồng bộ.", True
            )

    def check_capacity(self, conversation_id: UUID, extra_bytes: int) -> None:
        def size(identity):
            c = self.store.conversations[identity]
            return sum(len(m.text.encode()) for m in c.messages) + sum(
                len(event.model_dump_json().encode())
                for run in self.runs.values()
                if run.conversation_id == identity
                for event in run.events
            ) + sum(
                run.reserved_output_bytes
                for run in self.runs.values()
                if run.conversation_id == identity
            ) + sum(
                byte_count
                for conversation, byte_count in self.pending_inputs.values()
                if conversation == identity
            )

        sizes = {identity: size(identity) for identity in self.store.conversations}
        if (
            sizes.get(conversation_id, 0) + extra_bytes > 2 * 1024 * 1024
            or sum(sizes.values()) + extra_bytes > 64 * 1024 * 1024
        ):
            raise DomainError(
                429,
                "CONTEXT_LIMIT",
                "Không gian trò chuyện đã đạt giới hạn. Hãy kết thúc phiên trước khi mở thêm.",
            )

    @contextmanager
    def reserve_input(self, conversation_id: UUID, extra_bytes: int):
        self.check_capacity(conversation_id, extra_bytes)
        identity = uuid4()
        self.pending_inputs[identity] = (conversation_id, extra_bytes)
        try:
            yield
        finally:
            self.pending_inputs.pop(identity, None)

    def event(
        self,
        run: LiveRun,
        kind: Literal["progress", "final", "completed", "failed", "cancelled"],
        data: dict,
    ) -> None:
        event = AIEvent(seq=str(len(run.events) + 1), type=kind, data=data)
        run.events.append(event)
        run.wake.set()

    async def check(self, run: LiveRun) -> None:
        if run.deadline is not None and run.deadline.remaining() <= 0:
            raise guest_expired()
        if run.terminal or time.monotonic() - run.started > self.settings.ai_timeout_seconds:
            raise DomainError(410, "RUN_ENDED", "Lượt trò chuyện đã kết thúc.")
        self.store.get(run.conversation_id, str(run.actor.user_id), str(run.actor.session_id))
        async with self.database.require()() as db, db.begin():
            user = await lock_actor(db, run.actor)
            await assert_purpose(db, user, "AI")
            if user.data_version != run.data_version:
                raise DomainError(409, "CONTEXT_CHANGED", "Quyền hoặc dữ liệu đã thay đổi.")
            await current_turn(db, run, self.worker_id)
            if run.persistent and not await owned_conversation(db, run.conversation_id, user.id):
                raise DomainError(410, "CONVERSATION_EXPIRED", "Cuộc trò chuyện đã kết thúc.")
            status = await db.scalar(
                select(AiRun.status).where(
                    AiRun.id == run.id,
                    AiRun.user_id == run.actor.user_id,
                    AiRun.conversation_id == run.conversation_id,
                )
            )
            if status != "running":
                raise DomainError(410, "RUN_ENDED", "Lượt trò chuyện đã kết thúc.")
            if self.settings.ai_accounting_enabled:
                usage = await db.get(AiUsage, run.id)
                if usage is None or usage.worker_id != self.worker_id or usage.lease_until <= now():
                    raise DomainError(410, "WORKER_FENCED", "Lượt trò chuyện đã kết thúc.")

    async def reserve_usage(self, db, run_id: UUID, user_id: UUID, bot_id: str):
        if self.settings.ai_accounting_enabled:
            await reserve_accounting(db, run_id, user_id, self.worker_id, self.settings.openai_model,
                                     # Compact journal policy revision fits existing varchar(60).
                                     prompt_version(SELECTED_VARIANTS[bot_id]) + "+" + EVIDENCE_POLICY + "+" + CONVERSATION_POLICY + ("+j1" if bot_id == "nhip" else ""))

    async def record_usage(self, run: LiveRun, event: UsageEvent):
        run.usage.observe(event)
        if self.settings.ai_accounting_enabled:
            async with self.database.require()() as db, db.begin():
                if not await persist_snapshot(db, run.id, self.worker_id, run.usage):
                    raise DomainError(410, "WORKER_FENCED", "Lượt trò chuyện đã kết thúc.")

    def invalidate(self, user_id: str, session_id: str | None = None) -> None:
        for run in self.runs.values():
            if str(run.actor.user_id) == user_id and (
                session_id is None or str(run.actor.session_id) == session_id
            ):
                self.request_cancel(run)
        for identity, c in list(self.store.conversations.items()):
            if c.user_id == user_id and (session_id is None or c.session_id == session_id):
                del self.store.conversations[identity]
        for identity, p in list(self.proposals.items()):
            if str(p.user_id) == user_id and (
                session_id is None or str(p.session_id) == session_id
            ):
                del self.proposals[identity]

    async def close(self):
        await asyncio.gather(
            *(
                self.stop(run)
                for run in self.runs.values()
                if not run.terminal or run.terminal_status
            ),
            return_exceptions=True,
        )
        if self.finalizers:
            await asyncio.gather(*self.finalizers, return_exceptions=True)
        for run in (*self.runs.values(), *self.pending_terminal.values()):
            run.events.clear()
        self.runs.clear()
        self.store.clear()
        self.proposals.clear()
        self.pending_inputs.clear()
        closer = getattr(self.provider, "aclose", None)
        if closer:
            await closer()

    def tools(self, run: LiveRun, bot_id: str, *, memory_enabled: bool = True):
        async def check_tool():
            await self.check(run)
            run.tool_calls += 1
            if run.tool_calls > 2:
                raise DomainError(429, "TOOL_LIMIT", "Đã hết số thao tác cho lượt này.")

        async def propose(text: str, purpose: str):
            await check_tool()
            if not text.strip() or len(text.strip()) > 120:
                raise DomainError(422, "INVALID_PROPOSAL", "Nội dung đề xuất chưa hợp lệ.")
            async with self.database.require()() as db, db.begin():
                user = await lock_actor(db, run.actor)
                # A preview is temporary; persistence still requires approval.
                await assert_purpose(db, user, "AI")
                if user.data_version != run.data_version:
                    raise DomainError(409, "CONTEXT_CHANGED", "Quyền hoặc dữ liệu đã thay đổi.")
                from app.ai.memory import create_proposal

                p = await create_proposal(db, run.actor, bot_id, text.strip(), purpose, run.data_version)
            return {
                "status": "proposed",
                "proposalId": str(p.id),
                "proposalVersion": 1,
                "text": p.text,
                "purpose": purpose,
            }

        @function_tool(failure_error_function=None)
        async def propose_memory(ctx: RunContextWrapper[LiveRun], text: str) -> str:
            """Propose one short memory for the user to preview and approve. This never saves it."""
            return json.dumps(await propose(text, "memory"), ensure_ascii=False)

        @function_tool(failure_error_function=None)
        async def propose_private_item(ctx: RunContextWrapper[LiveRun], text: str) -> str:
            """Propose a tentative self-description, requiring explicit human confirmation."""
            return json.dumps(await propose(text, "private_item"), ensure_ascii=False)

        async def read_mood_summary(ctx: RunContextWrapper[LiveRun], arguments: str) -> str:
            """Read only mood scores for the dates explicitly selected for this turn. No notes or inferred missing days."""
            from app.modules.mood.service import selected_summary

            if json.loads(arguments) != {}:
                raise DomainError(
                    422, "INVALID_TOOL_ARGUMENTS", "Công cụ không nhận nguồn do model chọn."
                )
            state = run.sources.setdefault("mood", SourceState())
            try:
                await check_tool()
                async with self.database.require()() as db, db.begin():
                    user = await lock_actor(db, run.actor)
                    await assert_purpose(db, user, "AI")
                    if user.data_version != run.data_version:
                        raise DomainError(409, "CONTEXT_CHANGED", "Quyền hoặc dữ liệu đã thay đổi.")
                    if bot_id != "nhip" or run.mood_scope is None:
                        raise DomainError(403, "MOOD_SCOPE_REQUIRED", "Hãy chọn khoảng ngày trước.")
                    result = await selected_summary(db, user, run.mood_scope)
                await self.check(run)
            except Exception:
                state.evidence = "tool_execution_failure"
                raise
            state.authorization, state.evidence = "authorized", "retrieved"
            state.record_count = result["count"]
            run.mood_evidence = EvidenceEnvelope.from_summary(
                result, run, expires_at=datetime.now(UTC) + timedelta(
                    seconds=max(0, self.settings.ai_timeout_seconds - (time.monotonic() - run.started))
                ),
            )
            result["evidence"] = run.mood_evidence.model_view()
            return json.dumps(result, ensure_ascii=False)

        async def search_journal_entries(ctx: RunContextWrapper[LiveRun], arguments: str) -> str:
            from app.modules.journal.ai import JournalSearchInput, search_for_ai

            args = JournalSearchInput.model_validate_json(arguments)
            state = run.sources.setdefault("journal", SourceState())
            try:
                await check_tool()
                if bot_id != "nhip" or run.mood_scope is not None or not run.journal_read_allowed:
                    raise DomainError(403, "JOURNAL_READ_DENIED", "Lượt này không đọc nhật ký.")
                async with self.database.require()() as db, db.begin():
                    user = await lock_actor(db, run.actor)
                    await assert_purpose(db, user, "AI")
                    if user.data_version != run.data_version:
                        raise DomainError(409, "CONTEXT_CHANGED", "Quyền hoặc dữ liệu đã thay đổi.")
                    result = await search_for_ai(db, user, **args.model_dump())
                    # Persist provenance before any retrieved prose can reach the model.
                    turn = await current_turn(db, run, self.worker_id)
                    if turn is not None:
                        turn.context_policy = JOURNAL_TURN_POLICY
                conversation = self.store.get(run.conversation_id, str(run.actor.user_id), str(run.actor.session_id))
                conversation.context_stamps[run.id] = ContextStamp(run.data_version, JOURNAL_TURN_POLICY)
                await self.check(run)
            except Exception:
                state.evidence = "tool_execution_failure"
                raise
            sources = {source.entry_id: source for source in run.journal_evidence.sources} if run.journal_evidence else {}
            for entry in result["entries"]:
                sources[UUID(entry["id"])] = JournalSource(UUID(entry["id"]), datetime.fromisoformat(entry["localDate"]).date(), entry["version"])
            run.journal_evidence = JournalEvidence(
                owner_id=run.actor.user_id, run_id=run.id, data_version=run.data_version,
                expires_at=datetime.now(UTC) + timedelta(seconds=max(0, self.settings.ai_timeout_seconds - (time.monotonic() - run.started))),
                sources=tuple(sources.values()),
            )
            state.authorization, state.evidence = "authorized", "retrieved"
            state.record_count = len(sources)
            result["evidence"] = {"policy": JOURNAL_EVIDENCE_POLICY, "reuse": "current_run_only"}
            return json.dumps(result, ensure_ascii=False)

        if bot_id == "guong":
            return ([propose_memory] if memory_enabled else []) + [propose_private_item]
        if bot_id == "nhip" and run.mood_scope is not None:
            return [
                *([propose_memory] if memory_enabled else []),
                FunctionTool(
                    name="read_mood_summary",
                    description="Read mood score statistics only for the dates selected by the user for this turn. Never returns private notes.",
                    params_json_schema={
                        "type": "object",
                        "properties": {},
                        "required": [],
                        "additionalProperties": False,
                    },
                    on_invoke_tool=read_mood_summary,
                ),
            ]
        if bot_id == "nhip":
            from app.modules.journal.ai import JournalSearchInput

            return [
                *([propose_memory] if memory_enabled else []),
                FunctionTool(
                    name="search_journal_entries",
                    description="Search a bounded sample of your saved journal entries. Only current owner text/metadata, never drafts, attachments or legacy mood notes.",
                    params_json_schema=ensure_strict_json_schema(JournalSearchInput.model_json_schema(by_alias=False)),
                    on_invoke_tool=search_journal_entries,
                ),
            ]
        if bot_id == "may":
            return [propose_memory] if memory_enabled else []
        return []

    def guest_dispatch_guard(self, run: LiveRun) -> Callable[[], Awaitable[None]]:
        """Last awaited authorization before each provider request of a guest run."""
        from app.modules.guests.accounting import mark_guest_dispatched

        async def guard() -> None:
            if run.reservation is not None and not run.dispatched:
                # Persisted BEFORE the send: a crash after this point charges the upper bound.
                async with self.database.require()() as db, db.begin():
                    await mark_guest_dispatched(db, run.reservation.id)
                run.dispatched = True
            await self.check(run)  # fresh database lifetime + live policy
            if run.deadline is not None and run.deadline.remaining() <= 0:
                raise guest_expired()

        return guard

    async def settle_guest(self, run: LiveRun, status: str) -> None:
        """Settle the detached reservation once, then finish the quota claim (never an upsert)."""
        if run.reservation is None:
            return
        from app.modules.guests import accounting, limits, pricing

        actual: int | None = None
        if (
            status == "completed"
            and run.dispatched
            and run.usage.responses_received > 0
            and (run.usage.input_tokens or run.usage.output_tokens)
        ):
            actual = pricing.actual_ai_cost(
                self.settings.guest_pricing_json,
                run.usage.input_tokens,
                run.usage.cached_input_tokens,
                run.usage.output_tokens,
            )
        try:
            async with self.database.require()() as db, db.begin():
                if not run.dispatched:
                    await accounting.release_guest_operation(db, run.reservation.id)
                else:
                    await accounting.settle_guest_operation(db, run.reservation, actual)
            if run.quota is not None:
                async with self.database.require()() as db, db.begin():
                    await limits.finish_guest_quota(
                        db, run.actor.user_id, "ai", run.quota.operation_key_hash, run.quota.lease_token
                    )
        except Exception as error:
            # The stale-reservation sweep charges it uncertain; never lose liability silently.
            logging.getLogger("moodprint").error(
                "guest_settlement_deferred error_type=%s", type(error).__name__
            )

    async def _cancel_at_deadline(self, run: LiveRun) -> None:
        """Stop a guest run exactly at its bound, independent of the 0.5 s policy monitor."""
        assert run.deadline is not None
        await asyncio.sleep(max(0.0, run.deadline.remaining()))
        self.request_cancel(run)

    def expire_guest(self, user_id: UUID) -> None:
        """Cancel and drop every in-memory copy for an ended or expired guest."""
        uid = str(user_id)
        self.invalidate(uid)
        for identity, run in list(self.runs.items()):
            if str(run.actor.user_id) == uid:
                run.events.clear()
                run.mood_evidence = None
                run.journal_evidence = None
                run.sources.clear()
                del self.runs[identity]
        for identity, pending in list(self.pending_terminal.items()):
            if str(pending.actor.user_id) == uid:
                del self.pending_terminal[identity]

    async def drive(self, run: LiveRun) -> None:
        from app.modules.guests.limits import maintain_guest_quota
        run.drive_started = True
        status = "failed"
        # Guest activity identifiers must never leave active stores via operational
        # logs (including structured args). Registered runs retain their diagnostic ID.
        identity_field = "" if run.actor.account_kind == "guest" else " run_id=%s"
        identity_args = () if run.actor.account_kind == "guest" else (run.id,)
        monitor = None
        expiry = None
        budget = self.settings.ai_timeout_seconds
        if run.deadline is not None:
            budget = min(budget, max(0.0, run.deadline.remaining()))
            expiry = asyncio.create_task(self._cancel_at_deadline(run))
        try:
            async with maintain_guest_quota(self.database, run.actor.user_id, "ai", run.quota), asyncio.timeout(budget), self.slots:
                await self.check(run)
                c = self.store.get(
                    run.conversation_id, str(run.actor.user_id), str(run.actor.session_id)
                )
                from app.ai.embeddings import MEMORY_BOTS, retrieve_memories

                # Check live durable policy before projecting either transcript or
                # memory. data_version is monotonic across revoke/regrant and edits.
                async with self.database.require()() as db, db.begin():
                    user = await lock_actor(db, run.actor)
                    consents = await assert_purpose(db, user, "AI")
                    if user.data_version != run.data_version:
                        raise DomainError(409, "CONTEXT_CHANGED", "Quyền hoặc dữ liệu đã thay đổi.")
                    mem: Consent | None = consents.get("MEM")
                    memory_state = SourceState()
                    if mem and mem.enabled and mem.policy_version == "v1":
                        memory_state.authorization = "authorized"
                    elif mem and mem.version > 1:
                        memory_state.authorization = "revoked"
                    if c.bot_id not in MEMORY_BOTS:
                        memory_state.evidence = "tool_unavailable"
                    run.sources["memory"] = memory_state
                run.sources["mood"] = SourceState(
                    authorization="authorized" if run.mood_scope else "no_current_authorization",
                    previous="previously_authorized" if any(
                        s.policy == MOOD_TURN_POLICY for rid, s in c.context_stamps.items() if rid != run.id
                    ) else "missing_verified_evidence",
                    evidence="missing_verified_evidence" if c.bot_id == "nhip" and run.mood_scope else "tool_unavailable",
                )
                if c.bot_id == "nhip" and run.mood_scope is None:
                    run.sources["journal"] = SourceState(authorization="authorized")
                projected = model_messages(
                    c.messages, c.context_stamps, current_run=run.id, data_version=run.data_version
                )
                memories = []
                if memory_state.authorization == "authorized" and memory_state.evidence != "tool_unavailable":
                    try:
                        memories = await retrieve_memories(
                            self.database, self.settings, run.actor, c.bot_id,
                            projected[-1].text if projected else "", run.data_version,
                            operation_key=f"embed-query:{run.id}",
                        )
                    except Exception:
                        memory_state.evidence = "tool_execution_failure"
                        raise
                    memory_state.evidence, memory_state.record_count = "retrieved", len(memories)
                await self.check(run)
                history = build_history(projected, memories)
                run.journal_read_allowed = not journal_read_refused(history)

                async def monitor_policy():
                    while True:
                        await asyncio.sleep(0.5)
                        try:
                            await self.check(run)
                        except Exception:
                            if run.task and not run.task.done():
                                run.task.cancel()
                            return

                monitor = asyncio.create_task(monitor_policy())

                async def progress():
                    await self.check(run)
                    if run.first_progress_ms is None:
                        run.first_progress_ms = round((time.monotonic() - run.started) * 1000)
                    self.event(run, "progress", {})

                async def observe(event):
                    await self.record_usage(run, event)

                output = await self.provider.run(
                    bot_id=c.bot_id,
                    history=history,
                    tools=self.tools(run, c.bot_id, memory_enabled=True),
                    context=run,
                    on_progress=progress,
                    model_override=self.model_override,
                    usage_observer=observe,
                )
                output = AiOutput.model_validate(output)
                if run.mood_evidence is not None:
                    run.mood_evidence.assert_current(run)
                if run.journal_evidence is not None:
                    run.journal_evidence.assert_current(run)
                await self.check(run)
                # Include the replay copy and message copy, not only plain text.
                output_bytes = len(output.model_dump_json().encode()) + len(output.text.encode()) + 1024
                self.check_capacity(run.conversation_id, output_bytes)
                async with self.database.require()() as db, db.begin():
                    user = await lock_actor(db, run.actor)
                    await assert_purpose(db, user, "AI")
                    if user.data_version != run.data_version:
                        raise DomainError(409, "CONTEXT_CHANGED", "Quyền hoặc dữ liệu đã thay đổi.")
                    await current_turn(db, run, self.worker_id)
                    await assert_journal_revisions(db, user, run)
                    if run.deadline is not None:
                        await final_guest_authorization(db, user)
                    if run.persistent:
                        durable = await owned_conversation(db, c.id, user.id, lock=True)
                        if durable is None:
                            raise DomainError(410, "CONVERSATION_EXPIRED", "Cuộc trò chuyện đã kết thúc.")
                    # Keep space across the final DB await; terminal metadata
                    # must not commit before a fallible capacity check.
                    self.check_capacity(run.conversation_id, output_bytes)
                    run.reserved_output_bytes = output_bytes
                    if self.settings.ai_accounting_enabled and not await persist_snapshot(
                        db, run.id, self.worker_id, run.usage, terminal=True,
                    ):
                        raise DomainError(410, "WORKER_FENCED", "Lượt trò chuyện đã kết thúc.")
                    completed = await db.scalar(
                        update(AiRun)
                        .where(AiRun.id == run.id, AiRun.status == "running")
                        .values(status="completed", version=2)
                        .returning(AiRun.id)
                    )
                    if completed is None:
                        raise DomainError(410, "RUN_ENDED", "Lượt trò chuyện đã kết thúc.")
                    if run.persistent:
                        durable.version += 1
                        durable.updated_at = now()
                        db.add(AiMessageRecord(conversation_id=c.id, sequence=durable.version, actor="bot", text=output.text, cards=[card.model_dump(mode="json", by_alias=True) for card in output.cards], run_id=run.id))
                if run.deadline is not None and run.deadline.remaining() <= 0:
                    # Decided before T but published after it: drop, never append late output.
                    raise guest_expired()
                # Do not publish tokens/JSON before output and live policy have both passed.
                c.messages.append(
                    AIMessage(id=uuid4(), actor="bot", text=output.text, cards=output.cards, created_at=now(), run_id=run.id, status="completed")
                )
                c.version += 1
                self.event(run, "final", output.model_dump(mode="json", by_alias=True))
                self.event(run, "completed", {})
                status = "completed"
        except asyncio.CancelledError:
            status = "cancelled"
        except Exception as error:
            status = "failed"
            run.failure = public_failure(error)
            logging.getLogger("moodprint").warning("ai_execution_error" + identity_field + " error_type=%s code=%s", *identity_args, type(error).__name__, error.code if isinstance(error, DomainError) else "AI_RUN_FAILED")
        finally:
            # No snapshot survives a terminal run, saved-chat reload or worker restart.
            run.mood_evidence = None
            run.journal_evidence = None
            # Stop every cancellation source before awaiting any drain. A second expiry/
            # policy cancellation must not strand settlement or terminal persistence.
            if monitor:
                monitor.cancel()
            if expiry:
                expiry.cancel()

            async def finish_terminal():
                await asyncio.gather(*(task for task in (monitor, expiry) if task), return_exceptions=True)
                run.reserved_output_bytes = 0
                await self.settle_guest(run, status)
                await self.finalize(run, status)

            cleanup = asyncio.create_task(finish_terminal())
            while not cleanup.done():
                try:
                    await asyncio.shield(cleanup)
                except asyncio.CancelledError:
                    # Cancellation has already stopped the provider. Finish private cleanup
                    # before allowing shutdown/revocation to consider this task drained.
                    continue
            await cleanup
            # Saved threads reload from PostgreSQL; keep no idle RAM copy per thread.
            copy = self.store.conversations.get(run.conversation_id)
            if copy is not None and copy.persistent and copy.active_run_id is None:
                del self.store.conversations[run.conversation_id]
            logging.getLogger("moodprint").info("ai_execution_end" + identity_field + " status=%s duration_ms=%s first_progress_ms=%s input_tokens=%s output_tokens=%s model_requests=%s active_local=%s", *identity_args, run.terminal_status, round((time.monotonic()-run.started)*1000), run.first_progress_ms, run.usage.input_tokens, run.usage.output_tokens, run.usage.requests_started, sum(not r.terminal for r in self.runs.values()))
