# MoodPrint/Me2We — Kế hoạch triển khai ứng dụng full-stack

> **Kiến trúc đã chốt ngày 23/10/2026:** Python 3.12/FastAPI/Pydantic v2, SQLAlchemy 2 async + psycopg 3, Alembic/uv, Supabase PostgreSQL/Auth và OpenAI Agents SDK Python. Giữ React/Vite/TypeScript; Pydantic → OpenAPI → `frontend/src/api/generated/`. Chỉ scaffold cloud, không deploy. Evidence audit ban đầu là lịch sử, không phải trạng thái implementation mới.

Ngày audit: **23/10/2026**, múi giờ Asia/Bangkok. Trạng thái: **IMPLEMENTATION AUTHORIZED** cho source/local verification. Các kết quả audit bên dưới có phạm vi lịch sử; trạng thái task mới phải có evidence thực tế. Chưa phê duyệt cloud deployment, remote schema changes hoặc thử nghiệm người thật.

Mục tiêu là giữ trải nghiệm Self-Discovery, năm AI Companions và Human Connection hiện có, rồi thay từng phần giả lập bằng API, quyền dữ liệu và persistence có thể kiểm chứng. **Đã chốt một backend Python/FastAPI Modular Monolith, OpenAI Agents SDK Python và Supabase PostgreSQL/Auth; giữ React/Vite.**

## Hiện trạng và cách đọc

Audit ban đầu ghi nhận frontend chạy được, có domain logic/tests, backend/agents trống và thiếu auth/database/model/realtime. Đây là baseline lịch sử trước implementation. Trạng thái chi tiết và bằng chứng nằm ở [audit](01-codebase-audit.md). Các nhận định IMPLEMENTED chỉ áp dụng cho phạm vi thực sự đã kiểm tra, không chuyển từ “UI chạy” sang “sản phẩm full-stack hoàn tất”.

| Tài liệu                                                         | Dùng khi                                                     |
| ---------------------------------------------------------------- | ------------------------------------------------------------ |
| [00 — Tóm tắt điều hành](00-executive-summary.md)                | Chọn hướng, phạm vi và milestone đầu tiên                    |
| [01 — Audit codebase](01-codebase-audit.md)                      | Tra file, luồng hiện có, mock và kết quả kiểm tra            |
| [02 — Gap analysis](02-gap-analysis.md)                          | Truy từ yêu cầu Rxx đến task cần thực hiện                   |
| [03 — Kiến trúc đích](03-target-architecture.md)                 | Chọn stack, module boundaries và đường di chuyển             |
| [04 — Agents SDK](04-agents-sdk-architecture.md)                 | Làm runtime, bot registry, context, tools và streaming       |
| [05 — Backend/data/realtime](05-backend-data-realtime-plan.md)   | Làm API, mô hình dữ liệu, transaction, chat và jobs          |
| [06 — Tích hợp frontend](06-frontend-integration-plan.md)        | Thay mock từng màn hình, giữ UI và xử lý lỗi thật            |
| [07 — Roadmap](07-implementation-roadmap.md)                     | Giao task, kiểm dependencies, nghiệm thu và rollback         |
| [08 — Testing/evals](08-testing-evals-plan.md)                   | Chọn test, dữ liệu tổng hợp, rubric và quality gates         |
| [09 — Security/DevOps](09-security-devops-plan.md)               | Thực thi consent, TTL, deployment, vận hành và release gates |
| [10 — Quyết định/câu hỏi mở](10-decisions-and-open-questions.md) | Phân biệt sự thật, đề xuất, giả định và quyết định cần chốt  |

Các file 04, 05, 06 là nguồn chuẩn của contract tương ứng; 07 sở hữu thứ tự/task ID; 08 sở hữu test IDs và tiêu chí chất lượng; 10 sở hữu decision IDs. Tránh sao chép schema hoặc policy sang nhiều chỗ rồi sửa lệch nhau.

## Nguồn chuẩn và mức độ chắc chắn

Thứ tự áp dụng: quyết định stack/quyền implementation mới của người dùng → Charter/spec đã duyệt cho sản phẩm → source và test evidence cho hành vi hiện tại → tài liệu technical PROPOSED cho phần chưa chốt → official documentation cho khả năng API. **Chưa tìm thấy Charter và các spec gốc trong checkout này.** Không gọi các ràng buộc được thuật lại trong tài liệu technical là “đã xác minh bản phê duyệt”.

