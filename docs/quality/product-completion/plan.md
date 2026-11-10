# Kế hoạch hoàn thiện sản phẩm

Ngày 10/11/2026. Đặc tả ràng buộc: yêu cầu Product Completion của owner trong phiên này. Owner đã giao thực thi tự chủ, không cần vòng duyệt thiết kế mới. Giữ React/Vite, FastAPI, Agents SDK, Supabase; giữ Action Plan trong hồ sơ. Không deploy, không đổi phase gate, không sửa `.env`/`.gitignore`, không migration hosted, không nghiên cứu RAG.

## Chu kỳ 1 — Khám phá và sửa chức năng

- [x] Xác nhận worktree, nhánh, HEAD/upstream `e02abdfab5221ffc7b620104194387ab15e6feb1`, cây sạch.
- [x] Kiểm tra metadata không lộ secret: API/Auth và username DB cùng project `xhlshihobyxrgfqrdafh`; role `moodprint_api`; RLS trên bảng nghiệp vụ.
- [x] Chạy Vite/FastAPI tại máy, audit bằng browser và lập inventory theo kết quả quan sát.
- [x] Tạo bộ chạy hosted riêng, không tái sử dụng bootstrap/reset local; chỉ hai tài khoản synthetic, ghi manifest và dọn theo ID chính xác.
- [x] Reproduce lỗi trước khi sửa; viết regression cho lỗi hành vi ở chat/roleplay/cross-feature; kiểm tra persistence và A/B.

## Chu kỳ 2 — Companion và trải nghiệm

- [x] Kiểm tra prompt/context/tools/approval/memory/roleplay, chạy harness scripted hiện có và matrix 20 tình huống tiếng Việt.
- [x] Sửa lỗi tạo/khôi phục hội thoại, điều hướng ngữ cảnh, roleplay lifecycle, loading/error/retry nếu tái hiện được; không giả lập kết quả live.
- [x] Audit 7 viewport 320×720, 360×800, 390×844, 430×932, 768×1024, 1024×768, 1440×900; axe, keyboard, reduced motion, zoom.
- [x] Cập nhật README và mô tả sản phẩm cũ gây hiểu nhầm.

## Chu kỳ 3 — Regression và bàn giao

- [x] Python checks/contract/OpenAPI, frontend type/lint/unit/build/boundary/format, demo E2E, hosted synthetic journeys và local-stack regression nếu môi trường có sẵn.
- [x] Review độc lập toàn diff, sửa finding nghiêm trọng và chạy lại kiểm tra liên quan.
- [ ] Báo cáo đầy đủ có bằng chứng/giới hạn, commit, push thường cùng nhánh, kiểm tra remote SHA và CI cuối.

## Các quyết định và rủi ro cần kiểm chứng

- Hosted chưa có schema `knowledge` (metadata chỉ đọc). Dừng riêng việc thay schema; ghi exact migration gap, không dùng fixture để tuyên bố Knowledge Hub thật hoạt động.
- OpenAI authorization gốc tại worktree `agent-companin/.local` có ceiling 900; báo cáo trước ghi hết 900/900. Không mở paid client trong audit, không tạo budget mới. Live quality là NOT_RUN cho đến khi gate hợp lệ.
- Backend bình thường chạy purge/reconcile toàn cục; hosted audit seam tắt các worker này trước lifespan để không thay đổi bản ghi chưa biết.
- Kiểm tra đặc biệt: double-submit, lỗi tạo hội thoại, session roleplay cũ, reload trong approval, màn nhỏ với composer và nội dung dài, không coi cache là DB persistence.

## Sổ thực thi

- Khởi đầu: Node 24.13.0/npm 11.6.2; locked uv sync exit 0; npm ci exit 0 (7 moderate dependency advisories, chưa tự cập nhật).
- Read-only Auth: settings/JWKS HTTP 200; signup bật, xác nhận email bật, anonymous tắt. Chưa gửi email hay tạo tài khoản trong bước kiểm tra này.
