# Phase 2 — 01. Yêu cầu sản phẩm: điều phối và cộng tác giữa trợ lý

**Điều kiện bắt đầu:** Gate G1 và G2-entry của Phase 1 đã đạt ([phase-1/08 §3](../phase-1/08-implementation-plan.md)). Phase 2 dùng lại: nhiều bubble + SSE v2, `ai_runs.origin`, `ai_message_sources` (provenance), pipeline proactive.

## 1. Mục tiêu

Một trợ lý có thể nhờ một trợ lý khác làm **một việc nhỏ, có giới hạn** khi điều đó thực sự giúp câu trả lời tốt hơn — với dữ liệu tối thiểu, có sự cho phép rõ ràng của người dùng, có bản ghi kiểm chứng, và được giải thích bằng lời dễ hiểu **chỉ khi việc nhờ đó thật sự đã xảy ra**.

Không phải mục tiêu: trợ lý thứ sáu, hội thoại nhóm giữa các trợ lý, trợ lý tự hành động xã hội, matching dựa trên cảm xúc/nhật ký, chuỗi nhờ vả lồng nhau.

## 2. Trường hợp sử dụng (Phase 2)

| ID | Cạnh | Ví dụ | Giá trị |
| --- | --- | --- | --- |
| UC-1 | Nhịp → Rủ Rê (`energy_hint`), lời hỏi thăm buổi sáng | Hôm qua người dùng ghi là rất mệt → Rủ Rê chọn thử thách 5 phút nhẹ nhàng thay vì vận động | Thử thách hợp sức người dùng mà Rủ Rê không đọc nhật ký |
| UC-2 | Nhịp → Rủ Rê (`energy_hint`), trong chat | "Rủ Rê ơi gợi ý gì nhẹ nhàng hợp với mình hôm nay" | Như trên, theo yêu cầu |
| UC-3 | Nhịp → Mây (`tiny_habit`), trong chat | Người dùng kể với Mây "mấy hôm nay mất ngủ" → Mây đáp ấm áp kèm một thói quen nhỏ do Nhịp đề xuất | Chuyên môn thói quen của Nhịp, Mây vẫn là người nói |
| UC-4 | Rủ Rê → Gương (`activity_for_interest`), trong chat | Người dùng khám phá sở thích vẽ với Gương → Gương gợi một hoạt động nhỏ do Rủ Rê chuẩn bị | Biến khám phá thành hành động nhỏ |

Cầu Nối **không** tham gia bất kỳ cạnh nào ở Phase 2.

## 3. User stories

| ID | Câu chuyện |
| --- | --- |
| US-21 | Tôi muốn bật/tắt riêng từng kiểu phối hợp và biết chính xác điều gì được chia sẻ |
| US-22 | Khi một trợ lý thật sự đã nhờ trợ lý khác, tôi muốn thấy một dòng giải thích ngắn, dễ hiểu |
| US-23 | Tôi không muốn thấy thuật ngữ kỹ thuật hay "suy nghĩ" nội bộ của trợ lý |
| US-24 | Nếu việc nhờ vả thất bại, tôi vẫn nhận được câu trả lời bình thường mà không bị làm phiền |
| US-25 | Khi tôi tắt phối hợp, việc chia sẻ dừng ngay, kể cả ở lượt đang chạy |
| US-26 | Nhật ký của tôi không bao giờ được chuyển nguyên văn sang trợ lý khác |

## 4. Yêu cầu chức năng

| ID | Yêu cầu | Tiêu chí |
| --- | --- | --- |
| P2-FR-01 | Chỉ các cạnh trong ma trận được phép; mọi cạnh khác bị từ chối ở code | Test ma trận 5×5 |
| P2-FR-02 | Mỗi cạnh cần quyền chia sẻ riêng, **mặc định tắt** | Tài khoản mới: 0 cạnh bật |
| P2-FR-03 | Quyết định nhờ vả theo **luật xác định** (R1–R4), không do model tự ý | Test luật; không có tool "ask another bot" |
| P2-FR-04 | Tối đa 1 lần nhờ mỗi lượt; specialist không được nhờ tiếp (độ sâu 1) | Test |
| P2-FR-05 | Dữ liệu chuyển giữa trợ lý chỉ là trường có cấu trúc đã khai báo (enum, số có giới hạn, văn bản ngắn do specialist tạo) | Validator; test canary |
| P2-FR-06 | Specialist chạy với quyền riêng, tối thiểu, có timeout, có bản ghi run/usage riêng | Test |
| P2-FR-07 | Câu giải thích cộng tác do backend tạo từ template, chỉ khi bản ghi `completed` và kết quả đã được dùng | Test; LLM không thể tạo câu này |
| P2-FR-08 | Trạng thái trực tiếp "Rủ Rê đang hỏi Nhịp…" chỉ hiện khi bước nhờ thật sự bắt đầu | SSE v2 `progress` thật |
| P2-FR-09 | Thất bại/timeout/bị từ chối → primary trả lời một mình; không hiện dòng cộng tác | Test |
| P2-FR-10 | Tắt quyền giữa chừng → hủy lượt đang dùng cạnh đó, không lưu kết quả | Test |
| P2-FR-11 | Giới hạn 10 lần phối hợp/ngày/người dùng; dừng khi ngân sách AI ≥ 70 % | Test |
| P2-FR-12 | Lời hỏi thăm buổi sáng của Rủ Rê có thể dùng UC-1 (R2) | Test pipeline proactive |

## 5. Phi chức năng

| ID | Yêu cầu | Ngưỡng |
| --- | --- | --- |
| P2-NFR-01 | Độ trễ thêm khi có phối hợp | p95 +≤ 4 s so với lượt đơn (ước tính [91](../91-performance-cost-and-capacity.md)) |
| P2-NFR-02 | Tổng thời gian lượt | ≤ 30 s (giới hạn hiện có) |
| P2-NFR-03 | Không lưu nội dung request/response giữa trợ lý | Chỉ digest |
| P2-NFR-04 | Khả năng kiểm toán | Mỗi lần phối hợp có một `ai_collaborations` row |
| P2-NFR-05 | Không ảnh hưởng người dùng không bật | 0 call thêm khi mọi cạnh tắt |

## 6. Tài liệu liên quan

Kiến trúc: [02](02-orchestration-architecture.md). Giao tiếp và consent: [03](03-agent-communication-and-consent.md). UI: [04](04-collaboration-ui-ux.md). Backend/DB: [05](05-backend-and-database-contracts.md). Kế hoạch: [06](06-implementation-plan.md). Kiểm thử: [07](07-testing-and-acceptance.md).
