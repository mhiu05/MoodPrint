"""Frozen Phase 2 query set. Re-running this module rewrites the same JSONL."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

ANSWERABLE: dict[str, tuple[list[str], list[str]]] = {
    "definition": (
        ["legacy-bat-nat-la-gi", "mp-definition-01", "mp-definition-02", "mp-definition-03"],
        [
            "trêu nhau có tính là bắt nạt không",
            "thế nào là bắt nạt học đường",
            "xung đột khác bắt nạt chỗ nào",
            "dấu hiệu mình đang bị bắt nạt",
            "bạn đùa dai có phải bắt nạt",
            "bắt nạt khác cãi nhau thế nào",
            "làm sao biết một việc là bắt nạt",
            "trêu cho vui nhưng mình thấy sợ",
            "định nghĩa bắt nạt cho học sinh",
            "khi nào trò đùa trở thành bắt nạt",
            "mình không chắc việc đó có phải bắt nạt",
            "bạn cứ trêu hoài có phải chuyện nhỏ",
        ],
    ),
    "physical": (
        ["mp-physical-01", "mp-physical-02", "mp-physical-03"],
        [
            "bị bạn đánh ở sân trường",
            "bị xô ngã ở hành lang",
            "bị giật tóc lúc ra chơi",
            "bị tát trước mặt cả lớp",
            "bị đẩy vào tường ở trường",
            "bị đánh mà không dám kể",
            "bạo lực thể chất ở sân chơi",
            "bị đạp vào cặp sách",
            "bị giữ tay không cho đi",
            "bị đánh rồi bị dọa im lặng",
            "bị véo ở lớp mà không ai thấy",
            "bị lấy mạnh cặp rồi đẩy mình",
        ],
    ),
    "verbal-social": (
        ["mp-verbal-social-01", "mp-verbal-social-02", "mp-verbal-social-03"],
        [
            "cả lớp nói xấu mình sau lưng",
            "bị đặt biệt danh xấu",
            "bị chế giễu ngoại hình mỗi ngày",
            "bị tung tin đồn trong lớp",
            "bị la mắng giữa giờ ra chơi",
            "bạn bè cười nhạo mình liên tục",
            "bị nói nặng lời ở nhóm bạn",
            "bị trêu vì điểm số",
            "bị nhại giọng trước lớp",
            "lời nói làm mình không dám đến lớp",
            "bị nói tục mỗi lần đi qua",
            "cả nhóm đặt chuyện về mình",
        ],
    ),
    "exclusion": (
        ["mp-exclusion-01", "mp-exclusion-02", "mp-exclusion-03"],
        [
            "không ai chơi cùng mình",
            "bị loại khỏi nhóm bạn",
            "không được ngồi chung bàn",
            "bị cô lập ở giờ ra chơi",
            "nhóm không cho mình tham gia",
            "mọi người tránh mặt mình",
            "bị bỏ rơi trong hoạt động nhóm",
            "không ai trả lời khi mình chào",
            "bị gạt khỏi cuộc chơi",
            "cảm giác bị cả lớp loại ra",
            "không được mời vào nhóm làm bài",
            "ra chơi một mình vì không ai rủ",
        ],
    ),
    "cyber": (
        ["mp-cyber-01", "mp-cyber-02", "mp-cyber-03", "legacy-chan-va-bao-cao-noi-dung"],
        [
            "bị nhắn tin dọa trong nhóm lớp",
            "bị lập nhóm nói xấu trên mạng",
            "có tài khoản giả dùng tên mình",
            "bị gửi ảnh riêng vào nhóm chat",
            "bị quấy rối trong tin nhắn",
            "nhóm chat cứ nhắc đến mình",
            "bị dọa phát tán tin nhắn",
            "bị tag vào bài viết xấu",
            "không thoát được nhóm nói xấu",
            "bị nhắn tin đêm khuya để dọa",
            "bi nhan tin doa trong nhom lop",
        ],
    ),
    "evidence": (
        ["mp-evidence-01", "mp-evidence-02", "mp-evidence-03", "legacy-luu-anh-chup-co-ngu-canh"],
        [
            "chụp màn hình lưu lại như nào",
            "giữ tin nhắn trước khi bị xóa",
            "lưu bằng chứng mà không chuyển tiếp",
            "ghi ngày giờ của tin nhắn",
            "ảnh chụp màn hình đưa cho ai",
            "không biết có nên giữ ảnh không",
            "bằng chứng trên điện thoại bị mất",
            "cách giữ lại cuộc trò chuyện",
            "lưu tin nhắn mà không trả thù",
            "chụp màn hình rồi nói với người lớn",
        ],
    ),
    "help-seeking": (
        [
            "legacy-noi-chuyen-voi-giao-vien",
            "legacy-noi-chuyen-voi-nguoi-cham-soc",
            "legacy-tong-dai-111",
            "mp-help-seeking-01",
        ],
        [
            "nói với cô giáo thế nào",
            "không biết mở lời với người lớn",
            "muốn kể với bố mẹ nhưng ngại",
            "nên nói với giáo viên chủ nhiệm",
            "cần một người lớn đáng tin",
            "sợ kể ra sẽ bị mắng",
            "làm sao bắt đầu câu chuyện",
            "nhờ cô giáo nghe mình",
            "nói với người chăm sóc ở nhà",
            "chưa dám kể hết một lúc",
            "theo dõi sau khi đã nhờ giúp",
        ],
    ),
    "school-procedure-vn": (
        ["mp-school-procedure-vn-01", "mp-school-procedure-vn-02", "mp-school-procedure-vn-03"],
        [
            "báo với trường thì ai xử lý",
            "giáo viên chủ nhiệm làm gì khi có bắt nạt",
            "ban giám hiệu có vai trò gì",
            "quy trình nhà trường khi bị bắt nạt",
            "nên báo cô tổng phụ trách không",
            "nhà trường tiếp nhận việc này ra sao",
            "ai trong trường có thể đứng ra nghe",
            "báo cáo ở trường khác kể trên mạng",
            "trường sẽ gọi phụ huynh khi nào",
            "muốn nhà trường biết mà không ồn ào",
        ],
    ),
    "legal-vn": (
        ["mp-legal-vn-01", "mp-legal-vn-02", "mp-legal-vn-03", "legacy-tong-dai-111"],
        [
            "khi nào gọi 111",
            "tổng đài 111 có mất tiền không",
            "111 hoạt động giờ nào",
            "gọi 111 khác gọi công an thế nào",
            "quyền được bảo vệ khi bị bắt nạt",
            "khi nào cần cơ quan chức năng",
            "số 111 dành cho trẻ em",
            "có được gọi 111 dù chưa chắc",
            "111 nghe chuyện bắt nạt không",
            "pháp luật bảo vệ học sinh ra sao",
        ],
    ),
    "bystander": (
        ["mp-bystander-01", "mp-bystander-02", "mp-bystander-03"],
        [
            "thấy bạn bị bắt nạt thì làm gì",
            "có nên vào giữa khi bạn bị trêu",
            "mình đứng nhìn có sao không",
            "rủ bạn ra khỏi chỗ đang bị trêu",
            "không muốn tham gia cười nhạo",
            "người chứng kiến nên gọi người lớn",
            "thấy bạn bị cô lập thì sao",
            "không dám can nhưng muốn giúp",
            "báo cô giáo hộ một bạn khác",
            "đứng về phía bạn bị hại",
        ],
    ),
    "emotional-impact": (
        [
            "legacy-tam-dung-khi-lo-lang",
            "mp-emotional-impact-01",
            "mp-emotional-impact-02",
            "mp-emotional-impact-03",
        ],
        [
            "bị bắt nạt xong rất lo",
            "không muốn đến trường vì sợ",
            "thấy mệt sau khi bị nói xấu",
            "cần tạm dừng khi quá lo lắng",
            "không ngủ được vì sợ ngày mai",
            "cảm thấy xấu hổ sau khi bị trêu",
            "muốn bình tĩnh lại trước khi kể",
            "lo lắng không có nghĩa là yếu",
            "sau buổi bị trêu mình rất run",
            "làm sao dịu lại khi đang sợ",
        ],
    ),
    "parents-teachers": (
        ["mp-parents-teachers-01", "mp-parents-teachers-02", "mp-parents-teachers-03"],
        [
            "nói với bố mẹ như nào",
            "phụ huynh nên nghe con thế nào",
            "giáo viên hỏi học sinh ra sao",
            "đừng bắt con đối chất ngay",
            "người lớn không nên đổ lỗi cho con",
            "cách ngồi nghe một học sinh kể",
            "bố mẹ muốn giúp mà con chưa muốn nói",
            "thầy cô không được phớt lờ",
            "nói chuyện ở nhà cho an toàn",
            "người lớn hứa gì khi con kể",
        ],
    ),
    "platform-reporting": (
        ["mp-platform-reporting-01", "mp-platform-reporting-02", "mp-platform-reporting-03"],
        [
            "báo cáo bài đăng làm mình sợ",
            "chặn người nhắn tin dọa",
            "báo nội dung xấu mà không trả thù",
            "không biết nút báo cáo ở đâu theo nguyên tắc",
            "gỡ mình khỏi nhóm chat",
            "báo cáo tài khoản giả mạo tên mình",
            "chặn và giữ bằng chứng",
            "nói với người lớn trước khi bấm báo cáo",
            "báo nội dung lộ ảnh riêng",
            "nguyên tắc chặn người đang quấy rối",
        ],
    ),
    "urgent-safety": (
        ["mp-urgent-safety-01", "mp-urgent-safety-02", "mp-urgent-safety-03"],
        [
            "mình sợ bị đánh nữa ngay hôm nay",
            "đang bị dồn vào góc thì làm gì",
            "cần ra chỗ đông người",
            "sợ bị hại ngay bây giờ",
            "không an toàn khi về một mình",
            "cần người lớn ngay lúc này",
            "bị đe dọa đánh sau giờ học",
            "đang run và muốn rời khỏi đó",
            "gọi người lớn khi nguy hiểm tức thì",
            "nếu sợ bị đánh tiếp thì đi đâu",
        ],
    ),
}

NO_RESULT = [
    "công thức nấu phở bò",
    "lịch sử miệng núi lửa",
    "giải phương trình bậc hai",
    "tỷ số bóng đá đêm qua",
    "giá vé máy bay đi huế",
    "cách thay lốp xe đạp",
    "nguồn gốc của trà ô long",
    "chu vi hình tròn là gì",
    "tên các hành tinh trong hệ mặt trời",
    "cách gấp máy bay giấy",
    "lịch thi violon cuối năm",
    "công dụng của vitamin k",
    "sông nào dài nhất việt nam",
    "cách reset modem wifi",
    "luật việt vị trong bóng đá",
    "công thức diện tích hình thang",
    "mùa mưa ở đà lạt bắt đầu khi nào",
    "cách trồng rau mầm",
    "ý nghĩa của số pi",
    "lịch sử áo dài thập niên 1960",
    "cách đọc bản đồ địa hình",
    "tên gọi khoa học của mèo",
    "cách bảo quản mật ong",
    "vì sao lá cây có màu xanh",
    "cách thắt cà vạt",
    "lịch sử cầu long biên",
    "công thức hóa học của muối ăn",
    "cách chơi cờ vua khai cuộc",
    "tên các cung hoàng đạo",
    "cách đo huyết áp tại nhà",
]


def write_cases(path: Path) -> str:
    rows: list[dict[str, object]] = []
    number = 1
    for topic, (docs, queries) in ANSWERABLE.items():
        for query in queries:
            rows.append(
                {
                    "id": f"A{number:03d}",
                    "query": query,
                    "topic": topic,
                    "relevant": docs,
                    "no_result": False,
                }
            )
            number += 1
    for index, query in enumerate(NO_RESULT, start=1):
        rows.append(
            {
                "id": f"N{index:03d}",
                "query": query,
                "topic": "",
                "relevant": [],
                "no_result": True,
            }
        )
    dev_answerable = [row for row in rows if not row["no_result"]][:60]
    dev_ids = {row["id"] for row in dev_answerable}
    dev_ids.update(row["id"] for row in rows if row["no_result"] and int(str(row["id"])[1:]) <= 12)
    for row in rows:
        row["split"] = "dev" if row["id"] in dev_ids else "test"
    payload = "\n".join(json.dumps(row, ensure_ascii=False, sort_keys=True) for row in rows) + "\n"
    path.write_text(payload, encoding="utf-8")
    return hashlib.sha256(payload.encode()).hexdigest()


if __name__ == "__main__":
    target = Path(__file__).with_name("benchmark.jsonl")
    print(write_cases(target), target)
