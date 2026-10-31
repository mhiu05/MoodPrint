# Phase 1 — 01. Yêu cầu sản phẩm

Phạm vi: **P1.1** nhiều bubble, **P1.2** tin chủ động sáng/tối, **P1.3** lịch do người dùng cấu hình, **P1.4** thông báo **trong ứng dụng**. Ngoài phạm vi: Web Push, Service Worker, VAPID, thông báo native, email, SMS, hành động xã hội tự động, matching từ dữ liệu riêng tư, điều phối đa agent (Phase 2).

## 1. Người dùng và bối cảnh

| Nhóm | Đặc điểm | Hệ quả thiết kế |
| --- | --- | --- |
| Người dùng 16–17 (`age_band='teen'`) | Dùng được trợ lý cá nhân, **không** dùng tính năng kết nối | Không có lịch Cầu Nối; giờ tối mặc định sớm hơn; giờ yên lặng mặc định 21:30–07:00 |
| Người dùng ≥18 (`adult`) | Có thể bật MATCH | Cầu Nối chỉ nhắn khi đủ điều kiện kết nối |
| Guest (thử 2 giờ) | Không có lịch sử dài hạn | **Không** có tin chủ động |
| Người không rành công nghệ | Không quen "lịch", "cron" | Ngôn ngữ đời thường: "Lời hỏi thăm", "Buổi sáng lúc 07:30" |

## 2. User stories

| ID | Câu chuyện | Ưu tiên |
| --- | --- | --- |
| US-01 | Là người dùng, tôi muốn trợ lý trả lời thành vài tin ngắn khi tự nhiên hơn, để đọc dễ như nhắn tin với bạn | P0 |
| US-02 | Là người dùng, tôi muốn **tự chọn** trợ lý nào được hỏi thăm tôi và vào giờ nào | P0 |
| US-03 | Là người dùng, tôi muốn Nhịp xem lại khoảnh khắc tôi đã lưu hôm qua rồi gợi ý **một** việc nhỏ cho hôm nay — chỉ khi tôi cho phép | P0 |
| US-04 | Là người dùng, khi mở lại web tôi muốn thấy ngay trợ lý nào vừa nhắn và đọc trong đúng cuộc trò chuyện | P0 |
| US-05 | Là người dùng, tôi muốn tạm dừng hoặc tắt hẳn lời hỏi thăm bất cứ lúc nào, không cần giải thích | P0 |
| US-06 | Là người dùng, tôi không muốn bị nhắn trong giờ nghỉ hoặc bị nhắn quá nhiều | P0 |
| US-07 | Là người dùng 16–17 tuổi, tôi được trải nghiệm hỏi thăm an toàn, không bị mời kết bạn | P0 |
| US-08 | Là người dùng không viết nhật ký hôm qua, tôi không muốn bị nhắc khiến mình thấy có lỗi | P0 |
| US-09 | Là người dùng có nhiều tab, khi đọc ở một tab thì tab kia hết chấm báo | P1 |

## 3. Yêu cầu chức năng

### P1.1 — Nhiều bubble

| ID | Yêu cầu | Tiêu chí chấp nhận |
| --- | --- | --- |
| P1-FR-01 | Một run có thể tạo 1–4 bubble; mặc định 1 | Schema từ chối 0 hoặc >4; eval đo tỷ lệ tách |
| P1-FR-02 | Không ép tách: danh sách, một ý liền mạch, câu trả lời ngắn giữ một bubble | Eval: câu < 160 ký tự → 1 bubble ≥ 95 % |
| P1-FR-03 | Mọi bubble chỉ hiện khi **cả run** đã validate và lưu | Không có bubble nào trong UI trước event `completed` |
| P1-FR-04 | Thứ tự bubble ổn định qua reload, phân trang, export | `sequence` liên tiếp; test reload |
| P1-FR-05 | Client cũ (v1) vẫn nhận được câu trả lời | Contract test v1 với run 3 bubble |
| P1-FR-06 | Sao chép, chọn chữ, đọc bằng screen reader theo từng bubble và theo nhóm | E2E a11y |

