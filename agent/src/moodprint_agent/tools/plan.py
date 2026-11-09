"""Action-plan tools: read the plan, propose a validated revision, save only what is approved.

Reads never change anything and there is no tool that ticks an item (the user does that in the
app). Revisions keep the id, status and notes of items whose label already exists, so progress
is never lost, and the proposal records the plan version it was based on.
"""

import re
from typing import Any, Final, Literal
from uuid import UUID, uuid5

from agents import RunContextWrapper
from moodprint_shared.contracts.agent import ToolPolicy
from moodprint_shared.contracts.errors import NotFound
from moodprint_shared.contracts.plans import PlanItem, PlanUpsert
from pydantic import BaseModel, ConfigDict

from moodprint_agent.tools.context import CompanionToolContext
from moodprint_agent.tools.proposals import payload_sha256
from moodprint_agent.tools.registry import ToolSpec
from moodprint_agent.tools.saving import error, parse_uuid, save_approved, stored_preview

MAX_ITEMS: Final = 8
MAX_HIGH: Final = 3
LABEL_MAX: Final = 140
GOAL_MAX: Final = 200
PLAN_NAMESPACE: Final = UUID("6f1c9c1e-6d0b-4d9a-9a52-4d6f6f6f7002")
# Steps the Companion must never recommend, whatever the model proposes.
_UNSAFE_STEP: Final = re.compile(
    r"đối\s*đầu|trả\s*đũa|tự\s*(?:đi\s*)?điều\s*tra|"
    r"tự\s*(?:đi\s*)?tìm\s*(?:ra\s*)?(?:người|ai\b|danh\s*tính|tài\s*khoản)|đánh\s*lại|"
    # Meeting the person who hurts you alone is unsafe; meeting a teacher or parent privately is the plan.
    r"hẹn\s*(?:gặp\s*)?(?:riêng\s*)?(?:với\s*)?(?:bạn\s*ấy|bạn\s*đó|người\s*(?:đó|kia|bắt\s*nạt)|nhóm\s*(?:đó|kia))|"
    r"moodprint\s*(?:sẽ|đã)\s*(?:liên\s*hệ|gửi|báo)|"
    # Retaliation, even when phrased as "reply" ("nhắn tin dọa lại", "chửi lại").
    r"(?:dọa|đe\s*dọa|chửi|mắng|nói\s*xấu|nhắn\s*tin\s*(?:dọa|chửi|mắng))\s*(?:lại|trả|bạn\s*(?:ấy|đó)|họ)|"
    # Going alone to the person or group, to their home, blocking their way or following them.
    r"tự\s*(?:mình\s*)?(?:đến|tới|đi\s*gặp|gặp)\s*(?:nhà\s*)?(?:bạn\s*(?:ấy|đó)|người\s*(?:đó|kia)|nhóm\s*(?:đó|kia))|"
    r"gặp\s*(?:bạn\s*(?:ấy|đó)|người\s*(?:đó|kia)|nhóm\s*(?:đó|kia))\s*một\s*mình|"
    r"chặn\s*đường|đi\s*theo\s*(?:bạn\s*(?:ấy|đó)|người\s*(?:đó|kia)|nhóm\s*(?:đó|kia))|"
    r"theo\s*dõi\s*(?:bạn\s*(?:ấy|đó)|người\s*(?:đó|kia)|nhóm\s*(?:đó|kia))|"
    # Public shaming, organising others against someone, fake accounts, hunting for who did it.
    r"đăng\s*(?:công\s*khai\s*)?(?:tên|ảnh|thông\s*tin)\s*(?:của\s*)?(?:bạn\s*(?:ấy|đó)|người\s*(?:đó|kia))|"
    r"đăng\s*công\s*khai.{0,24}(?:tên|ảnh)\s*(?:của\s*)?(?:bạn\s*(?:ấy|đó))|"
    r"tẩy\s*chay|rủ\s*(?:bạn\s*bè\s*)?(?:cùng\s*)?(?:đánh|nói\s*xấu|tẩy\s*chay)|"
    r"(?:lập|tạo|dùng)\s*tài\s*khoản\s*(?:giả|ảo|phụ)|hỏi\s*cho\s*ra|truy\s*(?:tìm|lùng)",
    re.IGNORECASE,
)


class PlanItemIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    label: str
    priority: Literal["high", "normal"] = "normal"
    reason: str = ""


def _norm(label: str) -> str:
    return re.sub(r"\s+", " ", label.strip()).casefold()


async def get_action_plan(
    ctx: RunContextWrapper[CompanionToolContext], case_id: str
) -> dict[str, Any]:
    """Read the action plan of one of the user's cases (read only)."""
    context = ctx.context
    cid = parse_uuid(case_id)
    if cid is None:
        return error("not_found")
    try:
        await context.services.incidents.get_case(context.auth, cid)
        plan = await context.services.plans.get_for_case(context.auth, cid)
    except NotFound:
        return error("not_found")
    if plan is None:
        return {"exists": False}
    done = sum(1 for item in plan.items if item.status == "done")
    return {
        "exists": True,
        "version": plan.version,
        "goal": plan.goal,
        "status": plan.status,
        "items": [
            {
                "id": str(i.id),
                "label": i.label,
                "status": i.status,
                "priority": i.priority,
                "reason": i.reason,
            }
            for i in plan.items
        ],
        "progress": {"done": done, "total": len(plan.items)},
    }


