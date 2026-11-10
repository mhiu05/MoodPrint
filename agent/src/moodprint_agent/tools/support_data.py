"""Static, verified support directory. Add an entry only with a source and a verification date.

Phone numbers: only the national child-protection line 111 is verified (tongdai111.vn, copied
from the frontend support feature, checked 2026-11-07). Everything else is guidance without a
number, so the Companion can never hand out an unverified contact.
"""

from typing import Any, Final

VERIFIED_ON: Final = "2026-11-07"

DIRECTORY: Final[dict[str, list[dict[str, Any]]]] = {
    "urgent": [
        {
            "id": "vn-111",
            "title": "Tổng đài Quốc gia bảo vệ trẻ em 111",
            "description": "Miễn phí, hoạt động 24/24. Bạn không cần có hồ sơ đầy đủ mới gọi được.",
            "phone": "111",
            "source": "https://tongdai111.vn/tin/so-dien-thoai-bao-ve-tre-em",
            "verifiedOn": VERIFIED_ON,
        },
        {
            "id": "adult-nearby",
            "title": "Người lớn ở gần bạn",
            "description": "Thầy cô, bảo vệ trường, người thân hoặc hàng xóm bạn tin; nhờ họ ở cạnh bạn ngay.",
            "phone": None,
            "source": None,
            "verifiedOn": None,
        },
    ],
    "school": [
        {
            "id": "school-teacher",
            "title": "Giáo viên bạn tin tưởng",
            "description": "Có thể cùng bạn xem lại việc xảy ra ở lớp và bàn bước tiếp theo.",
            "phone": None,
            "source": None,
            "verifiedOn": None,
        }
    ],
    "family": [
        {
            "id": "family-adult",
            "title": "Bố mẹ hoặc người thân đáng tin",
            "description": "Chuẩn bị 2–3 sự việc cụ thể và điều bạn muốn người đó giúp.",
            "phone": None,
            "source": None,
            "verifiedOn": None,
        }
    ],
    "online": [
        {
            "id": "platform-report",
            "title": "Báo cáo nội dung trên nền tảng",
            "description": "Lưu lại bằng chứng, chặn tài khoản và dùng chức năng báo cáo của nền tảng.",
            "phone": None,
            "source": None,
            "verifiedOn": None,
        }
    ],
}

RECIPIENT_ROLES: Final = {
    "teacher": ("Em chào cô/thầy ạ,", "Em cảm ơn cô/thầy đã đọc tin nhắn của em."),
    "parent": ("Bố/mẹ ơi,", "Con cảm ơn bố/mẹ đã nghe con."),
    "trusted_adult": ("Chào anh/chị/cô/chú,", "Cảm ơn bạn đã dành thời gian cho mình."),
    "counselor": ("Em chào cô/thầy tư vấn ạ,", "Em cảm ơn cô/thầy đã hỗ trợ em."),
}
