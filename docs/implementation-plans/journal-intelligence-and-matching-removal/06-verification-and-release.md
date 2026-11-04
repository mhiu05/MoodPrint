# 06 — Kiểm chứng, SQL review 0029, triển khai và demo

Task JI-00, JI-50, JI-51. JI-51 chỉ chạy khi chủ dự án duyệt rõ cửa sổ bảo trì và môi trường (OD-11).

## JI-00 — Worktree, DB disposable, baseline

**Mục tiêu:** Môi trường cô lập và số liệu baseline để phân biệt hồi quy với lỗi có sẵn.

- [ ] Làm trực tiếp trong `E:\MoodPrint`, nhánh `feat/journal-intelligence` (gốc `origin/main@565f5a74`). Cách chuyển workspace, kể cả giải phóng nhánh khỏi worktree tạm `E:\MoodPrint-journal-intelligence-exec` nếu còn, nằm ở [09-codex-prompt.md](09-codex-prompt.md) mục 1. `git status --short` phải sạch trước khi bắt đầu. Không `stash pop/drop` `stash@{0}` của chủ dự án; không sửa `.gitignore`; không đọc hay sửa `backend/.env` (DB hosted + key thật, xem 09 mục 2); không đụng các worktree V3/proactive.
- [ ] DB: `backend\.venv\Scripts\python.exe scripts\disposable_postgres.py --port 36432` (một container riêng; credential chỉ ghi vào `.tmp\moodprint-disposable-*\.env`, không in ra). Tạo DB `moodprint_ji_{unit,baseline,migration,fullstack,eval}_test`. Role cluster-wide (`moodprint_runtime`…) tạo cho kiểm tra migration phải drop sau đó, nếu không `tests/test_runtime_provision.py` sẽ hỏng (ghi chép hạ tầng test của dự án).
- [ ] Workspace thực thi `E:\MoodPrint` có `backend/.env` production theo bàn giao: tuyệt đối không đọc/sửa/xóa/đổi tên. Chỉ snapshot baseline riêng không chứa file này. Pytest và mọi entrypoint synthetic phải tắt dotenv trước khi tạo Settings; không làm workspace “sạch” bằng cách đụng file bí mật hoặc thay đổi sẵn của chủ dự án.
- [ ] Baseline (ghi vào [08](08-execution-ledger.md)): `uv sync --locked`; `npm.cmd ci`; `uv run --locked ruff check app tests evals alembic`; `uv run --locked mypy app`; `$env:TEST_DATABASE_URL=…moodprint_ji_baseline_test; uv run --locked pytest -q`; `npm.cmd run typecheck; npm.cmd test; npm.cmd run build`; e2e owned. Mọi fail ở baseline được phân loại "có sẵn" kèm nguyên nhân. Trên `origin/main@565f5a74`, CI ghi 1965 passed/4 skipped (theo báo cáo `11-live-release.md` trong stash, chưa xác minh lại).

## JI-50 — Cổng kiểm tra trước khi coi là xong

Mọi lệnh Alembic bên dưới phải chạy với URL disposable local `_test` đặt tường minh **ngay trong cùng lệnh/process**, ví dụ `if (-not $env:TEST_DATABASE_URL) { throw 'Set the owned local test database first' }; $env:DATABASE_MIGRATION_URL=$env:TEST_DATABASE_URL; uv run --locked alembic check`. Không lấy URL từ `backend/.env`; không dựa riêng vào remote-host guard. Driver phiên thực thi còn tắt dotenv trước import Alembic.

**Mục tiêu:** Bằng chứng đầy đủ, ghi trong ledger, trước khi xin duyệt triển khai.

