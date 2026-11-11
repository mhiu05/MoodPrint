"""``analyze_evidence``: the only path by which an image can reach the model from chat.

The tool needs the user's explicit approval *before* it runs, because running it sends the image to
an AI model. The approval preview names the file only; the image bytes and the model's reading
never pass through this module's arguments, and the result handed back is text-only and labelled as
unverified.
"""

from typing import Any

from agents import RunContextWrapper
from safevoice_shared.contracts.agent import AgentToolContext, ToolPolicy
from safevoice_shared.contracts.errors import NotFound

from safevoice_agent.tools.context import CompanionToolContext
from safevoice_agent.tools.registry import ToolSpec
from safevoice_agent.tools.saving import error, parse_uuid

CONSENT_LINE = "Ảnh này sẽ được gửi tới mô hình AI để đọc. Bản gốc của bạn không bị thay đổi."


async def analyze_evidence(
    ctx: RunContextWrapper[CompanionToolContext], evidence_id: str
) -> dict[str, Any]:
    """Read an uploaded screenshot with the AI image reader (runs only after the user approves)."""
    context = ctx.context
    runner = context.deps.analysis
    target = parse_uuid(evidence_id)
    if runner is None:
        return error("unavailable")
    if target is None:
        return error("not_found")
    try:
        return await runner.analyze(context.auth, evidence_id=target, run_id=context.run_id)
    except NotFound:
        return error("not_found")


async def _preview(ctx: AgentToolContext, arguments: dict[str, Any]) -> dict[str, Any]:
    target = parse_uuid(arguments.get("evidence_id"))
    if target is None:
        return {}
    try:
        meta = await ctx.services.evidence.get(ctx.auth, target)
    except NotFound:
        return {}
    return {
        "kind": "evidence_analysis",
        "summary": f"Gửi ảnh “{meta.original_filename or 'ảnh'}” cho AI đọc",
        "filename": meta.original_filename,
        "size": meta.byte_size,
        "type": meta.stored_mime_type,
        "consent": CONSENT_LINE,
    }


def evidence_tools() -> list[ToolSpec]:
    return [
        ToolSpec(
            analyze_evidence,
            ToolPolicy("analyze_evidence", "1", "prepare", True, 60, 1),
            "Đọc ảnh bằng AI",
            async_preview=_preview,
        )
    ]
