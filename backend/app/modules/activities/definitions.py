"""Static, versioned activity definitions (DR-08, DR-09). No AI-generated content."""

from dataclasses import dataclass
from datetime import timedelta
from typing import Literal

Kind = Literal["icebreaker", "coop_quiz", "focus"]
KINDS: tuple[Kind, ...] = ("icebreaker", "coop_quiz", "focus")

FOCUS_PLANS = ((25, 5), (15, 3), (50, 10))
FOCUS_MAX_CYCLES = 4


@dataclass(frozen=True)
class Definition:
    kind: Kind
    version: str
    rounds: int | None
    invite_ttl: timedelta
    idle_ttl: timedelta | None
    title: str
    description: str
    estimated_minutes: int


DEFINITIONS: dict[str, Definition] = {
    "icebreaker": Definition(
        "icebreaker",
        "icebreaker-v1",
        3,
        timedelta(minutes=10),
        timedelta(hours=24),
        "Câu hỏi làm quen",
        "Ba câu hỏi nhẹ nhàng. Mỗi người tự trả lời, rồi cùng xem câu trả lời của nhau.",
        5,
    ),
    "coop_quiz": Definition(
        "coop_quiz",
        "coop_quiz-v1",
        5,
        timedelta(minutes=10),
        timedelta(hours=24),
        "Đố vui đồng đội",
        "Năm câu đố vui. Hai bạn cùng ghi điểm cho một đội, không thi với nhau.",
        7,
    ),
    "focus": Definition(
        "focus",
        "focus-v1",
        None,
        timedelta(minutes=10),
        None,
        "Cùng tập trung",
        "Cùng tập trung theo thời gian đã chọn. Hai bạn có thể tạm dừng hoặc kết thúc phiên.",
        30,
    ),
}
