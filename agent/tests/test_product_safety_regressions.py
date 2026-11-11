"""Development regressions found during product audit; never an independent safety set."""

import pytest
from safevoice_agent.tools.safety import assess_urgency


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Hồi trước chú họ có chạm vào vùng kín của mình. Chuyện đó đã qua lâu rồi.", "elevated"),
        ("Người đó đang sờ vào vùng kín của em, em sợ.", "immediate"),
        ("Chú không chạm vào vùng kín của mình.", "none"),
        ("Nếu ai chạm vào vùng kín của mình thì báo với ai?", "none"),
        ("Em muốn hiểu cách ngăn người khác chạm vào vùng kín của mình.", "none"),
        ("Trong phim, người đó chạm vào vùng kín của mình.", "none"),
        ("Mình chạm vào vùng kín của mình để vệ sinh khi tắm.", "none"),
        ("Em tự chạm vào vùng kín của em khi tắm.", "none"),
        ("Bác sĩ chạm vào vùng kín của em để khám bệnh, em đã đồng ý.", "none"),
        ("Có người chạm vào vùng kín của em.", "immediate"),
        ("Em bị ngứa nên tự chạm vào vùng kín của em khi tắm.", "none"),
        ("Em bị ngứa nên chạm vào vùng kín của em.", "none"),
        ("Em bị người ta chạm vào vùng kín của em.", "immediate"),
    ],
)
def test_intimate_contact_disclosure_keeps_time_and_non_disclosure_context(
    text: str, expected: str
) -> None:
    assert assess_urgency(text).level == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (
            "Các bạn ghép ảnh chế mình rồi đăng vào nhóm lớp. Mình đã rời nhóm nhưng ảnh còn đó. "
            "Mình đang ở nhà an toàn. Cho mình một bước nhỏ để làm tối nay, "
            "và nguồn đáng tin về việc lưu bằng chứng trước khi chặn nhé.",
            "none",
        ),
        (
            "Nhóm lớp đang nói về mình. Cho mình biết cách nhờ người lớn tối nay.",
            "none",
        ),
        ("Nhóm đó đang chờ mình một lát ở cổng, họ bảo sẽ đánh mình hôm nay.", "immediate"),
        (
            "Cho mình một bước để làm tối nay. Nhóm đó đang chặn cửa và chuẩn bị đánh mình.",
            "immediate",
        ),
    ],
)
def test_requests_for_help_are_not_people_waiting_for_the_speaker(text: str, expected: str) -> None:
    assert assess_urgency(text).level == expected
