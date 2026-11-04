# Prompt cho Codex triển khai kế hoạch (làm việc trong E:\MoodPrint)

Bạn đang nhận phiên **triển khai code** cho kế hoạch "Nhật ký thông minh, bỏ giao diện tìm bạn". Đây không phải phiên khảo sát hay viết lại kế hoạch. Làm hết phạm vi bên dưới theo đúng thứ tự task, không dừng ở việc đề xuất để người khác làm, và không xin xác nhận cho các bước thường lệ.

## 1. Chuyển workspace về nhánh `feat/journal-intelligence` (làm trước mọi việc khác)

Thư mục làm việc **duy nhất** là `E:\MoodPrint`, nhánh `feat/journal-intelligence`. Nguồn chuẩn của nhánh là **`origin/feat/journal-intelligence`**: `origin/main@565f5a74` + commit tài liệu `74901185` + commit cập nhật prompt này. Nhánh local có thể vẫn dừng ở `74901185`. Làm đúng thứ tự dưới đây; bất kỳ kiểm tra nào lệch thì dừng và báo, không tự "sửa cho khớp" bằng lệnh phá hủy.

1. `Set-Location E:\MoodPrint; git fetch origin; git branch --show-current; git status --short`. Kỳ vọng đang ở `main`, cây sạch. Có thay đổi lạ thì dừng và hỏi. **Không** `stash pop/drop/apply` `stash@{0}` (5 file auth/landing của chủ dự án).
2. `git worktree list`. Nếu `feat/journal-intelligence` đang được checkout ở `E:\MoodPrint-journal-intelligence-exec` (do phiên trước tạo), phải giải phóng nó trước:
   - Xác nhận không còn tiến trình nào (test, dev server, phiên agent khác) đang chạy trong thư mục đó. Không chắc thì hỏi chủ dự án; không kill tiến trình mình không tạo.
   - Tạo `E:\MoodPrint\.tmp\exec-worktree-<yyyyMMdd-HHmm>\` (gọi là `$B`). Trong worktree đó: `git status --short`. Đã có commit local mới hơn `74901185` thì dừng và báo: không tự rebase hay push. File **tracked** đã sửa (ví dụ `08-execution-ledger.md` có kết quả baseline thật): **không commit**; lưu `git diff > $B\tracked.patch`, kiểm patch khác rỗng, rồi `git restore -- <các đường dẫn đó>`. Lý do: nhánh local phải fast-forward được lên `origin/feat/journal-intelligence`.
   - Di chuyển dữ liệu chưa theo dõi cần giữ vào `$B`: `frontend\evidence\*` mới sinh và thư mục credential DB disposable `.tmp\moodprint-disposable-*` (nếu có). Không in nội dung file credential. Không commit evidence.
   - `git worktree remove E:\MoodPrint-journal-intelligence-exec` **không** `--force`. Git từ chối thì dừng và báo lý do.
   - Không đụng worktree `E:\MoodPrint-journal-intelligence` (nhánh `docs/journal-intelligence-plan`) cũng như các worktree khác.
3. Trong `E:\MoodPrint`: `git switch feat/journal-intelligence; git pull --ff-only origin feat/journal-intelligence`. Kiểm: `git rev-parse HEAD` bằng `git rev-parse origin/feat/journal-intelligence`; `git merge-base --is-ancestor 565f5a74 HEAD` thành công; `Test-Path backend\app\ai\skills\registry.py`; `Test-Path backend\alembic\versions\0028_collaboration_defaults.py`; thư mục `docs\implementation-plans\journal-intelligence-and-matching-removal\` có 00–09, và file `09-codex-prompt.md` có tiêu đề "(làm việc trong E:\MoodPrint)".
4. Có `$B\tracked.patch` thì `git apply --check` rồi `git apply`. Cập nhật bảng đầu `08-execution-ledger.md`: nhánh `feat/journal-intelligence`, workspace `E:\MoodPrint`, gốc `origin/main@565f5a74`, worktree tạm đã gỡ. Commit `docs: record JI-00 baseline and move execution to E:\MoodPrint` (chỉ các file tài liệu). Patch không apply được thì dừng và báo; không sửa tay cho khớp. `00-overview.md` và `06-verification-and-release.md` đã được cập nhật cho workspace này trong commit trên origin; không cần sửa.

## 2. `backend/.env` trong E:\MoodPrint: chỉ đọc là đủ hỏng

`E:\MoodPrint\backend\.env` trỏ tới **DB hosted (production)** và chứa key OpenAI/Voyage thật. Không đọc, in, sửa, đổi tên hay xóa file này. Quy tắc bắt buộc:

- Pytest an toàn nhờ `pytest_configure` (`backend/tests/conftest.py:27-55`), vốn xóa URL/key và đặt `Settings.model_config["env_file"] = None`. Không được làm yếu khối này.
- Alembic đọc `.env`. **Mọi** lệnh alembic phải đặt `$env:DATABASE_MIGRATION_URL` tới DB `_test` local ngay trong cùng lệnh. `env.py` từ chối host remote, nhưng không được dựa vào lớp chặn đó.
- `scripts/check_config.py` mặc định đọc `backend/.env`: luôn chạy với `--env-file E:\MoodPrint\.tmp\empty.env` (file rỗng do bạn tạo).
- Không chạy `uv run python -m app`, `scripts/test_supabase_fullstack.py`, `scripts/smoke_providers.py`, `scripts/verify_local_providers.py`, `scripts/run_live_browser.py` hay `tests/live/*`. Script mới (ví dụ `evals/journal_retrieval/run.py`) phải tạo `Settings(_env_file=None, …)`.
- Fullstack harness (`scripts/test_fullstack.py`, `tests/e2e_server.py`) đã dùng `_env_file=None`; giữ nguyên.

## 3. Đọc trước, đọc đầy đủ

1. `00-overview.md` (Global Constraints, Review Focus, bảng kiểm chứng giả định, thứ tự và cut line), rồi `01` → `08`.
2. `ARCHITECTURE.md`, `docs/development.md`, `docs/verification.md`, `docs/agents/*.md`, `docs/supabase/migrations.md`.
3. Mẫu sổ thực thi: `docs/implementation-plans/three-agent-orchestration-group-chat/12-execution-evidence.md`.
4. Code là căn cứ cuối cùng. Kế hoạch lệch với source thì: xác minh, sửa tài liệu kế hoạch, ghi "ruling" vào `08-execution-ledger.md` (lệch gì, quyết định gì, vì sao), rồi làm tiếp.

## 4. Phạm vi

Làm **JI-00 → JI-50** theo thứ tự ở `00-overview.md`. Phần JI-00 đã có trong ledger (nếu phiên trước đã chạy) chỉ cần kiểm lại trên workspace mới, không chạy lại toàn bộ nếu commit gốc không đổi.

1. **Bắt buộc:** JI-00, JI-01, JI-02, JI-10, JI-11, JI-12, JI-13, JI-20, JI-21, JI-22, JI-23, JI-24.
2. **Checkpoint cut line A:** chạy cổng JI-50 tối thiểu (1–10, 15), ghi ledger, commit. Nhánh phải phát hành được nếu phiên dừng tại đây.
3. **Nhóm A:** JI-40 (thứ tự skill: `weekly-review`, `mood-patterns`, `guided-journal`, `reframe-thought`).
4. **Checkpoint cut line B:** như checkpoint A.
5. **Nhóm B:** JI-30 + JI-31 (**một khối**: không để nhánh có JI-30 mà thiếu JI-31), sau đó JI-25.
6. **JI-50 đầy đủ:** SQL review 0029 pin trong `deploy/supabase/reviewed-sql/`, cập nhật mọi tài liệu liệt kê ở JI-50, review độc lập nếu công cụ có subagent.

**Không làm JI-51**: không migrate hosted, không deploy, không đổi runtime SSM, không đọc DB hosted kể cả chỉ đọc. Chỉ viết sẵn tài liệu và lệnh cho chủ dự án.

## 5. Quyết định mở: dùng khuyến nghị của kế hoạch

Chủ dự án chưa trả lời bảng OD ở `07`. Áp dụng khuyến nghị, ghi vào ledger, và làm sao cho việc đổi sau này rẻ:

- OD-01: 5 công tắc an toàn giữ `false`. OD-02: không đổi mặc định `AI_DAILY_BUDGET_USD`. OD-03: giữ router backend social/matching/activities mounted.
- OD-04: thông báo + công tắc opt-out (mặc định bật) ở mục Tài khoản; UI là component riêng, gỡ được mà không đụng API.
- OD-05: giữ 90 ngày. OD-06: guest không có embedding/memory tự động. OD-07: sửa entry thì xóa memory tự động chưa sửa, giữ memory đã sửa; tắt công tắc thì giữ memory đã có, kèm nút xóa hàng loạt. OD-08: memory tự động chỉ cho `nhatky`. OD-10: backfill memory tự động 14 ngày. OD-13, OD-14: không đổi. OD-15: mâu thuẫn tường minh vẫn raise, mặc định thì clamp.
- OD-09: sửa copy `Auth.tsx`/`GuestEntry.tsx` như kế hoạch; ghi rõ trong báo cáo cuối là sẽ xung đột với `stash@{0}` của chủ dự án.

## 6. Giới hạn tuyệt đối

- Không sửa `.gitignore`. Không đọc, in hay yêu cầu secret; không ghi secret, URL có mật khẩu, ID tài khoản thật hay nội dung nhật ký vào code, test, log hay tài liệu.
- Không gọi OpenAI, Voyage, Apify hay Google thật. JI-24 chỉ chạy `--embedder fake`; cổng 12 (Voyage) và 13 (eval live) ghi "chưa chạy, chờ chủ dự án duyệt chi phí".
- Không dùng AWS CLI/SSM/MCP Supabase/MCP AWS.
- DB test: chỉ `scripts/disposable_postgres.py --port 36432` (hoặc cổng trống khác), hoặc container đã chuyển credential ở bước 1.2, với DB tên kết thúc `_test`. Role cluster-wide tạo cho kiểm tra migration phải drop ngay sau đó. Không dừng hay xóa container không phải do phiên này (hoặc phiên trước của kế hoạch này) tạo.
- Git: commit cục bộ trên `feat/journal-intelligence` theo bước commit của từng task. Được `git push origin feat/journal-intelligence` **chỉ** tại checkpoint A, checkpoint B và khi kết thúc, sau khi các cổng của checkpoint đã xanh. Không force-push, không push nhánh khác, không merge vào `main`, không mở PR, không reset hard, không revert commit của người khác.
- Không thêm hay nâng dependency (giữ `openai-agents==0.24.0`, lockfile hiện tại). Frontend không có React Testing Library; đừng thêm, mà làm theo cách kế hoạch mô tả (hàm thuần + Playwright).
- Không nới hay bỏ cổng authorization, consent, age 18+, quota, budget, timeout, idempotency, cancellation, recovery hay `journal-evidence-v1` nào để test xanh. Không sửa assertion không liên quan. Không thêm `skip`/`xfail` mới mà không ghi lý do vào ledger.
- Không đổi byte prompt đóng băng: `instructions()` của 5 trợ lý cũ (sha256 ghi ở ledger V3) và persona V3. Prompt chỉ đổi ở lớp runtime như kế hoạch nêu.
- Mọi thay đổi API đi qua `scripts/export_openapi.py` → `backend/openapi.json` → `npm.cmd run contracts:generate`. Không sửa tay `schema.d.ts`.

## 7. Cách làm từng task

1. Đọc mục task, phần Interfaces của task trước, và code thật ở các file:dòng được trích.
2. Viết test đỏ đúng tên và assertion trong kế hoạch, chạy, ghi kết quả đỏ (lệnh + dòng lỗi chính) vào ledger.
3. Cài đặt tối thiểu cho test xanh, chạy lại test của task và các test hồi quy được liệt kê.
4. Cập nhật tài liệu inventory nếu task thêm setting, bảng hay endpoint, chạy `check_docs.py`.
5. Commit với message ở bước Commit của task. Ghi ledger: commit hash, lệnh, số pass/fail/skip thật, thời lượng, điểm lệch kế hoạch.

Dừng và hỏi chủ dự án **chỉ khi**: cần đổi schema ngoài đặc tả 0029; phải phá một bất biến không có trong kế hoạch; cần hành động phá hủy ngoài nhánh này; hoặc một OD ở mục 5 tỏ ra sai khi gặp code thật. Ghi câu hỏi vào ledger, làm tiếp những task không phụ thuộc.

## 8. Bẫy đã biết

- **Sửa kế hoạch JI-01 trước khi làm (ruling bắt buộc):** `pytest_configure` đặt env `AI_ENABLED`, `AI_WEB_SEARCH_ENABLED`, `AI_MAPS_SEARCH_ENABLED`, `AI_AGENT_SKILLS_ENABLED`, `AI_COLLABORATION_DEFAULTS_ENABLED`, `MAPS_SEARCH_WORKER_ENABLED`, `STT_ENABLED`, `SEMANTIC_MEMORY_ENABLED` = `false` cho **mọi** test. Biến env thắng mặc định của field, nên `Settings(_env_file=None)` trong pytest không thấy mặc định thật. Vì vậy:
  - Mọi test kiểm mặc định (`test_default_flags.py`, ca `PROD` của JI-02, fixture `clients_defaults`) phải `monkeypatch.delenv(name.upper(), raising=False)` cho mọi tên trong `FEATURE_FLAGS` (và URL/key liên quan) trước khi tạo `Settings`.
  - Giữ khối env trong `conftest.py`, chỉ được mở rộng. Có thể bổ sung các cờ còn lại vào khối env này thay cho, hoặc cùng với, `ALL_FEATURES_OFF` trong fixture; ghi lựa chọn vào ledger.
  - Red run của JI-01 (chạy toàn suite sau khi đổi mặc định, trước khi ghim nền) vẫn bắt buộc. Danh sách test fail là danh sách chính thức các test giả định cờ tắt.
- `tests/test_live_observability.py:58` dùng `Settings()`. Trong pytest, `env_file` đã là `None`, nhưng vẫn phải xử lý theo bảng JI-01. `chat_history_enabled` trong nền "tắt hết" phải là `True`.
- Hai field cờ mới (`journal_semantic_enabled`, `journal_auto_memory_enabled`) thêm ngay ở JI-01, vì test kiểm `len(FEATURE_FLAGS) == 28`.
- 0029 chứa cả schema memory tự động, kể cả khi chưa làm nhóm B. Offline SQL nhân đôi `%%`: dùng `quote_ident` như `0024_three_agent_groups.py:45-65`, không dùng `format()`. PowerShell 5.1 không có `utf8NoBOM`: ghi `0029-review.sql` không BOM như hướng dẫn ở 06, rồi kiểm sha bằng `check_reviewed_artifacts.py`.
- Không provider call nào được giữ owner lock: embed truy vấn trước khối `lock_actor`, embed document giữa hai transaction, đúng thứ tự khóa owner → job.
- Xóa entry phải dựa vào FK `ON DELETE CASCADE` (một điểm cho 5 đường xóa), không viết code xóa riêng ở từng route.
- `autoMemoryAvailable` luôn `false` cho tới JI-30. Memory tự động không được tăng `data_version`.
- Fullstack harness sở hữu cổng 8002/5174. Đừng sửa `frontend/` khi suite đang chạy: Vite HMR làm trang reload giữa test. Test deploy (`fcntl`) chỉ chạy trên Linux; trên Windows ghi "chưa chạy", không mock.
- Evidence Playwright trong `frontend/evidence/` là artifact, không commit.
- `git diff --check` và quét secret (cổng 15) trước mỗi checkpoint và trước mỗi push.

## 9. Báo cáo cuối

Cập nhật `08-execution-ledger.md`, rồi trả lời bằng tiếng Việt:

- Bảng task: trạng thái (xong / một phần / chưa làm), commit, test chính; commit nào đã push.
- Từng cổng JI-50: lệnh và số thật; cổng chưa chạy thì nói rõ vì sao.
- Danh sách test đã xóa, viết lại hoặc đổi assertion, mỗi mục một lý do.
- Mọi chỗ lệch kế hoạch và ruling; OD đã áp dụng; câu hỏi còn mở cho chủ dự án.
- Những gì chưa xác minh được (live provider, hosted, Linux deploy, chất lượng truy xuất thật).
- Không viết "sẵn sàng production" hay "đã đạt" cho điều chưa chạy.
