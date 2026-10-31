# Sổ tiến độ triển khai Phase 1

Nhánh `feat/proactive-companion-phase1`, worktree `E:\MoodPrint-proactive-phase1`, tách từ `test/local-2026-10-30@d6eaf71`. Kế hoạch: [phase-1/08](../phase-1/08-implementation-plan.md); gia cố: [96](../96-architecture-hardening-review.md).

Hạ tầng test (chỉ local, không hosted):

| Hạng mục | Giá trị |
| --- | --- |
| PostgreSQL disposable | Container `moodprint-proactive-p1-db` (`pgvector/pgvector:0.8.2-pg17`, tmpfs, `127.0.0.1:36432`), mật khẩu chỉ nằm trong scratchpad phiên, không trong repo |
| DB | `moodprint_p1_{unit,dev,migration,fullstack,load,baseline}_test` |
| Python | `backend/.venv` riêng của worktree, `uv sync --locked` (không đổi lockfile); `openai-agents==0.24.0` |
| Frontend | `npm ci` trong worktree |
| Cách ly Codex | Worktree gốc `E:\MoodPrint` không bị sửa; snapshot `git status` trước/sau khớp, trừ `.gitignore` (+`.tmp/`) do Codex tự sửa lúc 08:06 |

Quy ước: số pass/fail/skip là **kết quả thật** của lệnh đã chạy. "Chưa chạy" được ghi rõ.

## P1-00 — Baseline

| Lệnh (cwd) | Kết quả thật |
| --- | --- |
| `pytest -q` (backend, DB `moodprint_p1_baseline_test`, worktree) | **1099 passed, 6 failed, 1 skipped**, 1436 s. Lưu ý: chạy song song với lúc sửa P1-01/02 nên các test chạy Alembic bằng subprocess có thể bị ảnh hưởng → 4 fail không phải readiness được **chạy lại trên worktree sạch `d6eaf71`** (detached, scratchpad) |
| Chạy lại trên `d6eaf71` sạch: `test_guest_cleanup_recovery::test_guest_aware_rollback_cannot_resurrect`, `test_guest_embeddings::test_guest_proposal_and_history_expiry_capped`, `test_guest_schema::test_upgrade_from_0015_preserves_registered_rows_and_matches_models` | **3 failed** ⇒ fail **có sẵn** |
| `ruff check app tests evals alembic` trên blob của `d6eaf71` (`git show … \| ruff --stdin`) | **2 lỗi F401 có sẵn** (`models.py: Text`, `test_data_lifecycle.py: uuid4`) |
| `mypy app` | Success |
| Frontend `npm run typecheck` / `npm test` / `npm run build` | exit 0 / **118 passed (23 files)** / build OK |
| `python scripts/check_docs.py` | PASS |

Fail có sẵn (phân loại):

| Test | Nguyên nhân | Xử lý |
| --- | --- | --- |
| `test_foundation::test_ready_revisions_cover_the_reviewed_migration_window`, `[0019_journal-200]`, `test_readiness::[0019_journal-200]`, `test_guest_cleanup_recovery::test_guest_aware_rollback_cannot_resurrect`, `test_guest_schema::test_upgrade_from_0015…` | Kỳ vọng cũ `0019_journal`, `READY_REVISIONS` đã là 0020 | Cập nhật theo head mới ở P1-03 (R1 = 0022; R0 = 0020/0021/0022). **Codex cũng đang sửa các file này** trong worktree gốc → dự kiến conflict khi tích hợp |
| `test_guest_embeddings::test_guest_proposal_and_history_expiry_capped` | `TypeError: create_proposal() takes 5 positional arguments but 6 were given` — lỗi test có sẵn, không liên quan | **Không sửa** (ngoài phạm vi); không chặn G1a |
| Ruff F401 ×2 | Import thừa | Sửa riêng ở commit `b5484c9` |

## P1-01 — M-P1-A `0021_multi_message`

