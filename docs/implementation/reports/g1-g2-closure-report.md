# G1/G2 closure — vòng 2

Ngày: 2026-11-08. Workspace `C:/Users/minhh/orca/workspaces/MoodPrint/mhiu05-feat-refactor`. Nhánh lúc kiểm tra: `feat/phase-1-backend`. HEAD sản phẩm đã kiểm CI: `81d6d1c6d568eda6ffb7e31104339c3ca076d751`. Merge commit: `669bdb5133feac31364bbd47d62bb85d716956bd`. Hai cây Git giống nhau (`ced5a0b43a1ea1bf470da3be40ade16b9f680f3c`).

Sản phẩm **chưa** sẵn sàng cho học sinh thật. `00` §6 vẫn áp dụng.

## Kết luận phiên

| Hạng mục | Trạng thái |
|---|---|
| G0 | VERIFIED. PR #46, merge `d5c36ac0` |
| G1 tự động | VERIFIED trên CI của đúng SHA `d779a243` |
| G1 hosted UI | VERIFIED trong cửa sổ Chrome tách biệt của phiên Chrome đang chạy |
| G1 hosted API/schema/advisor | VERIFIED trong phiên này |
| G2 | VERIFIED. `verify_phase0.py --regression` và `verify_phase1.py` exit 0 trên `763dcdd6` |
| Tag `baseline/phase-1-verified` | Trỏ `763dcdd66ba8dbbfd691ad8541db21062ac06772`. Đã push |

## Git và CI

- Repo: https://github.com/mhiu05/MoodPrint
- PR: https://github.com/mhiu05/MoodPrint/pull/47
- Base `origin/mhiu05/feat-refactor`: `d5c36ac0a1eae81fbe61fe1c6efd2a3a4203606e`
- Head trước báo cáo này: `d779a2435149b0e8f6630873f70c56f06979ad20`
- Ahead/behind so với base: 11 / 0. `mergeable=MERGEABLE`, `mergeStateStatus=CLEAN`
- Không có branch protection trên `mhiu05/feat-refactor`. Không có review bắt buộc
- CI trên đúng HEAD, cả push và pull_request, kết luận SUCCESS:
  - https://github.com/mhiu05/MoodPrint/actions/runs/42440492063
  - https://github.com/mhiu05/MoodPrint/actions/runs/42440494924
  - Job `offline` và `integration` đều pass. `integration` gồm local Supabase, pgTAP, `pytest -m integration`, và `scripts/e2e_stack.py --run`

Worktree dùng chung git dir `E:/MoodPrint/.git`. `core.hooksPath` trống. `extensions.worktreeConfig` không bật, nên không ghi `core.hooksPath` vào config dùng chung. `.githooks/pre-commit` chỉ gọi `check_ownership.py` khi nhánh là `feat/knowledge-ingestion-rag` hoặc `feat/agent-companion`; trên nhánh này hook thoát 0. CI có cùng nhánh điều kiện trong `.github/workflows/ci.yml`.

`uv run pytest scripts/tests/test_ownership.py -q`: **98 passed**.

## Hosted UI

Điều khiển UI Automation trên cửa sổ Chrome mới của process Chrome sẵn có (`pid 12096`). Không mở profile mới và không dùng Playwright Chromium. Cửa sổ Facebook của người dùng được trả foreground sau mỗi thao tác và vẫn còn sau khi đóng cửa sổ smoke.

Frontend `http://127.0.0.1:5173`. API `http://127.0.0.1:8000`. `GET /health` và `GET /ready` đều 200. `APP_ENV=development`. Host Supabase là `xhlshihobyxrgfqrdafh.supabase.co`.

Đăng ký công khai `@example.test` bị GoTrue từ chối: HTTP 400 `email_address_invalid`. Form UI hiện `Chưa thể hoàn tất xác thực. Hãy kiểm tra thông tin rồi thử lại.` User tổng hợp được tạo bằng Admin API với `email_confirm=true`, đúng lối smoke đã có, rồi đăng nhập trên UI.

Quan sát được trong cửa sổ smoke:

