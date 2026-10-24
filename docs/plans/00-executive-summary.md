# 00 — Tóm tắt điều hành

> **Kiến trúc đã chốt ngày 23/10/2026:** Python 3.12/FastAPI/Pydantic v2, SQLAlchemy 2 async + psycopg 3, Alembic/uv, Supabase PostgreSQL/Auth và OpenAI Agents SDK Python. Giữ React/Vite/TypeScript; Pydantic → OpenAPI → `frontend/src/api/generated/`. Chỉ scaffold cloud, không deploy. Evidence audit ban đầu là lịch sử, không phải trạng thái implementation mới.

## Kết luận

**Giữ frontend và triển khai backend Python/FastAPI Modular Monolith với OpenAI Agents SDK Python.** Một ASGI application phục vụ HTTP, AI SSE và human SSE ID-only; Python worker dùng chung domain services. Supabase PostgreSQL lưu domain/metadata, Supabase Auth xử lý credentials. Context AI tạm nằm ngoài database bền vững. Năm bot là năm cấu hình có phiên bản trong một runtime, không cần năm service.

Đây là stack người dùng đã chốt ngày 23/10/2026; không phải chứng nhận mọi feature đã triển khai hoặc production-ready. [Tài liệu PoC](../technical-poc-architecture.md) cũng đang PROPOSED. Charter, Privacy/AI/Matching specs mà tài liệu đó dẫn tới không có trong checkout; Q01 cần đối chiếu bản gốc trước nghiệm thu phạm vi.

## Tài sản và khoảng trống ở audit lịch sử trước implementation

| Nhóm               | Kết luận từ source/kiểm tra                                                                                              | Hệ quả                                                                 |
| ------------------ | ------------------------------------------------------------------------------------------------------------------------ | ---------------------------------------------------------------------- |
| Frontend           | React/Vite/TypeScript, HashRouter, roster 5 bot, mood, hồ sơ, discovery, lời mời, human chat, reveal/block/report, ACT01 | Giữ layout, SVG, GSAP, navigation và components; tích hợp từng feature |
| Domain             | Scoring 45/35/20, checks theo consent/version, invalidation, quotas được thực thi trong reducer                          | Có oracle hồi quy; phải chuyển quyền quyết định sang backend           |
| AI                 | `scriptedReply`, timer và fixture; chưa cài Agents SDK                                                                   | Không có model/tool/session/memory thật để tái sử dụng                 |
| Backend/agents     | Hai thư mục trống                                                                                                        | Bắt đầu backend nhỏ; không có service cũ cần bảo tồn                   |
| Data/realtime/auth | RAM, không network client/server, không schema/migration/auth                                                            | P0 là identity, consent, ownership, lifecycle và transaction           |
| Testing            | Unit tests hiện có chạy thành công: 77/77; typecheck/build thành công                                                    | Chưa có test backend hoặc eval model thật                              |

Chi tiết, ảnh render và trạng thái kiểm tra browser nằm trong [01](01-codebase-audit.md). Không coi kết quả prototype là bằng chứng hai tài khoản thật đã kết nối an toàn.

## Các quyết định kiến trúc có hiệu lực

