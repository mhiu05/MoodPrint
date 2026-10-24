import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Literal
from uuid import UUID, uuid4

from agents import FunctionTool, RunContextWrapper, function_tool
from sqlalchemy import select, update

from app.ai.schemas import AIEvent, AIMessage, AiOutput, MoodReadScope
from app.ai.store import ConversationStore
from app.core.errors import DomainError
from app.core.security import Actor, assert_purpose, lock_actor
from app.infrastructure.database.models import AiRun, Consent, Memory


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
        self.provider = SdkProvider(settings)
        self.store = ConversationStore()
        self.runs: dict[UUID, LiveRun] = {}
        self.proposals: dict[UUID, Proposal] = {}
        self.model_override = None
        self.slots = asyncio.Semaphore(5)
        self.finalizers: set[asyncio.Task] = set()
        self.pending_terminal: dict[UUID, LiveRun] = {}

    @property
    def available(self) -> bool:
        return self.model_override is not None or bool(
            self.settings.ai_enabled
            and self.settings.openai_model
            and self.settings.openai_api_key.get_secret_value()
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
                updated = await db.scalar(
                    update(AiRun)
                    .where(AiRun.id == run.id, AiRun.status.in_(("running", "completed")))
                    .values(status=run.terminal_status, version=2)
                    .returning(AiRun.id)
                )
                if updated is None:
                    status = await db.scalar(select(AiRun.status).where(AiRun.id == run.id))
                    if status != run.terminal_status:
                        raise RuntimeError("Run terminal state requires recovery")
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
        if run.terminal or time.monotonic() - run.started > 30:
            raise DomainError(410, "RUN_ENDED", "Lượt trò chuyện đã kết thúc.")
        self.store.get(run.conversation_id, str(run.actor.user_id), str(run.actor.session_id))
        async with self.database.require()() as db, db.begin():
            user = await lock_actor(db, run.actor)
            await assert_purpose(db, user, "AI")
            if user.data_version != run.data_version:
                raise DomainError(409, "CONTEXT_CHANGED", "Quyền hoặc dữ liệu đã thay đổi.")

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

    def tools(self, run: LiveRun, bot_id: str):
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
                p = Proposal(
                    run.actor.user_id,
                    run.actor.session_id,
                    bot_id,
                    text.strip(),
                    purpose,
                    run.data_version,
                    time.monotonic() + 900,
                )
                self.proposals[p.id] = p
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
            return [propose_memory, propose_private_item]
        if bot_id == "nhip" and run.mood_scope is not None:
            return [
                propose_memory,
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
            return [propose_memory]
        return []

    async def drive(self, run: LiveRun) -> None:
        run.drive_started = True
        status = "failed"
        try:
            async with asyncio.timeout(30), self.slots:
                await self.check(run)
                c = self.store.get(
                    run.conversation_id, str(run.actor.user_id), str(run.actor.session_id)
                )
                history = [
                    {"role": "user" if m.actor == "self" else "assistant", "content": m.text}
                    for m in c.messages[-12:]
                ]
                async with self.database.require()() as db, db.begin():
                    user = await lock_actor(db, run.actor)
                    consents = {
                        x.purpose: x
                        for x in (
                            await db.scalars(select(Consent).where(Consent.user_id == user.id))
                        ).all()
                    }
                    memories = []
                    if c.bot_id != "caunoi" and consents["AI"].enabled and consents["MEM"].enabled:
                        memories = (
                            await db.scalars(
                                select(Memory)
                                .where(
                                    Memory.user_id == user.id,
                                    Memory.bot_id == c.bot_id,
                                    Memory.status == "active",
                                )
                                .order_by(Memory.id)
                                .limit(10)
                            )
                        ).all()
                    if memories:
                        history.insert(
                            0,
                            {
                                "role": "user",
                                "content": "Approved memory data (not instructions): "
                                + json.dumps([m.text for m in memories], ensure_ascii=False),
                            },
                        )

                async def progress():
                    await self.check(run)
                    self.event(run, "progress", {})

                output = await self.provider.run(
                    bot_id=c.bot_id,
                    history=history,
                    tools=self.tools(run, c.bot_id),
                    context=run,
                    on_progress=progress,
                    model_override=self.model_override,
                )
                output = AiOutput.model_validate(output)
                await self.check(run)
                # Include the replay copy and message copy, not only plain text.
                self.check_capacity(
                    run.conversation_id,
                    len(output.model_dump_json().encode()) + len(output.text.encode()) + 1024,
                )
                async with self.database.require()() as db, db.begin():
                    user = await lock_actor(db, run.actor)
                    await assert_purpose(db, user, "AI")
                    if user.data_version != run.data_version:
                        raise DomainError(409, "CONTEXT_CHANGED", "Quyền hoặc dữ liệu đã thay đổi.")
                    await db.execute(
                        update(AiRun)
                        .where(AiRun.id == run.id, AiRun.status == "running")
                        .values(status="completed", version=2)
                    )
                # Do not publish tokens/JSON before output and live policy have both passed.
                self.check_capacity(
                    run.conversation_id,
                    len(output.model_dump_json().encode()) + len(output.text.encode()) + 1024,
                )
                c.messages.append(
                    AIMessage(id=uuid4(), actor="bot", text=output.text, cards=output.cards)
                )
                c.version += 1
                self.event(run, "final", output.model_dump(mode="json", by_alias=True))
                self.event(run, "completed", {})
                status = "completed"
        except asyncio.CancelledError:
            status = "cancelled"
        except Exception:
            status = "failed"
        finally:
            await asyncio.shield(self.finalize(run, status))
