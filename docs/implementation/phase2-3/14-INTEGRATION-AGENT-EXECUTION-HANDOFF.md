# 14 — Integration Agent: bàn giao thực thi

> Dùng skill `executing-plans`. Làm đúng INT-00 đến INT-10. Không bắt đầu khi Phase 2 hoặc Phase 3 chưa có báo cáo và CI trên đúng SHA của từng nhánh.
> Worktree: `C:\Users\minhh\orca\workspaces\MoodPrint\mhiu05-feat-refactor`. Nhánh làm việc: `integration/phase-2-3`, tạo từ commit của tag `baseline/phase-2-3-start`. PR chỉ vào `mhiu05/feat-refactor`. Không merge vào `main`.

## 1. Khi nào được merge

Chỉ merge `integration/phase-2-3` vào `mhiu05/feat-refactor` khi cùng lúc:

- `PHASE_2 = VERIFIED` theo `12` mục Definition of Done, trên SHA đã push của `feat/knowledge-base`.
- `PHASE_3 = VERIFIED` theo `13` mục Definition of Done, trên SHA đã push của `feat/agent-companion`.
- `G_INTEGRATION = VERIFIED`: IT-01 đến IT-20 trong runbook `10` đều có lệnh, exit code và artifact.
- `REQUIRED_CI = SUCCESS`: job `offline` và `integration` trên đúng head SHA của PR integration.
- `CRITICAL_SECURITY_FINDINGS = 0`.

Thiếu một mục thì dừng, ghi blocker, không gắn VERIFIED và không merge. Không force-push, không bypass protection, không `--admin` để lách review bắt buộc.

## 2. Việc không làm trong integration

- Không tạo lại `feat/knowledge-base` hoặc `feat/agent-companion`.
- Không rebase hai feature branch. Cập nhật baseline chỉ bằng merge tag compat.
- Không reset hosted, không DDL qua MCP, không `--include-all` nếu không có lý do đã ghi.
- Không gọi API trả phí khi thiếu `.local/eval-budget.json` còn hạn, đúng model `gpt-6-luna`, đúng scope.
- Không sửa `.gitignore`. Không commit `.env`, `.env.live`, `.local/`, hoặc ba file cấu hình IDE/MCP của owner.
- Không dùng `git add -A`. Stage đường dẫn cụ thể.
- Không mở ba stack Supabase nặng cùng lúc. Tối đa hai stack. Dừng `kb` và `ag` trước khi chạy `int` offset 300.

## 3. INT-00 — Preflight

Đọc báo cáo `docs/implementation/reports/phase-2-report.md` và `phase-3-report.md`. Với từng SHA feature:

```powershell
git fetch origin --tags
git merge-base --is-ancestor baseline/phase-2-3-start <feature-sha>
git rev-parse origin/feat/knowledge-base
git rev-parse origin/feat/agent-companion
gh run list --commit <feature-sha> --repo mhiu05/MoodPrint
uv run python scripts/ci_ownership.py --branch feat/knowledge-base --head <p2-sha>
uv run python scripts/ci_ownership.py --branch feat/agent-companion --head <p3-sha>
```

Ghi SHA target và `origin/main`. Nếu `main` đổi ngoài dự kiến, dừng và hỏi owner. Kiểm `core.hooksPath` không bị script này ghi đè.

Acceptance: cả hai SHA là hậu duệ của tag baseline, CI xanh đúng SHA, ownership exit 0, báo cáo có mục giới hạn đã biết và không tự nâng benchmark/eval chưa đo thành pass.

## 4. INT-01 — Tạo nhánh và merge

```powershell
git switch --detach baseline/phase-2-3-start
git switch -c integration/phase-2-3
git merge --no-ff origin/feat/knowledge-base
git merge --no-ff origin/feat/agent-companion
git merge --no-ff origin/mhiu05/feat-refactor
```

Xung đột file sinh: xóa bản xung đột rồi chạy lại exporter. `config.py`, `.env.example`, `agent/pyproject.toml`: giữ cả hai section, không lấy một bên. Không dùng `-X ours` hoặc `-X theirs` cho file nghiệp vụ.

Sau merge sạch:

```powershell
uv sync --all-packages --all-extras --locked
uv run python scripts/export_contract_schemas.py --check
uv run python scripts/export_openapi.py
uv run python scripts/check.py
```

Trong `frontend`: `npm.cmd run gen:api`, rồi `git diff --exit-code -- src/services/http/schema.gen.ts`.

## 5. INT-02 — Migration và tương thích backend

Stack `int`, offset 300, `--lite`. Không đụng stack người khác đang chạy.

```powershell
$env:MOODPRINT_STACK_NAME = 'int'
$env:MOODPRINT_PORT_OFFSET = '300'
uv run python scripts/dev/supabase_worktree.py start --name int --offset 300 --lite
uv run python scripts/dev/migration_scope_check.py --all
uv run pytest scripts/db/tests/test_migration_versions.py -q
uv run python scripts/dev/supabase_worktree.py reset --name int --offset 300 --lite
uv run python scripts/dev/bootstrap_local_db.py --name int --offset 300
uv run python scripts/dev/supabase_worktree.py test --name int --offset 300 --lite
uv run python scripts/dev/migration_order_check.py
```