- [README gốc](../../README.md) mô tả mục đích MoodPrint; [README frontend](../../frontend/README.md) mô tả prototype Me2We.
- [Thiết kế PoC](../technical-poc-architecture.md), ngày 23/10/2026, ghi rõ PROPOSED; có các link cũ `prototype/` và `2-requirements/` không tồn tại trong checkout.
- [Prompt nghiên cứu](../prompt.md) thuật lại scoring, quota, retention, voice Must và Shared Activities Future. Dùng làm baseline bảo thủ để lập kế hoạch, chờ đối chiếu tài liệu gốc ở Q01.
- Hướng dẫn phiên do người dùng cung cấp: **không tự ý sửa `.gitignore`**. Không có `AGENTS.md`, `.agents/`, `.codex/`, PRODUCT.md hoặc DESIGN.md trong checkout ở thời điểm audit; tab IDE không chứng minh file tồn tại trên đĩa.
- SDK được tra từ [OpenAI Agents SDK](https://developers.openai.com/api/docs/guides/agents/sdk); danh mục nguồn và giới hạn xác minh ở [04](04-agents-sdk-architecture.md).

## Roadmap và critical path

| Phase | Demo/điểm kiểm chứng                                        | Phụ thuộc                                  |
| ----- | ----------------------------------------------------------- | ------------------------------------------ |
| 0     | Baseline, contracts, workspace/tooling có thể kiểm tra      | Checkout hiện tại                          |
| 1     | Đăng nhập, quyền độc lập, dữ liệu riêng lưu/reload đúng chủ | 0                                          |
| 2     | Mây gọi model thật, SSE, cancel, reload trong phiên         | 1; chỉ dữ liệu tổng hợp trước privacy gate |
| 3     | Năm bot, cards và context không lẫn thread                  | 2                                          |
| 4     | Mood, private items, memory được xác nhận/sửa/xóa thật      | 3 và dữ liệu nền ở 1                       |
| 5     | Hai tài khoản xuất bản, nhận gợi ý rule-based thật          | 1; có thể làm song song nhánh AI           |
| 6     | Hai phía đồng ý, chat, reconnect, block/reveal thật         | 5                                          |
| 7     | Voice có consent; nối màn hình vào backend thật             | 4, 6; gate riêng cho processor audio       |
| 8     | Bộ quyền/concurrency/E2E/evals/performance đạt gate         | Kiểm tra tích lũy từ 1; nghiệm thu sau 7   |
| 9     | Cloud skeleton, local restore/delete/rollback, Go/Hold      | 8 và các quyết định release                |

Critical path kỹ thuật: **contracts → auth/eligibility/consent + DB → Mây thật + context TTL + stream → năm bot/tools/memory → hoàn thiện UX → quality gates → local rehearsal/cloud skeleton**. Nhánh kết nối độc lập: **auth/consent → publish → matching → mutual transaction → messaging/replay/reveal**. Không bắt nhánh tìm bạn phải chờ LLM hoặc bật C-AI/C-MEM.

Milestone E2E đầu tiên ở cuối phase 2: frontend hiện tại → backend xác thực → C-AI → Agents SDK → model → kiểm output → stream → context phiên → reload còn đúng hội thoại; run metadata được lưu bền vững. **Transcript chỉ ở kho tạm có TTL, không mặc định thành lịch sử PostgreSQL.** Milestone dữ liệu dài hạn ở phase 4 chứng minh memory đã duyệt tồn tại sau restart.

## Cách giao Codex thực hiện

1. Đọc 00, 10 và phase tương ứng trong 07; kiểm prerequisites thực tế. Một task ID là một phạm vi review, thường 0,5–2 ngày công theo giả định ở 07, không phải cam kết lịch.
2. Dùng contract của 04/05/06 và test ID của 08. Chỉ thay file thuộc task; không rewrite UI, đổi scoring, mở quyền teen hoặc đưa Activities vào MVP.
3. Cập nhật trạng thái task cùng bằng chứng lệnh/test và decision đã chốt. Khi thay contract, cập nhật các tài liệu liên quan trong cùng thay đổi.
4. Chạy test đúng slice và gate quyền bắt buộc; demo hành vi cùng lỗi/revoke/reload. Không ghi PASS cho kiểm tra chưa chạy.
5. Báo thay đổi, dữ liệu đã lưu ở đâu, TTL, giới hạn và fallback. Đã được người dùng yêu cầu triển khai trực tiếp; không commit/push/cloud deploy/remote DDL.

**Bắt đầu ngay với P00.01–P00.03.** Thiếu Charter/provider không chặn baseline và contract local; chúng chặn việc khẳng định MVP đã đúng phạm vi hoặc chạy với dữ liệu thật. Xem Q01–Q08 trước khi đi qua các gate liên quan.

Bộ plans gồm **12 tài liệu, 39 task và 43 test IDs dự kiến**. [Báo cáo kiểm tra tài liệu](validation-artifacts/document-checks.json) ghi kiểm liên kết, task graph, code fences và hash tài liệu hiện tại; source hashes/test results audit cũ nằm riêng trong historicalAudit. Kết quả chạy prototype và giới hạn xác minh ở [08](08-testing-evals-plan.md). **Evidence lịch sử trước implementation:** typecheck, 77 unit tests, build và production smoke đạt; E2E **TIMED OUT ở teardown**, dù 15 cases hoàn tất assertions. Không tái dùng làm PASS cho source mới.

Kiểm integrity bằng `python scripts/check_plans.py`; thêm `--write` để cập nhật artifact. Giữ 39 task IDs và 43 test IDs. Product UI không nhãn Demo/Prototype/Experimental; fixtures/stub models chỉ automated testing. Pydantic DTOs là nguồn chuẩn; frontend generated TypeScript không chứa server-only fields.
