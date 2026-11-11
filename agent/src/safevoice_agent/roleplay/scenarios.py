"""The six practice scenarios. Synthetic situations only; no real person or school is named."""

from dataclasses import dataclass
from typing import Final, Literal

Role = Literal["teacher", "parent", "trusted_adult"]
CONTEXT_MAX: Final = 800
GOAL_MAX: Final = 300


@dataclass(frozen=True, slots=True)
class Scenario:
    key: str
    role: Role
    title: str
    context: str
    default_goal: str


SCENARIOS: Final[tuple[Scenario, ...]] = (
    Scenario(
        "teacher-group-chat",
        "teacher",
        "Báo với giáo viên chủ nhiệm về nhóm chat lớp",
        "Nhóm chat của lớp có vài tin nhắn đe dọa và chế giễu một bạn. Bạn muốn nói với giáo "
        "viên chủ nhiệm trong giờ ra chơi.",
        "Mô tả sự việc rõ ràng và xin một hỗ trợ cụ thể.",
    ),
    Scenario(
        "teacher-exclusion",
        "teacher",
        "Nói với giáo viên bộ môn về việc bị cô lập trong nhóm",
        "Trong hoạt động nhóm của môn học, vài bạn cố tình không cho bạn tham gia và không "
        "chia việc cho bạn.",
        "Nêu điều bạn cần và đề xuất một cách xử lý.",
    ),
    Scenario(
        "parent-first-talk",
        "parent",
        "Lần đầu kể với bố/mẹ",
        "Bạn muốn kể với bố hoặc mẹ về chuyện đang xảy ra trên mạng nhưng sợ bị cấm điện thoại.",
        "Mở lời được và giữ bình tĩnh trong lúc nói.",
    ),
    Scenario(
        "parent-evidence",
        "parent",
        "Cho bố/mẹ xem ảnh chụp màn hình",
        "Bạn cho bố hoặc mẹ xem vài ảnh chụp màn hình. Họ rất lo lắng và muốn xử lý ngay lập "
        "tức, kể cả nhắn thẳng cho phụ huynh khác.",
        "Đề nghị cùng bàn bước tiếp theo, không hành động nóng vội.",
    ),
    Scenario(
        "trusted-adult-opening",
        "trusted_adult",
        "Mở lời với một người lớn đáng tin",
        "Bạn gặp một người lớn mà bạn tin tưởng (huấn luyện viên, anh chị lớn hoặc cô chú) và "
        "muốn nhờ họ giúp.",
        "Nói rõ điều mình cần ở người đó.",
    ),
    Scenario(
        "trusted-adult-accompany",
        "trusted_adult",
        "Nhờ người lớn đi cùng gặp nhà trường",
        "Bạn muốn nhờ một người lớn đáng tin đi cùng bạn gặp nhà trường để nói về sự việc.",
        "Nhờ giúp một cách cụ thể và thống nhất kế hoạch.",
    ),
)

_BY_KEY: Final = {scenario.key: scenario for scenario in SCENARIOS}

PERSONAS: Final[dict[Role, str]] = {
    "teacher": "một giáo viên ở trường của người dùng, quan tâm nhưng có nhiều việc phải làm",
    "parent": "bố hoặc mẹ của người dùng, thương con và dễ lo lắng",
    "trusted_adult": "một người lớn đáng tin của người dùng (huấn luyện viên, anh chị lớn, cô chú)",
}


def scenario_for(key: str) -> Scenario | None:
    return _BY_KEY.get(key)
