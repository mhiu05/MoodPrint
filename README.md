# MoodPrint

MoodPrint giúp học sinh hiểu tình huống, ghi lại sự việc, chuẩn bị bước ứng phó, luyện cách nói và tìm người lớn đáng tin. React/Vite/TypeScript kết nối FastAPI, OpenAI Agents SDK và Supabase Auth/PostgreSQL/Storage. Demo độc lập vẫn dùng dữ liệu hư cấu trong trình duyệt; tài khoản thật dùng API và dữ liệu riêng theo người sở hữu.

Đây là bản tích hợp để phát triển và thử nghiệm bằng nội dung tổng hợp. Chưa có xác nhận an toàn độc lập cho học sinh thật, không phải dịch vụ tiếp nhận báo cáo của trường và không tự liên hệ bất kỳ ai. `PHASE_2`, `PHASE_3`, `G_INTEGRATION` vẫn `NOT_VERIFIED`; `Q3-03` vẫn `NOT_DEMONSTRATED`.

## Chạy tại máy

Yêu cầu Python 3.12, uv, Node.js 22.12+ và npm. Cài đúng lockfile:

```powershell
uv sync --all-packages --all-extras --locked
Set-Location frontend
npm ci
npm run dev
```

Vite đọc cấu hình `.env` ở root; chỉ các biến `VITE_PUBLIC_` được đưa vào frontend. Backend thông thường chạy bằng `uv run uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8000`. Backend có worker dọn evidence/khôi phục run và có thể gọi provider khi có key: chỉ chạy trên môi trường đã được phép. Không dùng key như một ủy quyền chi tiêu.

Audit project Supabase được chỉ định dùng [bộ chạy hosted synthetic](docs/quality/product-completion/hosted.md). Bộ này giữ Auth/DB/Storage thật, chỉ nhận hai user trong manifest, tắt maintenance toàn cục, chặn chi tiêu và dùng mô hình scripted. Không reset hay tự migrate hosted. Schema Phase 2/3 còn thiếu sẽ chặn các luồng tương ứng; xem [báo cáo sản phẩm](docs/implementation/reports/product-completion-review.md).

Chọn **Vào thử với tài khoản demo** để khám phá không cần backend. Companion kết nối bật khi `VITE_PUBLIC_AI_COMPANION=live` hoặc công tắc trình duyệt `moodprint:ai-companion=live`; mặc định hiện có vẫn được giữ. Voice là demo, không thu microphone hay phát giọng nói thật.

- [Đặc tả sản phẩm](docs/prototype/01-PRD.md)
- [Kế hoạch triển khai](docs/prototype/IMPLEMENTATION-EXECUTION.md)
- [Báo cáo và bằng chứng kiểm thử](docs/prototype/IMPLEMENTATION-REPORT.md)
- [Ảnh giao diện mobile/desktop](docs/prototype/screenshots/)

PRD và ảnh trong `docs/prototype/` mô tả baseline thiết kế ban đầu. Trạng thái tích hợp hiện tại xem [post-integration report](docs/implementation/reports/post-integration-quality-closure.md) và [product completion](docs/implementation/reports/product-completion-review.md). Hướng dẫn: [frontend](frontend/README.md), [backend](backend/README.md), [agent evals](agent/evals/README.md).

Kiểm tra: `uv run python scripts/check.py`, hai exporter với `--check`, và `npm run typecheck`, `lint`, `test`, `build`, `check:boundaries` trong frontend. `scripts/e2e_stack.py` chỉ nhận Supabase loopback cho regression local; hosted synthetic là đường riêng, không dùng bootstrap/reset local. Không deploy trong mission này.