### P1.2 — Tin chủ động

| ID | Yêu cầu | Tiêu chí |
| --- | --- | --- |
| P1-FR-10 | Trợ lý có thể bắt đầu cuộc trò chuyện vào khung sáng/tối đã bật mà **không** cần tin của người dùng | Có run `origin='proactive'`, **không** có row `actor='self'` tương ứng |
| P1-FR-11 | Nhịp (buổi sáng) chỉ đọc entry `saved` của **hôm qua theo múi giờ lịch**, khi người dùng bật "Dùng khoảnh khắc hôm qua" | Test với draft, entry hôm kia, entry 91 ngày, entry người khác |
| P1-FR-12 | Nhịp phân biệt điều đã ghi (quan sát) với gợi ý; gợi ý đúng **một** việc nhỏ, có thể bỏ qua | Validator: tối đa 1 gợi ý; eval rubric |
| P1-FR-13 | Không có entry hôm qua → không nhắc tới hôm qua, không trách | Validator chặn claim đọc nhật ký; eval |
| P1-FR-14 | Rủ Rê gợi ý một thử thách học/vui ngắn (≤15 phút), tránh lặp loại gần đây | Lưu `challenge_kind` content-free; test không trùng 3 lần liên tiếp |
| P1-FR-15 | Mây, Gương hỏi thăm nhẹ nhàng, không giả định tâm trạng | Eval rubric |
| P1-FR-16 | Cầu Nối chỉ nhắn khi `adult` + MATCH bật + không bị hạn chế; không nhắc người cụ thể, không gửi lời mời | Test eligibility; validator chặn claim "đã gửi/đã kết nối" |
| P1-FR-17 | Không bịa sự kiện quá khứ; không dùng transcript cũ làm nguồn | Input proactive không chứa transcript (test) |
| P1-FR-18 | Tín hiệu nguy cơ nghiêm trọng trong nhật ký → không gợi ý hoạt động; gửi mẫu tin an toàn đã duyệt | Test với entry canary |

### P1.3 — Lịch do người dùng cấu hình

| ID | Yêu cầu | Tiêu chí |
| --- | --- | --- |
| P1-FR-20 | **Opt-in**: mặc định mọi lịch tắt; không tự đăng ký | Tài khoản mới: 0 lịch bật |
| P1-FR-21 | Bật/tắt riêng từng trợ lý × buổi sáng/tối | API `PUT /ai/proactive/schedules/{botId}/{slot}` |
| P1-FR-22 | Chọn giờ: sáng 05:00–11:30, tối 17:00–22:30 (bước 15 phút); teen: tối ≤ 21:00 | Validator từ chối ngoài khoảng |
| P1-FR-23 | Lặp lại: Mỗi ngày / Ngày thường (T2–T6) / Cuối tuần / Tự chọn ngày | Bitmask `weekdays` |
| P1-FR-24 | Múi giờ: mặc định múi giờ tài khoản, có thể chọn múi giờ thiết bị hoặc từ danh sách IANA | Lưu ở `ai_proactive_settings.timezone` |
| P1-FR-25 | Tạm dừng 1 ngày / 3 ngày / 7 ngày / đến khi bật lại; xóa lịch | `paused_until`, `DELETE` |
| P1-FR-26 | Giờ yên lặng (mặc định 22:00–07:00; teen 21:30–07:00): không cho đặt lịch trong khoảng này | Validator |
| P1-FR-27 | Giới hạn **4 lời hỏi thăm mỗi ngày** cho toàn tài khoản | Tối đa 4 khung bật; worker kiểm lại |
| P1-FR-28 | Đổi/tắt lịch hủy job chưa giao của lịch đó ngay | Test: job `pending` → `cancelled` |
| P1-FR-29 | Tự động tạm dừng một trợ lý khi 3 lời hỏi thăm liên tiếp của trợ lý đó chưa được mở; báo rõ trong cài đặt | Test + UI copy |