- Commit `32e8bfa` (+ lint có sẵn `b5484c9`). File: `alembic/versions/0021_multi_message.py`, `app/ai/models.py`, `app/infrastructure/database/models.py`, `tests/test_multi_message_migration.py`.
- RED: thiếu file migration. GREEN: `test_multi_message_migration.py` 1 passed.
- **Lỗi bắt được khi review offline SQL:** `create_check_constraint("ck_…")` bị naming convention của `env.py` áp hai lần (`ck_ai_messages_ck_ai_messages_part`). Sửa bằng `op.f()`; test được nâng cấp dùng cùng `target_metadata` như `env.py` và khẳng định tên chính xác (RED → GREEN đã quan sát).
- `alembic upgrade head` trên `moodprint_p1_migration_test`: `0021_multi_message (head)`; `alembic check`: *No new upgrade operations detected*.
- Hồi quy: `test_chat_persistence`, `test_context_privacy`, `test_context_privacy_migration`, `test_sdk_adapter` + migration → **49 passed**. ruff/mypy sạch.

## P1-02 — M-P1-B `0022_proactive_messages` + lifecycle

- Commit `8e2a3d4`. File mới: `alembic/versions/0022_proactive_messages.py`, `app/ai/proactive/{__init__,models,lifecycle}.py`, `tests/proactive_helpers.py`, `tests/test_proactive_{migration,lifecycle}.py`. Sửa: `users/lifecycle.py` (xóa tường minh trong scope `account`/`all_private`), `guests/lifecycle.py` (`INVENTORY` + `_delete_owned`), `jobs/retention.py` (job kết thúc > 30 ngày), đăng ký model ở `alembic/env.py`, `tests/conftest.py`, `tests/e2e_server.py`, `tests/social_load_server.py`, `evals/scenarios_live.py`; docs `supabase/schema.md`, `backend/data-lifecycle.md`.
- RED: thiếu migration. GREEN: `test_proactive_migration`, `test_proactive_lifecycle` (4), `test_guest_cleanup` (seed thêm 5 bảng), `test_data_lifecycle` → **21 passed**.
- Kiểm chứng test xóa thật sự có sức bắt lỗi: tạm bỏ `purge_proactive` ở `process_deletions` → 2 test fail (account, all_private); khôi phục → xanh.
- Chuỗi Alembic sạch: `0022_proactive_messages (head)`, `alembic check` không drift.

## P1-03 — R0 tương thích và diễn tập migration

- R1 (nhánh này): `READY_REVISIONS = ("0022_proactive_messages",)` vì ORM ghi `part_index`/`origin` ở mọi insert — **khác kế hoạch gốc** (kế hoạch gộp R0 vào nhánh). R0 được tách thành nhánh riêng `release/proactive-r0-compat` (commit `e4fd51c`, từ `d6eaf71`, chỉ đổi `revisions.py` + test readiness).
- R0: readiness/foundation/guest rollback/guest schema **40 passed** (trong worktree tạm, đã gỡ). Smoke `r0_on_0022_smoke.py` (scratchpad): ORM R0 ghi/đọc trên schema 0022, đọc được run 2 bubble của R1, `scalar()` không lỗi → **PASS**.
- R1: test readiness/foundation **38 passed**; `test_guest_aware_rollback_cannot_resurrect` + `test_upgrade_from_0015…matches_models` **2 passed**.
- Offline SQL `0020→0022` (258 dòng, không `%%`): [sql/0020-0022-offline.candidate.sql](sql/0020-0022-offline.candidate.sql), sha256 `14097febf574fe3a19950759e61a879157c0619ad72f9c5561b33d131acddf52` — **ứng viên chưa duyệt**, không nằm trong `reviewed-sql/`.
- Diễn tập (DB `moodprint_p1_rehearsal_test`, role tạm `moodprint_runtime`, `moodprint_app ∈ moodprint_runtime`, `anon`, `authenticated`, `service_role`): `alembic upgrade 0020` → seed dữ liệu cũ tổng hợp → `psql -v ON_ERROR_STOP=1 < offline.sql` (một transaction) → exit 0; version `0022`; tin cũ `part 0/1`; run cũ `origin=user`; 5 policy `backend_access`; client roles 0 quyền; `moodprint_app` có DML trên 5 bảng. Đã xóa DB và **cả 5 role** (đếm lại = 0).
- **Chưa làm (cần owner):** rehearsal trên bản khôi phục `pg_dump --schema-only` của hosted (U-04); áp dụng 0020 hosted (BLK-02).

## P1-04 — Hợp đồng output nhiều bubble