async def propose_action_plan(
    ctx: RunContextWrapper[CompanionToolContext],
    case_id: str,
    goal: str,
    items: list[PlanItemIn],
    rationale: str,
    base_version: int | None = None,
) -> dict[str, Any]:
    """Draft a new or revised action plan for the user to review. Nothing is saved here."""
    context = ctx.context
    store = context.deps.proposals
    if store is None or context.tool_call_id is None:
        return error("unavailable")
    cid = parse_uuid(case_id)
    if cid is None:
        return error("not_found")
    goal, rationale = goal.strip(), rationale.strip()
    if not 1 <= len(goal) <= GOAL_MAX or len(rationale) > 200:
        return error("invalid_field", f"Mục tiêu cần 1–{GOAL_MAX} ký tự, lý do tối đa 200.")
    if not 1 <= len(items) <= MAX_ITEMS:
        return error("too_many_items", f"Kế hoạch cần 1–{MAX_ITEMS} bước; hãy rút gọn.")
    if sum(1 for i in items if i.priority == "high") > MAX_HIGH:
        return error("too_many_high", f"Tối đa {MAX_HIGH} bước ưu tiên cao; hãy chọn lại.")
    cleaned: list[PlanItemIn] = []
    seen: set[str] = set()
    for item in items:
        label, reason = re.sub(r"\s+", " ", item.label.strip()), item.reason.strip()
        if not label or len(label) > LABEL_MAX or len(reason) > LABEL_MAX:
            return error("invalid_item", f"Mỗi bước tối đa {LABEL_MAX} ký tự.")
        if _UNSAFE_STEP.search(label) or _UNSAFE_STEP.search(reason):
            return error(
                "unsafe_step", "Không đề xuất đối đầu, tự điều tra hay hứa MoodPrint liên hệ ai."
            )
        if _norm(label) in seen:
            return error("duplicate_item")
        seen.add(_norm(label))
        cleaned.append(PlanItemIn(label=label, priority=item.priority, reason=reason))
    try:
        await context.services.incidents.get_case(context.auth, cid)
        existing = await context.services.plans.get_for_case(context.auth, cid)
    except NotFound:
        return error("not_found")
    if existing is not None and base_version != existing.version:
        return {
            **error("version_conflict", "Kế hoạch đã thay đổi; hãy xem lại bản mới."),
            "latestVersion": existing.version,
        }
    previous = {_norm(i.label): i for i in (existing.items if existing else [])}
    ordered = sorted(enumerate(cleaned), key=lambda pair: (pair[1].priority != "high", pair[0]))
    plan_items: list[PlanItem] = []
    for _, item in ordered:
        old = previous.get(_norm(item.label))
        plan_items.append(
            PlanItem(
                id=old.id if old else uuid5(PLAN_NAMESPACE, f"{cid}:{_norm(item.label)}"),
                label=item.label,
                status=old.status if old else "not_started",
                notes=old.notes if old else "",
                priority=item.priority,
                reason=item.reason,
            )
        )
    status = (
        "draft"
        if existing is None
        else ("active" if existing.status == "completed" else existing.status)
    )
    upsert = PlanUpsert(
        id=existing.id if existing else uuid5(PLAN_NAMESPACE, f"plan:{cid}"),
        goal=goal,
        chosen_option_id="",
        status=status,
        items=plan_items,
    )
    payload: dict[str, Any] = {
        "case_id": str(cid),
        "plan": upsert.model_dump(mode="json"),
        "rationale": rationale,
    }
    preview: dict[str, Any] = {
        "kind": "action_plan",
        "summary": f"Kế hoạch: {goal}",
        "goal": goal,
        "steps": [
            {"label": i.label, "priority": i.priority, "reason": i.reason, "status": i.status}
            for i in plan_items
        ],
        "revision": existing is not None,
        "rationale": rationale,
    }
    stored = await store.create(
        context.auth,
        conversation_id=context.conversation_id,
        run_id=context.run_id,
        kind="action_plan",
        target_case_id=cid,
        payload=payload,
        preview=preview,
        base_version=existing.version if existing else None,
        request_key=context.tool_call_id,
    )
    if stored.payload_sha256 != payload_sha256(payload):
        return error("request_conflict")
    context.scratch.proposals[str(stored.id)] = "action_plan"
    return {
        "proposalId": str(stored.id),
        "status": "proposed",
        "preview": stored.preview,
        "expiresAt": stored.expires_at.isoformat(),
        "note": "Đây là đề xuất CHƯA LƯU. Hãy hỏi người dùng trước khi gọi save_plan.",
    }


async def _plan_preview(ctx: Any, arguments: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(ctx, CompanionToolContext):
        return {}
    return await stored_preview(ctx, arguments, "action_plan")


async def save_plan(
    ctx: RunContextWrapper[CompanionToolContext], proposal_id: str
) -> dict[str, Any]:
    """Save the approved plan proposal. The only parameter is the proposal id."""
    context = ctx.context
    return await save_approved(context, proposal_id, "action_plan", context.deps.plans)


def plan_tools() -> list[ToolSpec]:
    return [
        ToolSpec(
            get_action_plan,
            ToolPolicy("get_action_plan", "1", "read", False, 8, 2),
            "Xem kế hoạch",
        ),
        ToolSpec(
            propose_action_plan,
            ToolPolicy("propose_action_plan", "1", "prepare", False, 8, 2),
            "Soạn kế hoạch hành động",
        ),
        ToolSpec(
            save_plan,
            ToolPolicy("save_plan", "1", "write", True, 15, 2),
            "Lưu kế hoạch",
            async_preview=_plan_preview,
        ),
    ]
