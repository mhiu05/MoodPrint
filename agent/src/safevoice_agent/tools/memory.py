"""propose_memory: the model can only create a *candidate*; the user approves it in the UI."""

from typing import Any, Final, Literal

from agents import RunContextWrapper
from safevoice_shared.contracts.agent import ToolPolicy
from safevoice_shared.contracts.memory import MemoryCandidateCreate

from safevoice_agent.memory.validation import validate_candidate
from safevoice_agent.tools.context import CompanionToolContext
from safevoice_agent.tools.registry import ToolSpec
from safevoice_agent.tools.saving import error

REJECTION_HINTS: Final[dict[str, str]] = {
    "empty_after_trim": "Nội dung trống.",
    "too_long": "Nội dung quá dài; chỉ ghi một ý ngắn.",
    "contains_contact": "Không ghi email, số điện thoại hay liên kết.",
    "contains_name": "Không ghi tên người; chỉ ghi vai trò (ví dụ 'cô chủ nhiệm').",
    "incident_content": "Không ghi chuyện sự việc; ký ức chỉ cho sở thích và mục tiêu bền vững.",
    "category_mismatch": "Người hỗ trợ phải là vai trò, không phải tên.",
}


async def propose_memory(
    ctx: RunContextWrapper[CompanionToolContext],
    category: Literal["preference", "communication", "support_person", "goal", "context"],
    content: str,
) -> dict[str, Any]:
    """Suggest something worth remembering. The user decides in a separate screen."""
    context = ctx.context
    if context.scratch.memory_candidates >= context.memory_candidates_max:
        return error("candidate_limit", "Mỗi lượt chỉ gợi ý một điều cần ghi nhớ.")
    reason = validate_candidate(category, content)
    if reason is not None:
        return {"status": "rejected", "reason": reason, "hint": REJECTION_HINTS[reason]}
    candidate = await context.services.memory.propose(
        context.auth,
        MemoryCandidateCreate(
            category=category,
            content=content.strip(),
            source_kind="agent_proposed",
            source_conversation_id=context.conversation_id,
        ),
    )
    context.scratch.memory_candidates += 1
    return {
        "status": "proposed",
        "candidateId": str(candidate.id),
        "note": "Đây chỉ là gợi ý; người dùng sẽ tự duyệt. Chưa có gì được ghi nhớ.",
    }


def memory_tools() -> list[ToolSpec]:
    return [
        ToolSpec(
            propose_memory,
            ToolPolicy("propose_memory", "1", "prepare", False, 8, 1),
            "Gợi ý ghi nhớ",
        )
    ]