- Commit `637fdc3`. File: `app/ai/schemas.py` (`Bubble`, `CompanionReply`, `AiReply`), `app/ai/journal.py` (`NhipReply`, renderer chung), `app/ai/provider.py` (`run_reply()`, guardrail mọi bubble), `app/core/config.py` (`AI_MULTI_MESSAGE_ENABLED=false`), docs cấu hình, `.env.example`.
- RED: thiếu `AiReply`. GREEN: `test_multi_message_contract.py` **19 passed**.
- Điều kiện chấp nhận "không sửa kỳ vọng khi cờ tắt": `test_sdk_adapter`, `test_journal_ai`, `test_mood_evidence_runtime`, `test_mood_evidence`, `test_live_observability`, `test_ai`, `test_ai_availability`, `test_context_selection` + test mới → **138 passed**, không sửa test cũ nào.
- **Chênh lệch tài liệu:** `run()` giữ API cũ và trả bản ghép v1 (`AiReply.joined()`); runtime dùng `run_reply()`.

## P1-05 — Lưu N bubble, phân trang, context, export

- Commit `d97e99f`. File: `runtime.py` (publish mọi phần trong transaction kết thúc run, id dùng chung DB/RAM, metric `ai_reply_parts`), `persistence.py` (`message_view`, hoàn thiện nhóm ở mép trang, `hasMoreMessages` tính lại), `context.py` (`turn_messages` gộp bubble trước giới hạn 24), `chat_routes.py` (export), `AIMessage` thêm `partIndex/partCount/origin/proactiveSlot`, OpenAPI + `schema.d.ts`, 2 tin lạc quan ở `RealApp.tsx`.
- RED → GREEN: `test_multi_message_persistence.py` **9 passed** (2 lỗi kỳ vọng sequence trong chính test mới được sửa: hội thoại mới bắt đầu ở version 1).
- Hồi quy AI rộng: **214 passed**. `test_ai_availability` đổi điểm monkeypatch `provider.run` → `provider.run_reply` (cùng khẳng định).

## P1-06 — SSE v2

- Commit `0bf35af` (+ docs `eda5df0`). `?protocol=2` (1–2, khác → 422); persistent dựng final từ mọi bubble đã lưu theo `part_index`; RAM giữ event v1 và `LiveRun.final_v2` cho v2; OpenAPI `AIFinalV2`, `AIReplyBubble`; metric `ai_events_protocol`.
- RED → GREEN: `test_ai_events_v2.py` **14 passed** (v1 byte-for-byte 1 bubble persistent + temporary, v1 ghép, v2 thứ tự/id, `afterSeq` 0..3, `Last-Event-ID`, `CURSOR_GAP`, protocol=3 → 422, OpenAPI).
- Lần đầu lưu event final dạng v2 làm 9 test hiện có (đọc `run.events` nội bộ) fail → **đổi thiết kế** thay vì sửa test: event lưu dạng v1, v2 đọc `final_v2`. Sau sửa: hồi quy **193 passed**.

## P1-07 — Frontend

- File: `src/api/stream.ts` (`consumeAIReply`, lõi parser chung, v1 fallback), `messageGroups.ts`, `RealApp.tsx` (chèn N bubble một lần, render nhóm `role=group` "Tin nhắn từ X, N phần", mỗi bubble "Phần i trên N", STALE_VERSION giữ nháp + tải lại + thông báo), `agent-chat.css` (khoảng cách nhóm), `messageDates.ts` ("Hôm nay"/"Hôm qua").
- Unit: RED (thiếu module) → GREEN **136 passed / 25 files** (118 cũ + 18 mới). Typecheck, build OK.
- **Chênh lệch tài liệu 02 §4.3:** giới hạn client mỗi bubble 6.000 (không phải 1.500) vì lượt cờ tắt hoặc bubble cuối có dòng trích dẫn hợp lệ dài hơn 1.500; client kiểm tổng ghép ≤ 6.000 và ≤ 3 card. Không có hiệu ứng vào (render ngay) — đáp ứng "animation must never delay content", reduced motion hiển nhiên.
- E2E fixture: 11 test cũ fail do glob stub `**/runs/*/events` không khớp `?protocol=2` → **đã chứng minh trên `d6eaf71` sạch các test đó pass** → sửa glob thành `events*` (giữ body v1 → kiểm luôn đường fallback). `ux-redesign:744` cập nhật kỳ vọng "Hôm qua"/"Hôm nay".
- Fail E2E có sẵn (giống hệt trên `d6eaf71` sạch): `real.spec:471`; `ux-redesign` :186, :901, :1128 ×2, :1180, :1196, :1273.
- Spec mới `multi-message.spec.ts` (đăng ký trong `playwright.config.ts`): **7 passed** (1440/768/390, không bubble trước `completed`, fallback v1, STALE_VERSION, bàn phím + reduced motion). Viết sau code → kiểm bằng mutation: tắt nhánh STALE_VERSION → test fail; khôi phục → xanh.

