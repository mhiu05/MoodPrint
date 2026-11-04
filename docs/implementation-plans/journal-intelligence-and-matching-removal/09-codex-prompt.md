# Prompt cho Codex triển khai kế hoạch

Bạn đang nhận phiên **triển khai code** cho kế hoạch "Nhật ký thông minh, bỏ giao diện tìm bạn". Đây không phải phiên khảo sát hay viết lại kế hoạch. Làm hết phạm vi bên dưới theo đúng thứ tự task, không dừng ở việc đề xuất để người khác làm, và không xin xác nhận cho các bước thường lệ.

## 1. Workspace: đọc kỹ trước khi gõ lệnh

- Kế hoạch nằm ở `E:\MoodPrint\docs\implementation-plans\journal-intelligence-and-matching-removal\` (00–08 và file này), trên nhánh `test/04-11-26`.
- **Không sửa code trong `E:\MoodPrint`.** Nhánh `test/04-11-26` và `main` local chậm 132 commit so với `origin/main@565f5a74`: không có migration 0020–0028, không có `backend/app/ai/{skills,proactive,groups,orchestration,search}` (chỉ còn `__pycache__`). Mọi đường dẫn và số dòng trong kế hoạch là của `origin/main@565f5a74`.
- Làm theo JI-00 ở `06-verification-and-release.md`: từ `E:\MoodPrint` chạy `git fetch origin`, rồi `git worktree add -b feat/journal-intelligence E:\MoodPrint-journal-intelligence-exec origin/main`. Chép thư mục kế hoạch sang worktree mới, commit làm commit đầu tiên, và làm toàn bộ việc còn lại trong worktree đó. Nếu `origin/main` đã tiến xa hơn `565f5a74`, đối chiếu lại các file:dòng được trích trước khi sửa.
- Trong `E:\MoodPrint` không được đụng: `.gitignore` đang sửa dở, `stash@{0}` (5 file auth/landing của chủ dự án + báo cáo release), `backend/.env` (trỏ tới DB hosted và chứa key thật). Không đụng các worktree khác: `E:\MoodPrint-journal-intelligence`, `E:\MoodPrint-agent-platform-v3`, `E:\MoodPrint-proactive-phase1`, `E:\MoodPrint-proactive-phase2`, `.worktrees\*`, `.tmp\*`.
- Worktree mới **không có** `backend/.env`. Giữ nguyên như vậy.

## 2. Đọc trước, đọc đầy đủ

1. `00-overview.md` (Global Constraints, Review Focus, bảng kiểm chứng giả định, thứ tự và cut line), rồi `01` → `08` theo thứ tự.
2. `ARCHITECTURE.md`, `docs/development.md`, `docs/verification.md`, `docs/agents/*.md`, `docs/supabase/migrations.md`.
3. Mẫu sổ thực thi: `docs/implementation-plans/three-agent-orchestration-group-chat/12-execution-evidence.md`.
4. Code là căn cứ cuối cùng. Kế hoạch lệch với source thì: xác minh, sửa tài liệu kế hoạch trong worktree, ghi "ruling" vào `08-execution-ledger.md` (lệch gì, quyết định gì, vì sao), rồi làm tiếp.

## 3. Phạm vi

Làm **JI-00 → JI-50** theo thứ tự ở `00-overview.md`:

1. **Bắt buộc:** JI-00, JI-01, JI-02, JI-10, JI-11, JI-12, JI-13, JI-20, JI-21, JI-22, JI-23, JI-24. Chạy JI-10…JI-13 song song với JI-20 nếu công cụ cho phép.
2. **Checkpoint cut line A:** chạy đủ cổng JI-50 ở mức tối thiểu (cổng 1–10, 15), ghi ledger, commit. Sau checkpoint, nhánh phải ở trạng thái phát hành được nếu phiên dừng tại đây.
3. **Nhóm A:** JI-40 (thứ tự skill: `weekly-review`, `mood-patterns`, rồi `guided-journal`, `reframe-thought`).
4. **Checkpoint cut line B:** như checkpoint A.
5. **Nhóm B:** JI-30 + JI-31 (**một khối**: không để nhánh ở trạng thái có JI-30 mà thiếu JI-31), sau đó JI-25.
6. **JI-50 đầy đủ** (gồm SQL review 0029 pin trong `deploy/supabase/reviewed-sql/`, cập nhật mọi tài liệu liệt kê ở JI-50, review độc lập nếu công cụ có subagent).

**Không làm JI-51**: không migrate hosted, không deploy, không đổi runtime SSM, không đọc DB hosted kể cả chỉ đọc. Chỉ viết sẵn tài liệu và lệnh cho chủ dự án.

## 4. Quyết định mở: dùng khuyến nghị của kế hoạch

Chủ dự án chưa trả lời bảng OD ở `07`. Áp dụng khuyến nghị, ghi vào ledger, và làm sao cho việc đổi sau này rẻ:

- OD-01: 5 công tắc an toàn giữ `false`. OD-02: không đổi mặc định `AI_DAILY_BUDGET_USD`. OD-03: giữ router backend social/matching/activities mounted.
- OD-04: thông báo + công tắc opt-out (mặc định bật) ở mục Tài khoản; UI tách thành component riêng để gỡ được mà không đụng API.
- OD-05: giữ 90 ngày. OD-06: guest không có embedding/memory tự động. OD-07: sửa entry thì xóa memory tự động chưa sửa, giữ memory đã sửa; tắt công tắc thì giữ memory đã có, kèm nút xóa hàng loạt. OD-08: memory tự động chỉ cho `nhatky`. OD-10: backfill memory tự động 14 ngày. OD-13, OD-14: không đổi. OD-15: mâu thuẫn tường minh vẫn raise, mặc định thì clamp.
- OD-09: nếu stash của chủ dự án chưa được merge thì sửa copy `Auth.tsx`/`GuestEntry.tsx` trên nhánh mới như kế hoạch, và ghi rõ trong báo cáo cuối là sẽ có xung đột với stash.

## 5. Giới hạn tuyệt đối

- Không sửa `.gitignore`. Không đọc, in hay yêu cầu secret; không ghi secret, URL có mật khẩu, ID tài khoản thật hay nội dung nhật ký vào code, test, log hay tài liệu.
- Không gọi OpenAI, Voyage, Apify hay Google thật. JI-24 chỉ chạy `--embedder fake`; cổng 12 (chế độ Voyage) và cổng 13 (eval live) ghi "chưa chạy, chờ chủ dự án duyệt chi phí".
- Không dùng AWS CLI/SSM/MCP Supabase/MCP AWS. Không chạy `alembic upgrade` vào DB nào ngoài DB `_test` disposable. Alembic đọc `.env`, nên luôn đặt `DATABASE_MIGRATION_URL` local tường minh.
- DB test: chỉ `scripts/disposable_postgres.py --port 36432` (hoặc cổng trống khác) với DB tên kết thúc `_test`. Role cluster-wide tạo cho kiểm tra migration phải drop ngay sau đó. Không dừng hay xóa container không phải do bạn tạo.
- Git: được commit **cục bộ** trên `feat/journal-intelligence` theo bước commit của từng task. Không push, merge, rebase lên nhánh khác, reset hard hay revert commit của người khác.
- Không thêm hay nâng dependency (giữ `openai-agents==0.24.0`, lockfile hiện tại). Frontend không có React Testing Library; đừng thêm, mà làm theo cách kế hoạch mô tả (hàm thuần + Playwright).
- Không nới hay bỏ bất kỳ cổng authorization, consent, age 18+, quota, budget, timeout, idempotency, cancellation, recovery hay `journal-evidence-v1` nào để test xanh. Không sửa assertion không liên quan để qua test. Không thêm `skip`/`xfail` mới mà không ghi lý do vào ledger.
- Không đổi byte prompt đóng băng: `instructions()` của 5 trợ lý cũ (sha256 ghi ở ledger V3) và persona V3. Thay đổi prompt chỉ ở lớp runtime như kế hoạch nêu.
- Mọi thay đổi API đi qua `scripts/export_openapi.py` → `backend/openapi.json` → `npm.cmd run contracts:generate`. Không sửa tay `schema.d.ts`.

## 6. Cách làm từng task

1. Đọc mục task, phần Interfaces của task trước, và code thật ở các file:dòng được trích.
2. Viết test đỏ đúng tên và assertion trong kế hoạch, chạy, ghi kết quả đỏ (lệnh + dòng lỗi chính) vào ledger.
3. Cài đặt tối thiểu cho test xanh, chạy lại test của task và các test hồi quy được liệt kê.
4. Cập nhật tài liệu inventory nếu task thêm setting, bảng hay endpoint, chạy `check_docs.py`.
5. Commit với message ở bước Commit của task. Ghi ledger: commit hash, lệnh, số pass/fail/skip thật, thời lượng, các điểm lệch kế hoạch.

Dừng và hỏi chủ dự án **chỉ khi**: cần đổi schema ngoài đặc tả 0029; phải phá một bất biến không có trong kế hoạch; cần hành động phá hủy ngoài worktree; hoặc một OD ở mục 4 tỏ ra sai khi gặp code thật. Ghi câu hỏi vào ledger, làm tiếp những task không phụ thuộc.

## 7. Bẫy đã biết

- JI-01: chạy toàn suite **một lần** sau khi đổi mặc định và **trước** khi ghim nền, để có danh sách chính thức các test giả định cờ tắt. Đừng bỏ bước này.
- `tests/conftest.py` dùng `Settings(_env_file=None, …)`; `tests/test_live_observability.py:58` lại dùng `Settings()` (đọc `.env`). `chat_history_enabled` trong `ALL_FEATURES_OFF` phải là `True`.
- Hai field cờ mới (`journal_semantic_enabled`, `journal_auto_memory_enabled`) thêm ngay ở JI-01, vì test kiểm `len(FEATURE_FLAGS) == 28`.
- 0029 chứa cả schema memory tự động, kể cả khi chưa làm nhóm B. Offline SQL nhân đôi `%%`: dùng `quote_ident` như `0024_three_agent_groups.py:45-65`, không dùng `format()`. PowerShell 5.1 không có `utf8NoBOM`: ghi `0029-review.sql` không BOM như hướng dẫn ở 06, rồi kiểm sha bằng `check_reviewed_artifacts.py`.
- Không provider call nào được giữ owner lock: embed truy vấn trước khối `lock_actor`, embed document giữa hai transaction, đúng thứ tự khóa owner → job.
- Xóa entry phải dựa vào FK `ON DELETE CASCADE` (một điểm cho 5 đường xóa), không viết code xóa riêng ở từng route.
- `autoMemoryAvailable` luôn `false` cho tới JI-30. Memory tự động không được tăng `data_version`.
- Fullstack harness sở hữu cổng 8002/5174. Đừng sửa `frontend/` khi suite đang chạy: Vite HMR làm trang reload giữa test. Test deploy (`fcntl`) chỉ chạy trên Linux; trên Windows ghi "chưa chạy", không mock.
- `git diff --check` và quét secret (cổng 15) trước mỗi checkpoint.

## 8. Báo cáo cuối

Cập nhật `08-execution-ledger.md` trong worktree, rồi trả lời bằng tiếng Việt:

- Bảng task: trạng thái (xong / một phần / chưa làm), commit, test chính.
- Từng cổng JI-50: lệnh và số thật; cổng nào chưa chạy thì nói rõ vì sao.
- Danh sách test đã xóa, viết lại hoặc đổi assertion, mỗi mục một lý do.
- Mọi chỗ lệch kế hoạch và ruling; OD đã áp dụng; câu hỏi còn mở cho chủ dự án.
- Những gì chưa xác minh được (live provider, hosted, Linux deploy, chất lượng truy xuất thật).
- Không viết "sẵn sàng production" hay "đã đạt" cho điều chưa chạy.