Phải thấy cả `VERIFIED order=kb-first` và `VERIFIED order=ag-first`. Hai lần này dùng migration thật của hai phase, không chỉ baseline PB.

`CREATE TABLE ... INHERITS` và `PARTITION OF` là lỗi scope, không phải cách thêm bảng. Trùng version: đổi timestamp của một file chưa apply, không sửa SQL. Không sửa migration đã có trên hosted.

Tương thích: schema mới phải để backend bản đang deploy tiếp tục chạy tới khi bản tích hợp được đưa lên. Thêm cột nullable hoặc có default trước. Không rename, drop, hoặc đổi nghĩa cột mà backend cũ còn đọc. Chạy bộ test backend/API của baseline trên schema đã migrate. Apply thành công không thay cho lần chạy đó.

## 6. INT-03 đến INT-06 — Retriever thật và vertical slice

Đổi default retriever sang pgvector là việc integrator, có test. Nạp corpus bằng CLI ingest của Phase 2, đúng target `test-env` của stack `int`. HashingEmbedder dùng cho đường tất định. Voyage chỉ khi budget còn hiệu lực.

Vertical slice bắt buộc, không fixture fallback khi bước yêu cầu dịch vụ thật:

1. Synthetic Auth.
2. AI Conversation.
3. Real Knowledge Retrieval.
4. Valid Citation.
5. Incident Context.
6. Evidence Analysis.
7. User Approval.
8. Incident Update.
9. Action Plan.
10. Persistence.
11. User Isolation.

`knowledge_search` phải trả chunk có `source_id` tồn tại. No-result không được bịa citation. Proposal hết hạn, bị từ chối, hoặc sai owner không được ghi `user_confirmed`. User B không đọc được case, conversation, proposal, memory, analysis của user A.

Lệnh chi tiết IT-02 đến IT-18 nằm trong `10` mục 6 và 7. Chạy đúng loader env của stack `int` (`.local/stacks/int/test.env`). Không trỏ test sang hosted.

## 7. INT-07 — Bảo mật

Đọc diff migration, policy, grant, tool ghi, và đường fetch ảnh. SSRF, redirect, MIME, kích thước và EXIF phải có test. Không nới grant anon/authenticated để làm pgTAP xanh. Bảng private ingestion giữ comment `moodprint:private_ingestion`, không quyền anon/authenticated. Critical = 0 mới được đi tiếp. Finding High còn mở thì ghi và không merge.

## 8. INT-08 — Hosted

Project duy nhất: `db-school-violence`, ref `xhlshihobyxrgfqrdafh`.

```powershell
uv run python scripts/db/push_hosted.py --dry-run
```

Đọc receipt `.local/hosted-migration-dry-run.json`: project ref, HEAD, history, pending, sha256 từ blob đã commit, introducing commit. Không có secret. Nếu history là backfill, receipt phải có `cli_dry_run=false` và chưa được coi là dry-run CLI thành công.

Apply chỉ sau dry-run khớp và gate local phase 23:

```powershell
uv run python scripts/db/push_hosted.py --apply
```

Script đọc lại history ngay trước CLI. Lệch plan thì dừng, không gọi CLI. Việc đọc lại không phải lock. Sau apply vẫn so history với danh sách commit. Race sau lần đọc xác nhận phải làm gate fail, không được vá bằng cách sửa receipt.

Rồi advisor security/performance, smoke API và UI bằng user tổng hợp, sau đó xóa user và object smoke. Đếm còn 0. Không reset project.

## 9. INT-09 — PR và merge

```powershell
git push -u origin integration/phase-2-3
gh pr create --base mhiu05/feat-refactor --head integration/phase-2-3
```

Chờ `offline` và `integration` SUCCESS trên head SHA. PR phải mergeable, đúng base, không có approval bắt buộc còn thiếu, không có commit target mới chưa hòa giải.

```powershell
gh pr merge <number> --merge --match-head-commit <head-sha>
```

Không merge vào `main`.

## 10. INT-10 — Sau merge và tag

```powershell
git fetch origin
git rev-parse origin/mhiu05/feat-refactor
git merge-base --is-ancestor <pr-head> origin/mhiu05/feat-refactor
git rev-parse origin/main
```

`origin/main` phải vẫn là SHA đã ghi ở INT-00, trừ khi owner đã merge việc khác và bạn dừng để hòa giải. Chạy lại regression bắt buộc trên commit merge, không dùng receipt của SHA preparation. Kiểm diff giữa SHA đã đo và SHA tag. Nếu chỉ khác tài liệu báo cáo, nói rõ và không gọi tài liệu đó là bằng chứng test.

Tag annotated `baseline/phase-2-3-verified` chỉ khi post-merge gate xanh. Không di chuyển tag. Push tag và kiểm peeled SHA trên origin.

## 11. Báo cáo

Viết `docs/implementation/reports/integration-report.md` với: ba trạng thái PHASE_2, PHASE_3, G_INTEGRATION; SHA feature, SHA integration, SHA merge, tag; lệnh và exit; IT-01 đến IT-20; CI URL; hosted receipt không secret; finding bảo mật; giới hạn. Không điền số benchmark hoặc eval chưa chạy.
