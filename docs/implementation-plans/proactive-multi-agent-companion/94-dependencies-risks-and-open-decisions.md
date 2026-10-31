# 94 — Phụ thuộc, rủi ro và quyết định mở

## 1. Blocker và hạng mục chưa kiểm chứng

| ID | Blocker | Ảnh hưởng | Cần gì |
| --- | --- | --- | --- |
| BLK-01 | **AWS MCP không kết nối** (`aws-mcp`, lỗi `-32602 Invalid request parameters`; tái hiện 31/10/2026 trong phiên triển khai). AWS CLI cục bộ profile `moodprint`: phiên đăng nhập **hết hạn** (`aws login`) — xem [96 §6](96-architecture-hardening-review.md#6-khuyến-nghị-dung-lượng-aws) | Không kiểm được EC2 (loại instance, CPU/RAM thực tế), CloudWatch log/metric, systemd timer, compose đang chạy | Owner sửa cấu hình/đăng nhập AWS MCP (ví dụ: chạy lại xác thực của server `aws-mcp` trong Claude Code và cấp quyền **chỉ đọc** EC2 `Describe*`, CloudWatch `GetMetricData`/`FilterLogEvents`, SSM `DescribeInstanceInformation`), rồi chạy lại phần kiểm tra ở [91 §9](91-performance-cost-and-capacity.md) |
| BLK-02 | Hosted đang ở `0019_journal`; nhánh yêu cầu `0020` | Image từ nhánh này không ready trên hosted | Owner duyệt và áp dụng 0020 qua quy trình review hiện có |
| BLK-03 | Không có tài khoản thử nghiệm tổng hợp trên production/staging | Không kiểm được chat đã đăng nhập bằng agent-browser | Owner cấp tài khoản **tổng hợp** (không dữ liệu thật) — không dán mật khẩu vào Markdown |
| BLK-04 | Release hold trên `main` (theo ghi chú dự án) | Không publish staging | Owner gỡ bằng PR khi đủ điều kiện |

## 2. Phụ thuộc

| Phụ thuộc | Loại | Ghi chú |
| --- | --- | --- |
| `openai-agents==0.24.0` | Thư viện | Bản mới nhất trên PyPI; không nâng cấp |
| OpenAI model `gpt-6-luna` | Bên ngoài | Giữ model chung cho chat/proactive/specialist (OD-12) |
| Supabase PostgreSQL 17 | Hạ tầng | Không cần extension mới |
| `tzdata==2026.5` | Thư viện | Đã pin |
| Quy trình hosted SQL review (`scripts/apply_supabase_review.py`) | Quy trình | Bắt buộc cho M-P1-A/B, M-P2-A |
| Công việc song song friendship-profile redesign | Nội bộ | Đang sửa `social/*`, `openapi.json`, `schema.d.ts`; có thể tranh số migration và gây conflict contract → gán số migration lúc triển khai, rebase trước P1-01 |

## 3. Sổ rủi ro

| ID | Rủi ro | Khả năng | Tác động | Giảm thiểu |
| --- | --- | --- | --- | --- |
| R-01 | Model tách bubble quá nhiều/vụn | Trung bình | UX | Hướng dẫn "mặc định 1", eval, cờ tắt |
| R-02 | Lời hỏi thăm bị cảm nhận là làm phiền | Trung bình | Rời bỏ | Opt-in, cap 4, auto-pause, giờ yên lặng, không push |
| R-03 | Bịa đọc nhật ký/sự kiện | Thấp–TB | Tin cậy | Validator, eval 0-tolerance, payload có `journal.status` |
| R-04 | Worker làm chậm chat | Thấp | Hiệu năng | Concurrency 1, không transaction quanh model call, load test |
| R-05 | Giao trùng khi deploy chồng | Thấp | Tin cậy | Unique + lease + publish atomic, test hai worker |
| R-06 | Kết nối *idle in transaction* hiện có giữ lock | Chưa rõ | Khóa lâu | Điều tra nguồn (có thể dev local trỏ hosted); `SET LOCAL lock_timeout` trong worker |
| R-07 | Timezone tài khoản không đổi được → "hôm qua" lệch nếu người dùng ở xa UTC+7 | Thấp (người dùng VN) | Sai ngày | Timezone riêng cho lời hỏi thăm; ghi chú UI; OD-11 |
| R-08 | Xung đột version khi tin chủ động chen vào hội thoại đang mở | Trung bình | Lỗi gửi | Hoãn khi đang chat, client tự tải lại giữ draft |
| R-09 | Rò rỉ nhật ký qua cộng tác | Thấp | Nghiêm trọng | Chỉ enum cho cạnh đọc nhật ký, canary test, red-team |
| R-10 | Dòng cộng tác không khớp thực tế | Thấp | Tin cậy | Template + receipt, không LLM |
| R-11 | Chi phí vượt | Thấp | Tài chính | Budget share 50 %/70 %, cap, trần [91 §4](91-performance-cost-and-capacity.md) |
| R-12 | Tin nguy cơ nghiêm trọng bị bỏ sót bởi sàng lọc từ vựng | Trung bình | An toàn | Không tuyên bố là bộ phân loại toàn diện; guardrail output; owner review danh sách mẫu |
| R-13 | Số migration bị chiếm bởi nhánh khác | Trung bình | Conflict | Dùng ký hiệu M-P1-A…; gán số khi rebase |
| R-14 | Hosted bảng mới chưa có trong `docs/supabase/schema.md` → CI fail | Cao nếu quên | CI | Task P1-02 bắt buộc cập nhật |

## 4. Quyết định mở

OD-01…OD-07 **đã quyết** ngày 31/10/2026 theo ủy quyền của owner — xem [ADR-13](03-architecture-decisions.md#adr-13--quyết-định-od-01od-07-owner-ủy-quyền-31102026). Các mặc định dưới đây được giữ sau khi so sánh phương án.

| ID | Câu hỏi | Mặc định đề xuất | Nếu khác |
| --- | --- | --- | --- |
| OD-01 | Lời hỏi thăm vào hội thoại nào? | Hội thoại gần nhất đủ điều kiện, nếu không thì tạo mới (ADR-07) | Luôn tạo mới: đổi `choose_conversation`, không đổi schema |
| OD-02 | Giới hạn và khung giờ | 4/ngày; sáng 05:00–11:30, tối 17:00–22:30, bước 15 phút | Đổi hằng + CHECK (migration nhỏ nếu nới khung) |
| OD-03 | Người dùng 16–17 có lời hỏi thăm không? | Có (trừ Cầu Nối), tối ≤ 21:00, giờ yên lặng mặc định 21:30–07:00 | Chặn teen: một điều kiện trong `authorize_proactive` |
| OD-04 | Văn bản consent "Dùng khoảnh khắc đã lưu hôm qua" ([phase-1/06 §9](phase-1/06-frontend-ux-and-notifications.md)) | Như bản nháp, mặc định tắt | Review pháp lý/quyền riêng tư trước khi bật cho người dùng thật |
| OD-05 | Không hoạt động 14 ngày → ngừng; auto-pause sau 3 lời chưa mở | Như đề xuất | Hằng cấu hình |
| OD-06 | Phần ngân sách cho lời hỏi thăm | 50 % `AI_DAILY_BUDGET_USD` | Cấu hình |
| OD-07 | Thông tin khẩn cấp trong mẫu tin an toàn | Không có số điện thoại cho tới khi owner cung cấp nguồn kiểm chứng | Thêm theo quốc gia |
| OD-08 | Tập cạnh cộng tác Phase 2 | 3 cạnh ([phase-2/03 §1](phase-2/03-agent-communication-and-consent.md)) | Bớt cạnh: xóa khỏi policy + CHECK |
| OD-09 | Cap/ngân sách cộng tác | 10/ngày, 70 % ngân sách | Cấu hình |
| OD-10 | Sheet "Vì sao?" hiển thị giá trị cụ thể đã chia sẻ? | Không (chỉ loại dữ liệu) | Lưu thêm enum trong receipt |
| OD-11 | Cho đổi timezone tài khoản? | Không trong phạm vi; timezone riêng cho lời hỏi thăm | Tính năng riêng, ảnh hưởng cửa sổ 90 ngày của nhật ký |
| OD-12 | Model cho proactive/specialist | Dùng `OPENAI_MODEL` hiện tại | Model nhỏ hơn cho specialist (cần cập nhật `RATES`) |

Không có quyết định kiến trúc nào để "TBD": mọi mục trên đã có mặc định có thể triển khai.
