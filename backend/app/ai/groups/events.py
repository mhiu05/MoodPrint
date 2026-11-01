"""SSE ``ai-group-events-v1`` (06 §5): a pure, forward-only function of database state.

Speakers run one after another and every receipt only moves forward, so the event list of a
turn only ever grows at its end: a reconnect with ``afterSeq`` never misses or repeats an event.
Only committed bubbles appear; nothing speculative or unvalidated is ever sent.
"""

from typing import Any, Literal

from pydantic import Field

from app.contracts import DTO

GroupEventType = Literal[
    "turn_started", "agent_selected", "agent_started", "agent_message", "agent_failed",
    "turn_completed", "turn_failed", "turn_cancelled",
]
MAX_EVENTS = 1 + 3 + 3 * 2 + 1


class GroupEvent(DTO):
    version: Literal["ai-group-events-v1"] = "ai-group-events-v1"
    seq: str = Field(pattern=r"^[1-9][0-9]*$")
    type: GroupEventType
    data: dict


def group_events(turn, steps, bubbles: dict[Any, list]) -> list[GroupEvent]:
    """``turn`` is the turn's ai_runs row, ``steps`` its receipts, ``bubbles`` child run → messages."""
    items: list[tuple[str, dict]] = [("turn_started", {"turnId": str(turn.id)})]
    selection = next((step for step in steps if step.kind == "group_select" and step.status != "authorized"), None)
    speakers: list[str] = list((selection.detail or {}).get("speakers", [])) if selection is not None else []
    for ordinal, agent in enumerate(speakers):
        items.append(("agent_selected", {"agent": agent, "ordinal": ordinal}))
    replies = {step.ordinal: step for step in steps if step.kind == "group_reply"}
    for ordinal, agent in enumerate(speakers):
        step = replies.get(ordinal)
        if step is None:
            break
        if step.status == "denied":
            items.append(("agent_failed", {"agent": agent, "ordinal": ordinal, "code": "not_member"}))
            continue
        items.append(("agent_started", {"agent": agent, "ordinal": ordinal}))
        if step.status == "authorized":
            break
        if step.status == "completed" and step.used_in_reply:
            items.append(("agent_message", {"agent": agent, "ordinal": ordinal, "messages": [
                {"messageId": str(m.id), "partIndex": m.part_index, "text": m.text, "cards": m.cards}
                for m in bubbles.get(step.child_run_id, [])
            ]}))
        else:
            items.append(("agent_failed", {"agent": agent, "ordinal": ordinal,
                                           "code": step.failure_code or step.status}))
    if turn.status != "running":
        if turn.status == "completed":
            items.append(("turn_completed", {}))
        elif turn.status == "cancelled":
            items.append(("turn_cancelled", {}))
        else:
            items.append(("turn_failed", {"code": "AI_INTERRUPTED" if turn.status == "interrupted" else "AI_RUN_FAILED",
                                          "message": "Lượt trò chuyện chưa hoàn tất. Bạn có thể gửi lại."}))
    return [GroupEvent(seq=str(index + 1), type=kind, data=data) for index, (kind, data) in enumerate(items)]  # type: ignore[arg-type]
