"""Incident tools: read the case, propose a timeline event, save only what the user approved.

The model never writes. ``propose_case_event`` stores an immutable server-side proposal;
``save_confirmed_event`` takes nothing but a ``proposal_id`` and its approval preview is read
from the stored proposal, so the user approves exactly what will be written.
"""

from typing import Any, Final, Literal
from uuid import UUID, uuid4

from agents import RunContextWrapper
from safevoice_shared.contracts.agent import ToolPolicy
from safevoice_shared.contracts.errors import NotFound
from safevoice_shared.contracts.incidents import CaseQuery, EventCreate

from safevoice_agent.tools.context import CompanionToolContext
from safevoice_agent.tools.proposals import payload_sha256
from safevoice_agent.tools.registry import ToolSpec
from safevoice_agent.tools.saving import save_approved, stored_preview

DESCRIPTION_MAX: Final = 500
RATIONALE_MAX: Final = 200
INFERRED_MESSAGE: Final = (
    "Hãy hỏi người dùng xác nhận điều này trước; không đề xuất điều AI suy đoán."
)
LABEL_FOR_USER_REPORT: Final = "[người dùng kể]"


def _error(code: str, message: str | None = None, *, retryable: bool = False) -> dict[str, Any]:
    error: dict[str, Any] = {"code": code, "retryable": retryable}
    if message:
        error["message"] = message
    return {"error": error}


def _parse_uuid(value: str | None) -> UUID | None:
    try:
        return UUID(value) if value else None
    except (ValueError, AttributeError):
        return None


async def get_case_context(
    ctx: RunContextWrapper[CompanionToolContext], case_id: str | None = None
) -> dict[str, Any]:
    """Read one of the user's own cases (summary, timeline, evidence list, plan progress)."""
    context = ctx.context
    services = context.services
    target = _parse_uuid(case_id)
    if case_id and target is None:
        return _error("not_found")
    try:
        if target is None:
            page = await services.incidents.list_cases(context.auth, CaseQuery(limit=5))
            return {
                "cases": [
                    {"id": str(c.id), "title": c.title, "status": c.status} for c in page.items
                ],
                "note": "Hãy hỏi người dùng muốn xem hồ sơ nào.",
            }
        case = await services.incidents.get_case(context.auth, target)
        evidence = await services.evidence.list_for_case(context.auth, target)
    except NotFound:
        return _error("not_found")
    return {
        "id": str(case.id),
        "title": case.title,
        "status": case.status,
        "perspective": case.perspective,
        "version": case.version,
        "userReported": {
            "label": LABEL_FOR_USER_REPORT,
            "summary": case.summary[:600],
            "people": case.people,
            "place": case.place,
            "occurredAt": case.occurred_at,
        },
        "categoryTags": list(case.category_tags),
        "events": [
            {
                "when": e.when,
                "precision": e.time_precision,
                "place": e.place,
                "description": e.description[:240],
                "provenance": e.provenance,
                "needsReview": e.needs_review,
                "evidenceCount": len(e.evidence_ids),
            }
            for e in case.events[:20]
        ],
        # Metadata only: never the stored text or file content.
        "evidence": [
            {
                "id": str(item.id),
                "kind": item.kind,
                "filename": item.original_filename,
                "reviewStatus": item.review_status,
                "hasUserEditedText": item.user_edited_text is not None,
            }
            for item in evidence
        ],
        "plan": (
            {"done": case.plan_progress.done, "total": case.plan_progress.total}
            if case.plan_progress
            else None
        ),
    }