| # | Cổng | Lệnh (PowerShell) | Đạt khi |
| --- | --- | --- | --- |
| 1 | Lint/type | `uv run --locked ruff check app tests evals alembic ../scripts/apply_supabase_review.py ../scripts/check_reviewed_artifacts.py`; `uv run --locked mypy app` | 0 lỗi |
| 2 | Backend đầy đủ | `uv run --locked pytest -q` (DB `_unit_test`) | không fail mới so với baseline |
| 3 | Mặc định thuần | `uv run --locked pytest -q tests/test_default_flags.py` | pass (gồm khởi động app, admin 403, search đóng) |
| 4 | Migration | DB trắng: `alembic upgrade head` → `0029_journal_intelligence (head)`; `alembic check`; `tests/test_journal_intelligence_migration.py` | pass |
| 5 | SQL review 0029 | xem mục dưới; `uv run --project backend --locked python scripts/check_reviewed_artifacts.py`; `pytest -q tests/test_reviewed_artifacts.py` | PASS; sha khớp offline export |
| 6 | Hợp đồng | `uv run --locked python ../scripts/export_openapi.py`; `npm.cmd run contracts:generate`; `git diff --exit-code -- backend/openapi.json frontend/src/api/generated/schema.d.ts` sau commit | không drift |
| 7 | Tài liệu | `uv run --project backend --locked python scripts/check_docs.py` | PASS (bảng, setting, endpoint mới đã có trong inventory) |
| 8 | Frontend | `npm.cmd run typecheck; npm.cmd test; npm.cmd run build` | pass; ghi số test trước/sau JI-10 |
| 9 | E2E fixture | `npx.cmd playwright test --config playwright.owned.config.ts --reporter=list --output "$env:TEMP\ji-e2e"` | pass |
| 10 | Fullstack | mục 6 `docs/development.md` với `moodprint_ji_fullstack_test`; thêm spec mới `frontend/tests/fullstack/journal-intelligence.spec.ts`: lưu 3 entry → chờ worker (FakeEmbedder qua `app.state.journal_embedder` trong `e2e_server.py`) → hỏi diễn đạt khác → link trích dẫn đúng entry → xóa entry → `GET /journal/ai-settings` `indexedEntries` giảm 1 → hỏi lại không còn link đó | pass |
| 11 | Deploy (Linux) | `deploy/aws/tests` bằng image Python Linux mount read-only (cách ở `docs/verification.md`) | pass (Windows thiếu `fcntl`: không mock) |
| 12 | Đo truy xuất | Từ backend: `uv run --locked python -m evals.journal_retrieval.run --embedder fake --out ../.tmp/journal-retrieval`; tùy chọn `--embedder voyage --confirm-cost` khi chủ dự án cho phép | số thật vào ledger |
| 13 | Eval live skill/memory (tùy chọn) | theo `docs/agents/evaluation.md`, chỉ `gpt-6-luna`, trần chi phí do chủ dự án duyệt (ghi chép trước: ~3 USD cho đợt eval) | rubric: có căn cứ, không chẩn đoán, trích đúng |
| 14 | Review độc lập | 1 reviewer (subagent) đọc diff 0029 + `indexing.py` + `journal_memory.py` theo [00](00-overview.md) Review Focus | không P0/P1 mở |
| 15 | Khác | `git diff --check`; `rg -n "sk-|VOYAGE_API_KEY=|postgresql://[^ ]+:[^ ]+@" docs backend/tests frontend/tests` không có secret | sạch |

Tài liệu cập nhật trong JI-50: `ARCHITECTURE.md` (§1 bỏ "hồ sơ tìm bạn, lời mời, nhắn tin, hoạt động chung" khỏi phạm vi UI và ghi backend còn giữ; §5 memory tự động; §6 ghi UI đã gỡ), `PRODUCT.md`, `README.md`, `docs/agents/README.md` (bảng 5 bot đã cũ, thêm 3 agent + skill), `docs/agents/context-memory.md`, `docs/agents/runtime.md` (tool journal lai), `docs/backend/configuration.md`, `docs/backend/api-reference.md`, `docs/supabase/schema.md`, `docs/supabase/migrations.md` (mục 0029), `docs/verification.md` (kết quả lần này).

### SQL review 0029 (theo quy trình 0019)

1. Đặt URL local cùng lệnh: `if (-not $env:TEST_DATABASE_URL) { throw 'Set the owned local test database first' }; $env:DATABASE_MIGRATION_URL=$env:TEST_DATABASE_URL; uv run --locked alembic upgrade 0028_collaboration_defaults:0029_journal_intelligence --sql | Out-File -Encoding utf8NoBOM deploy\supabase\reviewed-sql\0029-review.sql`. Không sửa tay. `.gitattributes` đã tắt chuyển newline cho `*.sql` ở thư mục này. Trên PowerShell 5.1, `utf8NoBOM` không có; dùng `[IO.File]::WriteAllText(path, (… | Out-String), [Text.UTF8Encoding]::new($false))` hoặc subprocess ghi stdout UTF-8 không BOM. Không chuyển chuỗi credential giữa các shell.
2. Thêm vào `MANIFEST.json`: `{"path":"0029-review.sql","sha256":…,"bytes":…,"generatedFrom":{"commit":<sha commit chứa migration>,"command":"alembic upgrade 0028_collaboration_defaults:0029_journal_intelligence --sql"}}`, theo đúng dạng mục 0019.
3. `scripts/apply_supabase_review.py`: `UPGRADES["0029"] = UpgradePlan(REVIEWED_SQL / "0029-review.sql", REPORTS / "0029-execution.json", "0028_collaboration_defaults", "0029_journal_intelligence", tables=("journal_ai_settings","journal_entry_embeddings","journal_ai_jobs"))`. Kiểm `upgrade_checks` (dòng 233-318) có xác minh RLS/grant runtime cho `tables` và đếm hàng hiện có không đổi.
4. Diễn tập: restore `pg_dump --schema=moodprint` của hosted (chủ dự án cung cấp, mã hóa như các bản trước) vào DB `_test` local có role giống hosted (`moodprint_app` là thành viên `moodprint_runtime`), chạy `apply_supabase_review.py --upgrade 0029` ở chế độ local, rồi `alembic check`. Drop role sau đó.
5. Không bao giờ dùng `alembic upgrade` online hay `apply_migration` của MCP lên hosted.

