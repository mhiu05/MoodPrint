from app.ai.agents import REPLACED_BY
from app.contracts import BotPublicDTO

BOTS = [
    BotPublicDTO(
        bot_id="may",
        name="Mây",
        role="Lắng nghe & tâm sự",
        description="Một khoảng nhỏ để được lắng nghe.",
        starters=["Hôm nay mình hơi mệt", "Kể một chút", "Đổi chủ đề"],
        avatar_key="may",
    ),
    BotPublicDTO(
        bot_id="guong",
        name="Gương",
        role="Khám phá bản thân",
        description="Tìm thêm một điều thú vị về bạn.",
        starters=["Mình thích đọc sách", "Điều mình coi trọng"],
        avatar_key="guong",
    ),
    BotPublicDTO(
        bot_id="nhip",
        name="Nhịp",
        role="Cảm xúc & thói quen",
        description="Chậm một nhịp, nghe mình một chút.",
        starters=["Ghi lại cảm xúc", "Nhìn lại tuần", "Một thói quen nhỏ"],
        avatar_key="nhip",
    ),
    BotPublicDTO(
        bot_id="rure",
        name="Rủ Rê",
        role="Học hỏi & cùng chơi",
        description="Thử một điều mới, vui thêm một chút.",
        starters=["Giải đố", "Học gì đó", "Tìm người chơi cùng"],
        avatar_key="rure",
    ),
    BotPublicDTO(
        bot_id="caunoi",
        name="Cầu Nối",
        role="Tìm bạn đồng điệu",
        description="Từ một điểm chung đến một người bạn.",
        starters=["Tìm bạn cùng sở thích", "Sửa hồ sơ kết nối"],
        avatar_key="caunoi",
    ),
]

# V3 default agents (AI_THREE_AGENT_EXPERIENCE_ENABLED). Exactly these three are offered.
AGENTS = [
    BotPublicDTO(
        bot_id="dieuphoi",
        name="Điều phối",
        role="Trò chuyện & lên hướng đi",
        description="Hiểu điều bạn cần, cùng bạn gỡ rối và gọi đúng người giúp.",
        starters=["Hôm nay mình hơi rối", "Giúp mình sắp xếp tuần này", "Mình muốn hiểu bản thân hơn"],
        avatar_key="dieuphoi",
    ),
    BotPublicDTO(
        bot_id="nhatky",
        name="Nhật ký",
        role="Nhật ký & cảm xúc",
        description="Nhìn lại những gì bạn đã ghi, nhận ra điều lặp lại.",
        starters=["Nhìn lại tuần này", "Giúp mình viết vài dòng", "Một thói quen nhỏ"],
        avatar_key="nhatky",
    ),
    BotPublicDTO(
        bot_id="hoatdong",
        name="Hoạt động",
        role="Hoạt động & học hỏi",
        description="Biến ý định thành một việc nhỏ làm được ngay.",
        starters=["Gợi ý việc nhẹ cho tối nay", "Mình muốn học điều mới", "Chia nhỏ mục tiêu giúp mình"],
        avatar_key="hoatdong",
    ),
]
LEGACY_BOTS = [
    bot.model_copy(update={"legacy": True, "replaced_by": REPLACED_BY[bot.bot_id]}) for bot in BOTS
]