async def propose_case_event(
    ctx: RunContextWrapper[CompanionToolContext],
    case_id: str,
    description: str,
    basis: Literal["user_stated", "evidence_shows", "inferred"],
    rationale: str,
    when: str = "",
    time_precision: Literal["exact", "day", "week", "unknown"] = "unknown",
    place: str = "",
    evidence_ids: list[str] | None = None,
) -> dict[str, Any]:
    """Draft a timeline event for review; this does not save the event.

    Args:
        case_id: Copy the exact case UUID from context or get_case_context; never reconstruct it.
        when: For exact precision, a timezone-aware ISO datetime with T and an explicit
            offset, e.g. 2026-11-09T10:00:00+07:00. For day/week, YYYY-MM-DD.
            For unknown, an empty string. Never guess an offset or AM/PM; ask the
            user or use only the date if that is all they know.
        time_precision: Match the user's actual certainty, not the desired display format.
    """
    context = ctx.context
    deps = context.deps
    if deps.proposals is None:
        return _error("unavailable", retryable=False)
    if basis == "inferred":
        return _error("basis_not_allowed", INFERRED_MESSAGE)
    description, rationale, place = description.strip(), rationale.strip(), place.strip()
    if not 1 <= len(description) <= DESCRIPTION_MAX:
        return _error("invalid_description", f"Mô tả cần từ 1 đến {DESCRIPTION_MAX} ký tự.")
    if len(rationale) > RATIONALE_MAX or len(place) > 200:
        return _error("invalid_field", "Lý do hoặc nơi xảy ra quá dài.")
    target = _parse_uuid(case_id)
    if target is None:
        return _error("not_found")
    parsed_evidence: list[UUID] = []
    for raw in evidence_ids or []:
        item_id = _parse_uuid(raw)
        if item_id is None:
            return _error("not_found")
        parsed_evidence.append(item_id)
    if time_precision == "unknown":
        when = ""  # never invent a date: unknown precision means no date at all
    try:
        # Reuse the domain validator so the proposal can only contain a savable event.
        EventCreate(
            id=uuid4(),
            when=when,
            time_precision=time_precision,
            place=place,
            description=description,
            provenance="user_confirmed",
            evidence_ids=parsed_evidence,
        )
    except ValueError:
        return _error(
            "invalid_time",
            "Ngày giờ không khớp mức chính xác: exact cần timezone-aware ISO datetime "
            "(YYYY-MM-DDTHH:MM:SS+hh:mm); day/week dùng YYYY-MM-DD; unknown dùng chuỗi rỗng. "
            "Không tự đoán múi giờ hoặc sáng/tối; hãy hỏi người dùng khi chưa rõ.",
        )
    try:
        case = await context.services.incidents.get_case(context.auth, target)
        names: list[str] = []
        for item_id in parsed_evidence:
            meta = await context.services.evidence.get(context.auth, item_id)
            if meta.upload_status != "uploaded":
                return _error("evidence_not_ready")
            names.append(meta.original_filename or "ghi chú")
    except NotFound:
        return _error("not_found")
    if context.tool_call_id is None:
        return _error("internal", retryable=False)
    payload: dict[str, Any] = {
        "case_id": str(target),
        "event": {
            "when": when,
            "time_precision": time_precision,
            "place": place,
            "description": description,
            "evidence_ids": [str(i) for i in parsed_evidence],
            "basis": basis,
        },
        "rationale": rationale,
    }
    when_label = when if when else "chưa rõ ngày"
    preview: dict[str, Any] = {
        "kind": "case_event",
        "summary": f"Thêm mốc: {when_label} · {place or 'chưa rõ nơi'} · {description}",
        "when": when_label,
        "place": place,
        "description": description,
        "evidence": names,
        "rationale": rationale,
    }
    try:
        stored = await deps.proposals.create(
            context.auth,
            conversation_id=context.conversation_id,
            run_id=context.run_id,
            kind="case_event",
            target_case_id=target,
            payload=payload,
            preview=preview,
            base_version=case.version,
            request_key=context.tool_call_id,
        )
    except NotFound:
        return _error("not_found")
    if stored.payload_sha256 != payload_sha256(payload):
        # Same request key with different content must never silently reuse the old proposal.
        return _error("request_conflict", retryable=False)
    context.scratch.proposals[str(stored.id)] = "case_event"
    return {
        "proposalId": str(stored.id),
        "status": "proposed",
        "preview": stored.preview,
        "expiresAt": stored.expires_at.isoformat(),
        "note": "Đây là đề xuất CHƯA LƯU. Hãy hỏi người dùng trước khi gọi save_confirmed_event.",
    }


async def _event_preview(ctx: Any, arguments: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(ctx, CompanionToolContext):
        return {}
    return await stored_preview(ctx, arguments, "case_event")


async def save_confirmed_event(
    ctx: RunContextWrapper[CompanionToolContext], proposal_id: str
) -> dict[str, Any]:
    """Save the approved event proposal. The only parameter is the proposal id."""
    context = ctx.context
    return await save_approved(context, proposal_id, "case_event", context.deps.events)


def incident_tools() -> list[ToolSpec]:
    return [
        ToolSpec(
            get_case_context,
            ToolPolicy("get_case_context", "1", "read", False, 8, 2),
            "Xem hồ sơ của bạn",
        ),
        ToolSpec(
            propose_case_event,
            ToolPolicy("propose_case_event", "2", "prepare", False, 8, 3),
            "Soạn một mốc cho dòng thời gian",
        ),
        ToolSpec(
            save_confirmed_event,
            ToolPolicy("save_confirmed_event", "1", "write", True, 15, 2),
            "Lưu mốc vào hồ sơ",
            async_preview=_event_preview,
        ),
    ]
