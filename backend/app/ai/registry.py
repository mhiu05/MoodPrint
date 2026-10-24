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