- `/auth` ở chế độ thật, không phải demo
- Sau đăng nhập: `/home`, `Chào Synthetic`, liên kết hồ sơ ghi `Tài khoản của bạn`
- Tạo hồ sơ `Synthetic hosted case`. API `POST /v1/cases` 200, `PATCH` timeline 200
- Reload: `GET /v1/cases/9f626701-318a-4900-b4fd-8bf4d355efa0` 200, UI còn tiêu đề và câu timeline
- Upload `synthetic-evidence.txt`: `POST /v1/evidence/uploads` 200, Storage 200, `complete` 200, UI `Đã tải xong`
- Gắn vào hồ sơ: `PATCH` case 200 và `POST .../evidence/.../link` 200
- `Tải tệp gốc`: `GET /v1/evidence/{id}/download-url` 200 và Storage sign 200
- Kế hoạch: `PUT /v1/cases/{id}/plan` 200 hai lần. Sau reload, ô mục tiêu là `Synthetic hosted plan` và bước đầu là `Bỏ hoàn tất: Ghi lại điều mình muốn thay đổi`
- Đăng xuất về `/auth`
- User B mở cùng URL hồ sơ và thấy `Không tìm thấy hồ sơ` cùng `Không tìm thấy hồ sơ trong tài khoản của bạn`

Dọn sau đó: `DELETE` evidence 204, `DELETE` case 204, xóa hai Auth user 200. Đếm hosted: `ui-smoke` users 0, `smoke+` users 0, case tiêu đề synthetic 0, profile nickname synthetic 0, evidence tên file synthetic 0.

## Hosted schema và advisor

Project đọc từ Management API: name `db-school-violence`, ref `xhlshihobyxrgfqrdafh`, status `ACTIVE_HEALTHY`.

`uv run python scripts/db/push_hosted.py --dry-run`: không in migration pending, `Dry run completed; no hosted changes made.`

`supabase_migrations.schema_migrations`: **17** dòng. Cuối là `20261107140312 f1_account_deletion_guard`. Sáu migration `f1_*` đã có trong lịch sử.

`uv run python scripts/smoke_hosted.py --phase 1`: exit 0. In `VERIFIED readiness`, profile/memory/isolation, signed upload, case/evidence/plan/deletion, `VERIFIED synthetic cleanup completed`.

Security Advisor: **0** lint.

Performance Advisor:

| Advisor | Finding | Object | Severity | Action |
|---|---|---|---|---|
| performance | `multiple_permissive_policies` | `app.case_shares` | WARN | Chấp nhận. `owner_read` OR `staff_read`. Staff chỉ `submitted`/`in_review`/`closed` và `is_school_member` |
| performance | `multiple_permissive_policies` | `app.case_share_evidence` | WARN | Chấp nhận. `owner_all` OR `staff_read` với cùng giới hạn share đã gửi |
| performance | `unused_index` | nhiều bảng `app` và `agent_store` | INFO | Không xóa. Dataset hosted còn nhỏ |
| performance | `auth_db_connections_absolute` | Auth | INFO | Không đổi kế hoạch kết nối |

Không có security error mới. Không có escalation staff đọc draft riêng.

## Kiểm tra không cần Docker trong phiên này

- `uv run pytest shared/tests -q`: **53 passed**
- `uv run python scripts/export_contract_schemas.py --check`: exit 0
- `uv run python scripts/export_openapi.py --check`: exit 0
- `uv run pytest scripts/tests/test_ownership.py -q`: **98 passed**

Ngày 2026-11-08, sau khi Docker engine 29.8.2 lên, `uv run python scripts/verify_phase1.py` exit 0 trên `763dcdd6` trong 1024 giây. Checkpoint 1 là `verify_phase0.py --regression`, cũng exit 0. Bên trong regression: `check.py` 265 passed / 67 deselected; pgTAP 13 files, 194 tests, PASS; `pytest -m integration` 67 passed / 265 deselected. Phần Phase 1 thêm Vitest 94 passed, demo Playwright 13 passed, real Playwright 11 passed và urgent 1 passed.

## G2