## P1-08 — Hướng dẫn tách bubble và eval

- Commit `703c084`. `MULTI_MESSAGE_GUIDANCE` (lớp runtime, chỉ khi cờ bật); `evals/multi_message/` 20 case tổng hợp, rubric content-free, CLI offline + live có cổng ngân sách.
- Test prompt: RED (thiếu hằng) → GREEN. `test_multi_message_eval.py` **8 passed** (viết sau code — ghi nhận). 
- **Eval live: CHƯA CHẠY** (cần owner duyệt ngân sách). Không có số liệu chất lượng tách bubble thật.

## Gate G1a — kiểm chứng (31/10/2026)

| Hạng mục | Lệnh / cách chạy | Kết quả thật |
| --- | --- | --- |
| Backend toàn bộ | `pytest -q` trên DB mới `moodprint_p1_unit_test` (không sửa file backend trong lúc chạy) | **1167 passed, 1 failed, 1 skipped** (1321 s). Fail duy nhất `test_guest_embeddings::test_guest_proposal_and_history_expiry_capped` — **có sẵn** (fail y hệt trên `d6eaf71`) |
| Ruff / mypy | `ruff check app tests evals alembic`, `mypy app` | sạch / Success (129 files) |
| Migration | `alembic upgrade head` (chuỗi sạch) + `alembic check`; rehearsal offline SQL 0020→0022 với role mirror + dữ liệu cũ | `0022_proactive_messages (head)`, không drift; rehearsal PASS (xem P1-03) |
| Frontend unit / type / build | `npx vitest run`, `npm run typecheck`, `npm run build` | **136 passed (25 files)** / 0 lỗi / OK |
| E2E fixture toàn bộ | `npx playwright test` | 295 passed, 7 failed, 23 không chạy do `globalTimeout` 600 s (CPU tranh với backend suite). `ux-redesign.spec.ts` chạy riêng: 62 passed, 7 failed. **Mọi fail đều có sẵn**, giống hệt trên `d6eaf71` sạch: `auth` :141/:166/:188, `discovery` :76/:148, `real` :471, `ux-redesign` :186/:901/:1128×2/:1180/:1196/:1273 |
| E2E nhiều bubble (fixture) | `multi-message.spec.ts` | **8 passed** (1440/768/390, khoảng cách nhóm ≤ 16 px, sao chép từng bubble, không bubble trước `completed`, fallback v1, STALE_VERSION, bàn phím, reduced motion) |
| Fullstack backend thật + fake SDK model, cờ **bật** | `scripts/test_fullstack.py` (`E2E_MULTI_MESSAGE=1`) ×2 | Lần 1: 27 passed / 7 failed; lần 2: **28 passed / 6 failed**. 6 fail = đúng tập fail của `d6eaf71` sạch (27/6). Fail thêm ở lần 1 `journeys:421` (strict mode, 2 nút xóa ghi nhớ) không tái hiện: 2/2 pass khi chạy riêng, pass ở lần 2 ⇒ flake phụ thuộc thứ tự, không liên quan chat |
| Fullstack cờ **tắt** | `E2E_MULTI_MESSAGE=0` | **27 passed, 1 skipped (spec nhiều bubble), 6 failed** = tập có sẵn |
| Spec fullstack mới | `tests/fullstack/multi-message.spec.ts` (user 51) | pass: 3 row cùng run, `partIndex` 0..2, `version == số tin + 1`, v1 nhận bản ghép, reload giữ nhóm, 768/390 không tràn ngang, 0 console error |
| agent-browser (trình duyệt thật, backend thật, cờ bật) | session `p1-g1a-multi`, cookie tổng hợp user 51, `set media light reduced-motion` | Nhóm "Tin nhắn từ Mây, 3 phần" với "Phần 1/2/3 trên 3"; nhãn ngày "Hôm nay"; 1440/768/390 không tràn ngang; 0 page error, 0 console error. **Phát hiện và sửa:** mỗi bubble giữ chỗ 44 px cho hàng giờ/sao chép nên 3 bubble trông như 3 lượt → commit `abdb454` (chỉ bubble cuối giữ chỗ; bubble trước hiện khi focus bàn phím/chạm). Ảnh chụp lưu ngoài git (scratchpad phiên) |
| `check_docs.py` | | PASS |
| Eval tách bubble live | | **Chưa chạy** (cần owner duyệt ngân sách) |

