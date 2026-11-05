"""A child token ledger plus a separate hosted-tool fee; all I/O outside transactions."""

import asyncio
import time
from uuid import uuid4

from app.ai.accounting import UsageSnapshot, persist_snapshot, reserve_accounting
from app.ai.search.accounting import WEB_FEE_NANO, claim
from app.ai.search.models import AiSearchUsage
from app.ai.search.schemas import WebSearchResult
from app.ai.search.web import WebSearchAdapter
from app.ai.usage import UsageEvent
from app.core.errors import DomainError
from app.core.security import assert_purpose, lock_actor
from app.infrastructure.database.models import AiRun, AiUsage, now


class WebSearchService:
    def __init__(self, runtime):
        self.runtime = runtime

    async def search(self, query: str, run) -> WebSearchResult:
        runtime, settings = self.runtime, self.runtime.settings
        if settings.ai_dispatch_gate_enabled:
            # Hosted search has its own HTTP path and fee semantics. Until it shares
            # the post-queue authority fence, never bypass the candidate model gate.
            raise DomainError(503, "AI_DISPATCH_UNSUPPORTED", "Tìm kiếm web chưa khả dụng với cấu hình hàng đợi thử nghiệm.", True)
        remaining = min(30, settings.ai_timeout_seconds) - (time.monotonic() - run.started)
        if remaining < 20:
            return WebSearchResult(status="unavailable")
        await runtime.check(run)
        child_id, snapshot = uuid4(), UsageSnapshot()
        async with runtime.database.require()() as db, db.begin():
            user = await lock_actor(db, run.actor)
            await assert_purpose(db, user, "AI")
            operation = await claim(db, settings, user, run.id, "openai_web")
            operation.token_liability_nano_usd = 0  # child reservation below is authority, atomically.
            db.add(AiRun(id=child_id, user_id=user.id, conversation_id=None,
                         bot_id=run.responder or runtime.store.conversations[run.conversation_id].bot_id,
                         origin="agent", parent_run_id=run.id))
            await db.flush()
            await reserve_accounting(db, child_id, user.id, runtime.worker_id, settings.openai_model,
                                     "isolated-web-v1", settings=settings)
            operation.child_run_id = child_id
            operation.token_liability_nano_usd = 2_000_000_000
            operation_id = operation.id
        result, dispatched = None, False
        try:
            await runtime.check(run)
            async with runtime.database.require()() as db, db.begin():
                user = await lock_actor(db, run.actor)
                await assert_purpose(db, user, "AI")
                if user.data_version != run.data_version:
                    raise ValueError("context changed")
                operation = await db.get(AiSearchUsage, operation_id)
                operation.state = "dispatched"
                snapshot.observe(UsageEvent("request_started"))
                await persist_snapshot(db, child_id, runtime.worker_id, snapshot)
            dispatched = True
            # Only a test HTTP/SDK boundary may be replaced, never supplied by a browser.
            adapter = getattr(runtime, "web_search_adapter", None)
            if adapter is None:
                client = runtime.provider._openai(settings.openai_api_key.get_secret_value())
                adapter = WebSearchAdapter(client.responses.create, settings.openai_model)
            result = await adapter.search(query, timeout_seconds=min(12, remaining - 8))
            snapshot.observe(UsageEvent("response_received", input_tokens=result.input_tokens,
                cached_input_tokens=result.cached_input_tokens, output_tokens=result.output_tokens))
            await runtime.check(run)
            return result
        finally:
            async def settle():
                async with runtime.database.require()() as db, db.begin():
                    await persist_snapshot(db, child_id, runtime.worker_id, snapshot, terminal=True)
                    operation = await db.get(AiSearchUsage, operation_id)
                    usage = await db.get(AiUsage, child_id)
                    if operation:
                        operation.state = "settled" if result is not None or not dispatched else "uncertain"
                        operation.actual_nano_usd = result.calls * WEB_FEE_NANO if result is not None else 0 if not dispatched else None
                        operation.call_count = result.calls if result is not None else int(dispatched)
                        operation.token_liability_nano_usd = usage.estimated_nano_usd if usage else operation.token_liability_nano_usd
                        operation.tokens_uncertain = usage.state != "settled" if usage else True
                        operation.active = False
                        operation.updated_at = now()
                    child = await db.get(AiRun, child_id)
                    if child:
                        child.status = "completed" if result is not None else "interrupted"
                        child.version = 2
            task = asyncio.create_task(settle())
            while not task.done():
                try:
                    await asyncio.shield(task)
                except asyncio.CancelledError:
                    continue
            task.result()
