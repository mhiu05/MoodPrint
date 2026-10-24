"""Idempotent metadata accounting. Unknown provider usage is never refunded or invented."""

from dataclasses import dataclass
from datetime import timedelta
from uuid import UUID

from sqlalchemy import case, func, select, update

from app.ai.usage import UsageEvent
from app.infrastructure.database.models import AiRun, AiUsage, now

PRICING_VERSION = "openai-standard-2026-10-24"
# Integer nano-USD/token, short context. Source recorded in live-ai/README.md.
RATES = {"gpt-6-luna": (100, 10, 500)}
LEASE_SECONDS = 45


@dataclass
class UsageSnapshot:
    sequence: int = 0
    requests_started: int = 0
    responses_received: int = 0
    input_tokens: int = 0
    cached_input_tokens: int = 0
    output_tokens: int = 0
    tool_calls: int = 0

    def observe(self, event: UsageEvent):
        if min(event.input_tokens, event.cached_input_tokens, event.output_tokens) < 0 or event.cached_input_tokens > event.input_tokens:
            raise ValueError("Invalid provider usage")
        self.sequence += 1
        self.requests_started += event.kind == "request_started"
        self.responses_received += event.kind == "response_received"
        self.input_tokens += event.input_tokens
        self.cached_input_tokens += event.cached_input_tokens
        self.output_tokens += event.output_tokens
        self.tool_calls += event.kind == "tool_started"


async def reserve_accounting(db, run_id: UUID, user_id: UUID, worker_id: UUID, model: str, prompt_version: str):
    rates = RATES.get(model)
    db.add(AiUsage(run_id=run_id, user_id=user_id, worker_id=worker_id,
                   model=model, prompt_version=prompt_version, pricing_version=PRICING_VERSION,
                   input_nano_rate=rates[0] if rates else None,
                   cached_nano_rate=rates[1] if rates else None,
                   output_nano_rate=rates[2] if rates else None,
                   lease_until=now() + timedelta(seconds=LEASE_SECONDS)))
    await db.flush()


async def persist_snapshot(db, run_id: UUID, worker_id: UUID, snapshot: UsageSnapshot, *, terminal: bool = False) -> bool:
    row = await db.scalar(select(AiUsage).where(
        AiUsage.run_id == run_id, AiUsage.worker_id == worker_id,
        AiUsage.lease_until > func.now(),
    ).with_for_update())
    if row is None or snapshot.sequence < row.sequence:
        return False
    state = ("uncertain" if snapshot.requests_started != snapshot.responses_received else "settled") if terminal else "open"
    if row.state != "open":
        return row.sequence == snapshot.sequence and row.state == state
    if any(getattr(snapshot, field) < getattr(row, field) for field in (
        "requests_started", "responses_received", "input_tokens", "cached_input_tokens", "output_tokens", "tool_calls",
    )):
        return False
    for field in ("sequence", "requests_started", "responses_received", "input_tokens", "cached_input_tokens", "output_tokens", "tool_calls"):
        setattr(row, field, getattr(snapshot, field))
    row.state = state
    row.lease_until = now() + timedelta(seconds=LEASE_SECONDS)
    input_rate, cached_rate, output_rate = row.input_nano_rate, row.cached_nano_rate, row.output_nano_rate
    if input_rate is not None and cached_rate is not None and output_rate is not None:
        row.estimated_nano_usd = ((snapshot.input_tokens - snapshot.cached_input_tokens) * input_rate
                                  + snapshot.cached_input_tokens * cached_rate
                                  + snapshot.output_tokens * output_rate)
    await db.flush()
    return True


async def recover_expired(db):
    # Never replay a provider call or touch another worker's unexpired lease.
    # Keep the same usage → run lock order as terminal settlement.
    expired = (await db.scalars(select(AiUsage.run_id).where(
        AiUsage.state == "open", AiUsage.lease_until <= func.now(),
    ).order_by(AiUsage.run_id).limit(1000).with_for_update(skip_locked=True))).all()
    if not expired:
        return
    await db.execute(update(AiRun).where(AiRun.status == "running", AiRun.id.in_(expired)).values(status="interrupted", version=2))
    await db.execute(update(AiUsage).where(AiUsage.state == "open", AiUsage.run_id.in_(expired)).values(
        state=case((AiUsage.requests_started == AiUsage.responses_received, "settled"), else_="uncertain"),
    ))