Cách ly Codex: HEAD worktree gốc vẫn `d6eaf71`; trong phiên Codex đã tự stage/sửa nhiều file (kể cả `database/models.py`, `test_data_lifecycle.py`, `test_guest_embeddings.py`, các test readiness, `e2e_server.py`, `conftest.py`, `openapi.json`, `schema.d.ts`) — **trùng file với nhánh này ⇒ dự kiến conflict khi tích hợp**, cần rebase có kiểm soát. Nhánh này không ghi vào working tree/index của worktree gốc.

Artifact chưa track do harness sinh trong worktree (`frontend/evidence/**`, `docs/mvp-validation|plans|productization/`) không được commit.

## Phiên tiếp nối 31/10/2026 — P1-09…P1-20

Khởi đầu: HEAD `b02a2da`, worktree sạch (chỉ artifact harness chưa track). Worktree Codex `E:\MoodPrint` ở `d6eaf71`; snapshot `git status --porcelain` + sha256 của `git diff` lưu ở scratchpad phiên để so sánh cuối phiên. DB test `moodprint-proactive-p1-db` còn chạy. Sổ này là ledger duy nhất (không dùng thư mục `.superpowers/sdd`).

- **OD-01…OD-07** — commit `250154f`: [ADR-13](../03-architecture-decisions.md#adr-13--quyết-định-od-01od-07-owner-ủy-quyền-31102026); giữ mặc định sau khi so sánh phương án, không đổi schema, không mở rộng quyền dữ liệu.
- **AWS** — `aws login --profile moodprint` thành công (role `AccountFullAccessRole`; chỉ dùng lệnh Describe/Get/List). AWS MCP vẫn lỗi `-32602`. Số liệu ở mục P1-20.
- **P1-09** — commit `2149733`: `app/ai/proactive/schedule.py`, `tests/test_proactive_schedule.py`. RED: `ImportError` (module chưa có). GREEN **53 passed** (HCM, New York gap 02:30→03:30 và overlap fold=0 chỉ giao một lần, giờ yên lặng qua nửa đêm, weekday mask, pause bao gồm ngày cuối, không ngày hợp lệ trong 15 ngày → `None`, teen tối ≤ 21:00, downtime 2 ngày nhảy tới tương lai). Không có `pytest-cov` trong lockfile (không thêm dependency) → độ phủ nhánh rà thủ công: mọi nhánh có test.
- **P1-10** — commit `aba316b`: `config.py` (9 biến `PROACTIVE_*` + validator production cho worker + `proactive_open_for`), `proactive/{schemas,policy,routes}.py`, router mount, `features.proactive`, OpenAPI + `schema.d.ts`, `api-reference.md`, `configuration.md`, `.env.example`. RED: 404. GREEN `test_proactive_api.py` **23 passed** (cờ tắt, 10 cặp mặc định, tạo lịch + settings + `last_seen_at`, stale/idempotent, khung/bước/teen, giờ yên lặng, cap 4, Cầu Nối adult+MATCH/restricted, history tắt, guest 403/under16 403, rollout, sửa/xóa hủy job, pause ≤ 30 ngày + gỡ auto-pause, settings tz/giờ yên lặng/xung đột, đổi tz tính lại + hủy job, tắt journal tăng `journal_context_version`/`data_version` chỉ hủy job Nhịp, validator production). Hồi quy auth/session/foundation/contract/proactive **168 passed**; ruff/mypy sạch; `check_docs.py` PASS.
  - Ruling: `available` = cờ + cohort + AI khả dụng (matrix 09 §4 "AI tắt → available=false"); lý do `ai_unavailable` vẫn trong enum nhưng không hiện khi `available=true` — chi phí nếu sai: chỉ đổi thông điệp UI.
  - Ruling: quyền AI là mục đích cá nhân luôn bật (`consent_enabled`), nên chỉ Cầu Nối cần kiểm consent (MATCH) — chi phí nếu sai: thêm một lý do eligibility.
  - Ruling: tạo settings lần đầu qua `PUT /settings` có `version 0 → 1`; `PUT /settings` trả `409 SCHEDULE_IN_QUIET_HOURS` (lịch dùng 422) như đặc tả §2.2/§2.3.
- **P1-11** — `persistence.py` (`daily_turns`, `admission` own/recent lọc `origin='user'`; global đếm mọi origin), `proactive/policy.py` (`authorize_proactive`, `admit_proactive`, `Decision`/`Authorized`). RED **21 failed / 1 passed** (ca pass: trần global vốn đã đếm mọi run). GREEN `test_proactive_policy.py` **22 passed** (ma trận: deleted/under16/unknown/guest/suspended → `skipped(ineligible_account)`, `deletion_pending` → `cancel`, inactive 15 ngày, cờ/cohort → `disabled`, AI tắt, history tắt, paused/auto_paused/disabled/version lệch → cancel, job mồ côi, Cầu Nối MATCH/teen; quota: run proactive không trừ `daily_turns`/rate/per-user concurrency, `aiQuotaRemaining` không đổi, global vẫn chặn; E1: budget share 50 % → `skip(budget)`, cap ngày, chat đang chạy cùng trợ lý → `defer(active_chat)`, hết capacity → `defer(capacity)`, 3 lời chưa mở → auto-pause + ghi `auto_paused_at`, 1 lời đã mở → không pause). Hồi quy AI/chat/multi-message **108 passed**; proactive API+policy 45 passed; ruff/mypy sạch.
  - Ruling: kiểm tra `inactive_user` đặt **sau** kiểm tra lịch tồn tại/bật (job mồ côi → `disabled`, không phải `inactive_user`) — chi phí nếu sai: chỉ khác `skip_reason`.
  - Ruling: "đã mở" = `last_read_sequence ≥ sequence đầu của lời hỏi thăm` **hoặc** người dùng đã trả lời sau đó trong hội thoại; hội thoại đã xóa không bị tính là chưa mở — tránh auto-pause oan.
- **P1-12** — `app/jobs/proactive.py` (`transaction` với HD-03, `materialize_due`, `expire_stale`, `claim_job`, `finish`/`retry`/`defer` có rào `lease_token`, `proactive_tick`, `serve`/`main`, heartbeat `--health`), `budget.py` (+2 kết nối worker → headroom 4), service Compose `proactive` trong `deploy/compose.staging.yml` (cùng image, `python -m app.jobs.proactive`, pool 2+0, `mem_limit 384m`, `cpus 0.5`, `stop_grace_period 100s`, healthcheck heartbeat, mặc định `PROACTIVE_WORKER_ENABLED=false`; `docker compose config --services` hợp lệ). `test_proactive_worker.py` **22 passed** + `test_session_reliability.py` (tổng 29 passed).
  - **Ghi nhận TDD:** module được viết trước khi chạy test (không quan sát RED riêng). Bù bằng mutation: bỏ rào `lease_token` / bỏ loại trừ "1 job running mỗi user" / bỏ nhảy tới tương lai sau downtime / bỏ hoàn attempt khi hoãn → **mỗi đột biến làm đúng 1 test fail**; khôi phục → 21/21.
  - Test thời gian song song (`< 0.55 s`) fail dưới tải CPU (0,70 s) → đổi sang đo `peak` đồng thời thực tế = 2 (không nới assertion, đổi thước đo đúng bản chất).
  - Ruling: materialize mỗi tick 5 s (không phải 30 s) — truy vấn dùng partial index `ix_ai_proactive_schedules_due`, giảm độ trễ giao tối đa từ ~30 s xuống ~5 s; chi phí nếu sai: vài truy vấn index rẻ mỗi phút.
  - Ruling: job `cancelled` (do người dùng sửa lịch) được **hồi sinh** khi giờ mới đến hạn cùng ngày (`ON CONFLICT … DO UPDATE WHERE status='cancelled' AND run_id IS NULL`) — tránh mất lời hỏi thăm hôm nay vì một lần chỉnh giờ; unique vẫn bảo đảm tối đa một lần giao/ngày.
  - Ruling: lịch đang auto-pause vẫn được dời `next_due_at` nhưng không tạo job (không sinh hàng loạt `skipped(auto_paused)`).
  - Ruling: "1 job running/user" là best-effort ở claim (hai claim đồng thời có thể cùng thấy không có job running); tuần tự hóa thật nằm ở khóa hàng `users` tại E1/E5.