## JI-51 — Triển khai và demo

**Mục tiêu:** Đưa lên môi trường demo trong một cửa sổ bảo trì có đường lui, rồi chạy checklist demo.

### Trạng thái hosted cần xác minh trước (chỉ đọc)

Tài liệu mâu thuẫn (xem [00](00-overview.md)). Trước mọi bước, chủ dự án hoặc agent được phép chạy **chỉ đọc**: `select version_num from moodprint.alembic_version` (qua công cụ đọc đã dùng trước đây, không ghi). Kỳ vọng `0028_collaboration_defaults`. Nếu khác 0028 thì **dừng**: kế hoạch này giả định 0028.

Đồng thời kiểm (chỉ tên key, không giá trị) runtime SecureString `/moodprint/staging/runtime` có `OPENAI_API_KEY`, `OPENAI_MODEL`, `VOYAGE_API_KEY`, `AI_ACCOUNTING_ENABLED=true`, `AI_DAILY_BUDGET_USD>0`. Thiếu `VOYAGE_API_KEY` thì demo vẫn chạy nhưng truy xuất ở chế độ từ khóa (OD-12).

### Hai phương án môi trường demo

| | A. Hosted (`moodprint.duckdns.org`) | B. Local fullstack |
| --- | --- | --- |
| Khi nào | Còn ≥ 2 ngày trước demo và chủ dự án duyệt cửa sổ bảo trì | Không kịp, hoặc migrate hosted thất bại |
| Dữ liệu | Tài khoản demo đã đăng ký (18+) trên hosted | DB disposable, actor seed, key thật trong env của phiên |
| Rủi ro | Cửa sổ bảo trì, rollback image | Không phải môi trường thật; Supabase Auth local giả |

Khuyến nghị: **A**, chuẩn bị sẵn **B** làm dự phòng.

### Thứ tự an toàn cho A (migrate trước, cờ sau)

Vì image tính năng ánh xạ cột 0029 mà image hiện tại chỉ chấp nhận 0028 (`core/revisions.py`), làm theo tiền lệ 0018/0019 ("image tương thích chấp nhận cả hai revision", `ARCHITECTURE.md` §8):

1. **Image tương thích C**: `origin/main@565f5a74` + chỉ đổi `READY_REVISIONS = ("0028_collaboration_defaults", "0029_journal_intelligence")` và docstring, kèm test `test_ready_window_accepts_0028_and_0029`. Đi qua CI exact-main → publish → poller như thường lệ. Image cũ (ORM 0028) chạy được trên schema 0029 vì 0029 chỉ thêm: cột mới có default, `proposal_id` nới nullable, CHECK `origin` rộng hơn. Xác minh `/health/ready` 200.
2. Backup: `pg_dump --schema=moodprint` mã hóa (DPAPI như bản trước) + snapshot đếm hàng (nội dung-free).
3. `release_gate.py enable`; tạm dừng timer poller.
4. Áp `0029-review.sql`: `apply_supabase_review.py --upgrade 0029 --approved-sha256 <sha đã pin> --apply` (một transaction). C vẫn ready.
5. Cấu hình runtime: **không cần thêm key** cho cờ mới (mặc định true). Đặt tường minh `JOURNAL_AUTO_MEMORY_ENABLED=false` nếu nhóm B bị cắt hoặc chưa muốn bật trên hosted. Giữ nguyên mọi key hiện có.
6. Deploy **image tính năng F** (READY = 0029). Đọc log `feature_degraded` (JI-02): danh sách phải đúng như kỳ vọng; có `ai_enabled` trong đó thì **dừng và rollback**.
7. Smoke (danh sách dưới) với token cổng bảo trì.
8. Theo dõi backfill: log `journal_index_queue` giảm về 0; `GET /journal/ai-settings` của tài khoản demo có `pendingEntries=0`.
9. `release_gate.py disable`; bật lại timer poller.