| ID | Requirement | Status | Evidence |
|---|---|---|---|
| G2-01 | Combined baseline | VERIFIED | Merge `669bdb51`. Trên `763dcdd6`, `verify_phase0.py --regression` và `verify_phase1.py` đều exit 0 lúc 2026-11-08T07:09:07Z. Receipt `.local/phase1-gate.json` và `.local/phase0-regression-gate.json` |
| G2-02 | Contract snapshots | VERIFIED | `shared/tests` 53 passed; hai lệnh `--check` exit 0 trên `d779a243` |
| G2-03 | Database migrations | VERIFIED | Hosted history 17, dry-run không pending. Reset local không chạy lại trong phiên này; CI integration đã reset/bootstrap trên cùng SHA |
| G2-04 | AuthContext | VERIFIED | Không có thay đổi chưa merge ngoài nhánh này. CI và UI đăng nhập thật dùng JWT hosted |
| G2-05 | KnowledgeRetriever fixture | VERIFIED | `create_retriever` trả `FixtureKnowledgeRetriever`; `shared/tests` gồm contract fixture, không gọi Voyage |
| G2-06 | ScriptedModel runtime | VERIFIED | Nằm trong CI offline/integration của `d779a243` và cổng `ddf970dc`. Không gọi model trả phí |
| G2-07 | Memory | VERIFIED | Hosted smoke memory tạo/sửa chéo 404/xóa 204 trong phiên này; suite CI giữ test persist |
| G2-08 | Tool approval | VERIFIED | S-03 đã có kết luận từ Phase 0. Không giả định SDK resume chưa chứng minh |
| G2-09 | Mock/Real adapters | VERIFIED | UI thật không rơi về demo. `Tài khoản của bạn` sau đăng nhập. Composition tách file |
| G2-10 | Ownership enforcement | VERIFIED | `ownership.yaml`, `check_ownership.py`, 98 test pass, CI gọi script trên hai nhánh phase |
| G2-11 | Scaffolding | VERIFIED | Đủ mục `06` §3.3: retriever fixture, router rỗng đã `include_router`, ingestion/tests/evals, composition knowledge/chat/analysis/roleplay, extras `knowledge` và `companion`, ba config class, khối `.env.example` |
| G2-12 | Independent local stacks | VERIFIED | `spikes/S-04.md` kết luận VERIFIED, offset `+100`. Phiên này không dựng lại hai stack vì Docker không lên |
| G2-13 | CI | VERIFIED | Hai run SUCCESS trên `d779a243` |
| G2-14 | Integration strategy | VERIFIED | Mục dưới đây |

Tag `baseline/phase-1-verified` đã push và trỏ `763dcdd6`, commit vừa chạy xong hai script cổng. Phase 2 và Phase 3 có thể rẽ từ tag này. Không coi đây là phê duyệt cho học sinh thật.

## Chiến lược integration

Baseline đã merge là `669bdb5133feac31364bbd47d62bb85d716956bd` trên `mhiu05/feat-refactor`. Hai worktree sau này:

- `feat/knowledge-ingestion-rag` từ baseline đó, chỉ sửa vùng Phase 2 trong `docs/implementation/ownership.yaml`
- `feat/agent-companion` từ cùng baseline, chỉ sửa vùng Phase 3
- Nhánh chung `integration/phase-2-3` do integrator tạo khi cả hai sẵn sàng. Phiên này không tạo ba nhánh đó

Contract đóng băng ở `shared/src/moodprint_shared/contracts/**`, `shared/src/moodprint_shared/testing/**`, `shared/contract-schemas/**`. Đổi vùng khóa đi qua `docs/implementation/compat/CC-NNN.md`, nhánh `compat/CC-NNN`, rồi tag `baseline/phase-1-verified+ccNNN`.

Migration Phase 2 dùng `*_kb_*` trong schema `knowledge`. Phase 3 dùng `*_ag_*` và không `ALTER`/`DROP` bảng `f0`/`f1`. IT-01 chạy cả hai thứ tự trên database trống. Hosted chỉ integrator push bằng `scripts/db/push_hosted.py` sau khi integration xanh. Offset local theo S-04: Phase 2 `+100`, Phase 3 `+200`. Không để `DATABASE_URL` hosted trong worktree feature.

IT-02 đến IT-09 giữ nguyên bảng ở `06` §7. IT-09 dùng `gpt-6-luna` và chỉ chạy khi owner đặt trần chi phí. A-06 vẫn DEFERRED, P1, vì chưa có trần đó.

## Giới hạn

- Signed upload đã phát hành còn hiệu lực tới TTL sau khi xóa Auth user. Không có thu hồi tức thì. Không thấy yêu cầu P0 bắt buộc thu hồi sớm hơn TTL.
- A-06 không chạy. Model giữ `gpt-6-luna`.
- Đăng ký công khai không nhận `@example.test`. Admin API thì nhận. Không tắt xác nhận email.
- Docker engine 29.8.2 đã lên vào 2026-11-08. Cổng local chạy lại trên `763dcdd6` và exit 0.
