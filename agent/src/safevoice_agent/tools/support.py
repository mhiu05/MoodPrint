"""Support tools. They only read static data or compose text; nothing can be sent anywhere."""

import re
from typing import Any, Final, Literal

from agents import RunContextWrapper
from safevoice_shared.contracts.agent import ToolPolicy

from safevoice_agent.tools.context import CompanionToolContext
from safevoice_agent.tools.registry import ToolSpec
from safevoice_agent.tools.saving import error
from safevoice_agent.tools.support_data import DIRECTORY, RECIPIENT_ROLES, VERIFIED_ON

_URL: Final = re.compile(r"(?:https?://|www\.)\S+", re.IGNORECASE)
_PHONE: Final = re.compile(r"(?<!\w)\+?\d[\d .-]{6,}\d(?!\w)")
MAX_POINTS: Final = 5
POINT_MAX: Final = 200
DRAFT_NOTICE: Final = (
    "Đây là bản nháp để bạn tự xem lại, sửa và tự gửi. SafeVoice không gửi tin nhắn này "
    "và không liên hệ ai thay bạn."
)


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", _PHONE.sub(" ", _URL.sub(" ", text))).strip()


async def support_directory(
    ctx: RunContextWrapper[CompanionToolContext],
    kind: Literal["urgent", "school", "family", "online"],
) -> dict[str, Any]:
    """List verified places to get help. Only entries with a source carry a phone number."""
    entries = DIRECTORY.get(kind)
    if entries is None:
        return error("unknown_kind")
    return {"kind": kind, "verifiedOn": VERIFIED_ON, "entries": entries}


async def draft_support_message(
    ctx: RunContextWrapper[CompanionToolContext],
    recipient_role: Literal["teacher", "parent", "trusted_adult", "counselor"],
    purpose: str,
    key_points: list[str],
) -> dict[str, Any]:
    """Compose a draft the user can edit and send themselves. This tool cannot send anything."""
    greeting_closing = RECIPIENT_ROLES.get(recipient_role)
    if greeting_closing is None:
        return error("unknown_recipient")
    purpose = _clean(purpose)[:POINT_MAX]
    points = [p for p in (_clean(point)[:POINT_MAX] for point in key_points) if p][:MAX_POINTS]
    if not purpose or not points:
        return error("missing_content", "Cần nêu mục đích và ít nhất một ý chính.")
    greeting, closing = greeting_closing
    body = "\n".join(f"- {point}" for point in points)
    draft = (
        f"{greeting}\n\nEm muốn nhờ giúp đỡ về việc sau: {purpose}\n\n{body}\n\n"
        f"Em mong cô/thầy/bố/mẹ có thể cùng em tìm cách xử lý. {closing}"
    )
    return {"draft": draft, "notice": DRAFT_NOTICE, "sent": False}


def support_tools() -> list[ToolSpec]:
    return [
        ToolSpec(
            support_directory,
            ToolPolicy("support_directory", "1", "read", False, 3, 1),
            "Xem nơi hỗ trợ",
        ),
        ToolSpec(
            draft_support_message,
            ToolPolicy("draft_support_message", "1", "prepare", False, 8, 1),
            "Soạn tin nhắn nhờ hỗ trợ",
        ),
    ]