**Rollback:** F → C (C chấp nhận 0029). Tắt nhanh mà không đổi image: `JOURNAL_SEMANTIC_ENABLED=false`, `JOURNAL_AUTO_MEMORY_ENABLED=false` rồi recreate container. **Không** quay về image trước C sau khi đã áp 0029 (sẽ 503 NOT_READY). Downgrade SQL chỉ dùng khi chưa có hàng `journal_auto`/`origin='journal'`.

### Checklist trước demo (T−1 ngày và T−1 giờ, ghi kết quả vào ledger)

- [ ] `/api/v1/health/ready` 200; revision 0029; 4 service healthy, 0 restart.
- [ ] Session tài khoản demo: `features.ai`, `threeAgents`, `smartOrchestration`, `groupChat`, `agentSkills`, `proactive` đều true; nav chỉ có Trợ lý · Nhật ký · Tài khoản; `/#/connect` chuyển về `/#/assistants`.
- [ ] **Điều phối:** "Tuần này mình rối quá, giúp mình sắp xếp" → trả lời có bước; nếu có consult Nhật ký thì dòng phối hợp hiện từ receipt.
- [ ] **Nhật ký:** 3 entry demo viết sẵn với cách diễn đạt khác nhau, đợi ≥ 30 s; hỏi bằng từ đồng nghĩa ("dạo này mình kiệt sức vì gì?") → câu trả lời có "Bài viết đã tham khảo:" với link đúng entry; log `metric=journal_retrieval mode=hybrid`.
- [ ] **Hoạt động:** "5 phút, chỉ có giấy bút" → một thử thách một người, không có lời mời/kết nối.
- [ ] **Skill:** chọn "Nhìn lại tuần" trong Nhật ký → đọc 7 ngày, có trích dẫn; trong Hoạt động skill bị disabled kèm lý do.
- [ ] **Check-in chủ động:** lịch của tài khoản demo đã có tin trong inbox (slot sáng 05:00–11:30 hoặc tối 17:00–22:30); không ép tạo job trên prod (theo `deploy/aws/proactive-qa.md`).
- [ ] **Group chat:** nhóm Điều phối + Nhật ký + Hoạt động, `@Nhật ký` → đúng người nói.
- [ ] **Xóa entry ⇒ embedding biến mất:** ghi `indexedEntries` (N) → xóa một entry → `indexedEntries = N−1` ngay lập tức (cascade cùng transaction) → hỏi lại không còn link entry đó. Nếu được phép, chủ dự án chạy truy vấn đếm chỉ đọc `select count(*) from moodprint.journal_entry_embeddings where entry_id = :id` → 0.
- [ ] **Sửa entry:** sửa một entry → `indexedEntries` giảm 1 rồi trở lại sau ~20 s; (nhóm B) memory tự động chưa sửa của entry đó biến mất rồi có thể được tạo lại.
- [ ] **Memory (nhóm B):** màn Ghi nhớ có nhãn "Tự động từ nhật ký" + link trang; sửa/xóa được.
- [ ] **Công tắc:** tắt "Tìm theo ý nghĩa" → hỏi lại ⇒ vẫn trả lời (từ khóa); bật lại ⇒ backfill.
- [ ] **Chi phí:** tổng `ai_usage` ước tính hôm nay < 50 % `AI_DAILY_BUDGET_USD`.

### Dự phòng khi demo

| Sự cố | Phản ứng |
| --- | --- |
| Voyage lỗi/chậm | Tự động: tool trả kết quả từ khóa + gần nhất (`reason=provider_unavailable/timeout`), lượt không fail. Muốn ổn định trước demo: `JOURNAL_SEMANTIC_ENABLED=false` + recreate (khoảng 1 phút; vector **không** bị xóa, bật lại dùng tiếp). **Đừng** dùng công tắc người dùng cho việc này: nó xóa vector và phải backfill lại |
| OpenAI lỗi/chậm | UI báo không khả dụng theo `aiServiceMessage`; demo tiếp phần nhật ký/lịch/ghi nhớ (không cần AI); phát bản ghi màn hình các luồng agent đã quay ở T−1 ngày |
| Hết ngân sách ngày | Chủ dự án tăng tạm `AI_DAILY_BUDGET_USD` (trần cứng USD 20 trong `reserve_accounting`, `accounting.py:108`) hoặc dùng tài khoản/ngày khác. Kiểm trước ở checklist |
| Check-in không đến đúng giờ | Mở tin đã giao sẵn trong inbox |
| Migrate 0029 thất bại | Transaction rollback; ở lại image C trên 0028 (C chấp nhận 0028); chuyển sang phương án B |
| Image F không ready | Rollback F → C trong cổng bảo trì |
