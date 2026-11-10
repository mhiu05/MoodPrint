"""Development regressions found during product audit; never an independent safety set."""

import pytest
from moodprint_agent.tools.safety import assess_urgency


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
