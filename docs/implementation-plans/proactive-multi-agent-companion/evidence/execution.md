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
