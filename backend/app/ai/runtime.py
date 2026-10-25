import asyncio
import json
import logging
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Literal
from uuid import UUID, uuid4

from agents import FunctionTool, RunContextWrapper, function_tool
from sqlalchemy import select, update

from app.ai.accounting import UsageSnapshot, persist_snapshot, reserve_accounting
from app.ai.context import build_history
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
    persistent: bool = False
    first_progress_ms: int | None = None


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
        return self.model_override is not None or bool(
            (self.settings.ai_enabled or self.settings.ai_local_test_user_ids)
            and self.settings.openai_model
            and self.settings.openai_api_key.get_secret_value()
        )

    def available_for(self, user_id: UUID) -> bool:
        return self.model_override is not None or (
            self.available and self.settings.ai_available_for(user_id)
        )

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
                    {
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
                                     prompt_version(SELECTED_VARIANTS[bot_id]))

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
                await assert_purpose(db, user, "MEM" if purpose == "memory" else "AI")
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
        if bot_id in ("may", "nhip"):
            return [propose_memory] if memory_enabled else []
        return []

    async def drive(self, run: LiveRun) -> None:
        run.drive_started = True
        status = "failed"
        monitor = None
        try:
            async with asyncio.timeout(self.settings.ai_timeout_seconds), self.slots:
                await self.check(run)
                c = self.store.get(
                    run.conversation_id, str(run.actor.user_id), str(run.actor.session_id)
                )
                async with self.database.require()() as db, db.begin():
                    user = await lock_actor(db, run.actor)
                    consents = {
                        x.purpose: x
                        for x in (
                            await db.scalars(select(Consent).where(Consent.user_id == user.id))
                        ).all()
                    }
                from app.ai.embeddings import retrieve_memories

                memories = await retrieve_memories(self.database, self.settings, run.actor, c.bot_id, c.messages[-1].text if c.messages else "", run.data_version)
                await self.check(run)
                history = build_history(c.messages, memories)

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
                    tools=self.tools(run, c.bot_id, memory_enabled=consents["MEM"].enabled),
                    context=run,
                    on_progress=progress,
                    model_override=self.model_override,
                    usage_observer=observe,
                )
                output = AiOutput.model_validate(output)
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
            logging.getLogger("moodprint").warning("ai_execution_error run_id=%s error_type=%s code=%s", run.id, type(error).__name__, error.code if isinstance(error, DomainError) else "AI_RUN_FAILED")
        finally:
            if monitor:
                monitor.cancel()
                await asyncio.gather(monitor, return_exceptions=True)
            run.reserved_output_bytes = 0
            await asyncio.shield(self.finalize(run, status))
            # Saved threads reload from PostgreSQL; keep no idle RAM copy per thread.
            copy = self.store.conversations.get(run.conversation_id)
            if copy is not None and copy.persistent and copy.active_run_id is None:
                del self.store.conversations[run.conversation_id]
            logging.getLogger("moodprint").info("ai_execution_end run_id=%s status=%s duration_ms=%s first_progress_ms=%s input_tokens=%s output_tokens=%s model_requests=%s active_local=%s", run.id, run.terminal_status, round((time.monotonic()-run.started)*1000), run.first_progress_ms, run.usage.input_tokens, run.usage.output_tokens, run.usage.requests_started, sum(not r.terminal for r in self.runs.values()))