1. **Python/FastAPI đã chốt.** Python 3.12, Pydantic v2, SQLAlchemy 2 async+psycopg 3, Alembic/uv trong một backend. Npm/frontend lockfile giữ riêng; không thêm Python RPC service thứ hai. [03](03-target-architecture.md).
2. **Dùng SDK cho agent loop, không tự viết vòng model/tool mới.** App vẫn sở hữu auth, context policy, memory, quota, action approval, replay và recovery. SDK có khả năng approvals/state, nhưng baseline của app dùng read/proposal tools và domain API do người dùng kích hoạt. [OpenAI SDK](https://developers.openai.com/api/docs/guides/agents/sdk), [human review](https://developers.openai.com/api/docs/guides/agents/guardrails-approvals).
3. **Matching xác định được, độc lập AI.** Giữ công thức, round-half-up cuối, ngưỡng 30 và top 5. Tie-break hiện tại theo ID là baseline riêng có version; đổi sang ổn định theo ngày/cặp cần quyết định, không sửa âm thầm.
4. **Supabase Auth và Supabase PostgreSQL đã chốt.** Provider xử lý credentials; backend trusted password exchange→official getUser→opaque HttpOnly app session. Quyền/eligibility/consent/ownership tại domain services. SQLAlchemy async là DB abstraction duy nhất; Alembic và roles runtime/migration tách. Project credentials/region/hosting tương lai còn Q03.
5. **Không lưu transcript AI dài hạn mặc định.** Refresh trình duyệt trong phiên còn hạn có thể lấy lại context ở server RAM; restart có thể mất phiên. Chỉ memory đã được duyệt mới lưu lâu dài. `store:false` không tự giải quyết provider retention; privacy gate cần evidence theo tài khoản/endpoint. [Data controls](https://developers.openai.com/api/docs/guides/your-data).
6. **Giữ policy bảo thủ đang được mô tả.** C-AI/MEM/MATCH/VOICE độc lập; memory cần AI+MEM và duyệt từng mục; teen không publish/match/invite/chat/reveal; không dùng private chat/mood/memory cho matching; publish/revoke/linked-source invalidation đóng các dẫn xuất cũ.

## Ưu tiên và phạm vi

**P0:** contract dữ liệu và quyền; session/eligibility; consent version; ownership; SQL constraints/locks/idempotency; runtime giới hạn và output validation; raw-context TTL; không rò qua logs/exporter; revoke có hiệu lực trước cleanup; không mock fallback hoặc nhãn prototype/demo trong product UI. Privacy và report handling là điều kiện chạy với người thật, không để tới cuối mới thiết kế.

**P1:** đủ năm bot có vai trò rõ, mood/private CRUD, memory có duyệt, publish và matching thật, lời mời hai phía, chat/replay, block/report/reveal, delete/export đúng phạm vi; voice có consent được giữ là nghĩa vụ MVP thuật lại trong tài liệu nội bộ và phải xác minh Q01. Voice không chặn spike Mây đầu tiên, nhưng chưa làm voice thì không gọi MVP Must hoàn tất.

**P2/Future:** polish có đo đạc, hợp nhất token/CSS khi cần, semantic retrieval, multi-agent specialist, MCP ngoài, SDK sandbox/skills, proactive jobs và Shared Activities. ACT01 được bảo tồn làm test fixture, product entry ẩn/unavailable; không tự mở rộng thành feature production bắt buộc.

## Đường triển khai và bằng chứng cần có

Làm phase 0 trước để có baseline, contract và lệnh kiểm tra thống nhất; phase 1 dựng identity/consent/data; phase 2 chứng minh Mây thật toàn tuyến. Nhánh publish/matching có thể bắt đầu sau phase 1, song song nhánh AI. Các phase 3–7 hoàn thiện các lát chức năng; test/security tích lũy trong từng phase; phase 8–9 tổng kiểm/local rehearsal/cloud skeleton. [Roadmap chi tiết](07-implementation-roadmap.md) có task IDs, dependencies, test và fallback.

Demo thành công phải có thêm lỗi/retry/cancel/revoke/restart, hai browser account thật trong môi trường tổng hợp và database đối chiếu. Cần đo chất lượng AI theo baseline A/B/C, token/cost, latency, matching oracle, duplicate/replay và races. Demo với hồ sơ tổng hợp **không chứng minh** người thật sẽ hợp nhau hoặc friendship bền vững.

## Quyết định con người cần chốt

Q01: tài liệu sản phẩm gốc/phạm vi; Q02: model/processor và dữ liệu được phép; Q03: Supabase project/credentials/region và hosting tương lai; Q04: đã chốt24/10/2026 — năm sinh + xác nhận16 cho ứng dụng,18 cho kết nối; Q05: ý nghĩa kết thúc phiên/retention; Q06: taxonomy/tie-break/PD-05; Q07: vận hành report; Q08: ngân sách, ngưỡng chất lượng và lịch. Từng câu có owner, thời điểm chặn và default an toàn tại [10](10-decisions-and-open-questions.md). Không yêu cầu người dùng trả lời tất cả trước khi bắt đầu phần local đã rõ.