### P1.4 — Thông báo trong ứng dụng

| ID | Yêu cầu | Tiêu chí |
| --- | --- | --- |
| P1-FR-30 | Tin chủ động nằm trong hội thoại của đúng trợ lý | ADR-07 |
| P1-FR-31 | Chấm báo trên tab "Trợ lý", số trên từng trợ lý, mục "Lời nhắn mới" trên danh sách | E2E |
| P1-FR-32 | Còn thấy sau reload/mở lại | Read state lưu server |
| P1-FR-33 | Không trùng: một lượt giao = một thông báo dù 3 bubble | Test đếm |
| P1-FR-34 | Đánh dấu đã đọc khi hội thoại hiển thị tin đó; có nút "Đánh dấu đã đọc tất cả" | API read marker |
| P1-FR-35 | Không xem trước nội dung ngoài hội thoại (chỉ "Nhịp gửi lời hỏi thăm buổi sáng · 07:30") | Kiểm UI |
| P1-FR-36 | Người dùng có thể tắt chấm báo (tin vẫn được giao) | `badges_enabled` |

## 4. Yêu cầu phi chức năng

| ID | Yêu cầu | Ngưỡng |
| --- | --- | --- |
| P1-NFR-01 | Tin chủ động giao trong 10 phút sau giờ hẹn (khi hệ thống khỏe) | p95 ≤ 10 phút |
| P1-NFR-02 | Bỏ qua thay vì giao muộn | Muộn hơn `PROACTIVE_GRACE_MINUTES` (90) → `skipped(missed_window)` |
| P1-NFR-03 | Không ảnh hưởng chat của người dùng | p95 thời gian tới `final` tăng ≤ 10 % trong load test |
| P1-NFR-04 | Không thêm kết nối DB | Pool giữ 5+2 |
| P1-NFR-05 | Chi phí nằm trong ngân sách ngày | Dừng proactive khi chi ≥ `PROACTIVE_BUDGET_SHARE` × `AI_DAILY_BUDGET_USD` |
| P1-NFR-06 | Log/metric không chứa nội dung, nhật ký, câu trả lời | Test log privacy |
| P1-NFR-07 | Mọi chữ hiển thị là tiếng Việt tự nhiên | Review copy; không dùng "cron", "worker", "agent run", "SSE" |
| P1-NFR-08 | WCAG 2.2 AA cho màn mới | axe + kiểm tay |

## 5. Quy tắc nội dung và an toàn

- Không chẩn đoán, không gán nhãn tâm lý, không suy diễn nguyên nhân, không tạo cảm giác có lỗi, không thúc ép ("Bạn phải…", "Đừng quên…").
- Tối đa một câu hỏi mỗi lời hỏi thăm; luôn có cách "kệ nó" (không cần trả lời).
- Không bịa người, sự kiện, số liệu; không nói "mình đã đọc" khi không có bằng chứng backend.
- Nguy cơ tức thời: dùng mẫu an toàn đã duyệt ([07 §8](07-persona-behaviors-and-prompts.md)); không bịa số điện thoại/tổ chức (chính sách hiện có trong [prompts.py](../../../../backend/app/ai/prompts.py)).

## 6. Phụ thuộc chéo

Hợp đồng nhiều bubble: [02](02-multi-message-contract.md). Scheduler: [03](03-proactive-scheduler-and-workers.md). DB: [04](04-database-and-migrations.md). API/runtime: [05](05-backend-api-and-agent-runtime.md). UI: [06](06-frontend-ux-and-notifications.md). Persona: [07](07-persona-behaviors-and-prompts.md). Kế hoạch: [08](08-implementation-plan.md). Kiểm thử: [09](09-testing-and-acceptance.md).
