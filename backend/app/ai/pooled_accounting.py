"""Transfer bounded V3 child allocations under the existing admission transaction lock.

No new financial authority: AiUsage remains the durable hold. The parent's remaining
hold plus its children is conserved; settled children never replenish that hold.
Only the opt-in 64k envelope can use this path. Legacy and guest holds are unchanged.
"""

from sqlalchemy import func, select

from app.ai.envelope import BOUNDED_RESERVATION_NANO
from app.core.errors import DomainError
from app.infrastructure.database.models import AiRun, AiUsage

POOL_ROOT_VERSION = "openai-conservative-64k-pool-root-v1"
POOL_CALL_VERSION = "openai-conservative-64k-pool-call-v1"
POOL_HANDOFF_VERSION = "openai-conservative-64k-pool-handoff-v1"
POOL_VERSIONS = (POOL_ROOT_VERSION, POOL_CALL_VERSION, POOL_HANDOFF_VERSION)
CALL_HOLD = BOUNDED_RESERVATION_NANO // 3
WORKFLOW_HOLD = 7 * CALL_HOLD
CHILD_CALLS = {
    "plan-planner+orchestration-v1": 1,
    "consult-nhatky+orchestration-v1": 1,
    "consult-hoatdong+orchestration-v1": 1,
    "handoff-nhatky+orchestration-v1": 3,
    "handoff-hoatdong+orchestration-v1": 3,
}


def unavailable():
    return DomainError(503, "AI_BUDGET_UNAVAILABLE", "Chưa xác minh được giới hạn chi phí AI. Vui lòng thử lại sau.", True)


async def allocation(db, run, user_id, worker_id, model, prompt_version):
    """Return a planned transfer; caller checks global liability before mutating it."""
    if run is None:
        raise unavailable()
    if run.parent_run_id is None:
        if run.origin == "user" and run.bot_id == "dieuphoi":
            return WORKFLOW_HOLD, POOL_ROOT_VERSION, None
        return None
    parent = await db.scalar(select(AiUsage).where(
        AiUsage.run_id == run.parent_run_id,
    ).with_for_update().execution_options(populate_existing=True))
    if parent is None or parent.pricing_version not in POOL_VERSIONS:
        return None
    parent_run = await db.get(AiRun, run.parent_run_id)
    calls = CHILD_CALLS.get(prompt_version)
    at = await db.scalar(select(func.clock_timestamp()))
    if (parent.pricing_version != POOL_ROOT_VERSION or parent.state != "open"
            or parent.worker_id != worker_id or parent.user_id != user_id
            or parent.model != model or parent.lease_until <= at
            or parent_run is None or parent_run.status != "running"
            or run.origin != "agent" or calls is None
            or parent.estimated_nano_usd is None
            or parent.estimated_nano_usd - calls * CALL_HOLD < BOUNDED_RESERVATION_NANO):
        raise unavailable()
    return calls * CALL_HOLD, POOL_CALL_VERSION if calls == 1 else POOL_HANDOFF_VERSION, parent
