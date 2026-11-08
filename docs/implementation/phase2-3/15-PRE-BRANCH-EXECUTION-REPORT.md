# 15 — Báo cáo thực thi Pre-Branch

## A. Tổng thể

**CONDITIONALLY_READY / chưa đủ để tag.** Các sửa P0 đã có test unit. Gate Docker, CI, canary, merge và tag chưa có bằng chứng trên SHA cuối.

## B. PB-01 đến PB-09

| ID | Trạng thái | Bằng chứng hiện có |
|---|---|---|
| PB-01 | Tài liệu kế hoạch ở `7bc37ce7`. Source seam ở `a620718069c86accf9dfcb40d2dc2a37a65dcfc6`. | `git log` |
| PB-02 | Seams frontend có trong cây làm việc. Vitest đầy đủ chưa chạy lại trên SHA cuối. | `frontend/src/services/ports.ts`, composition, `client.stream.test.ts` |
| PB-03 | Factory backend và router analyses/roleplay có trong cây. | `backend/app/main.py`, `wiring.py`, tests knowledge/agent |
| PB-04 | `add_confirmed_event` là seam nội bộ. Chưa có ProposalStore. Hosted apply không chạy. | `incidents/service.py`, `push_hosted.py` |
| PB-05 | Manifest và scope guard đã chặn INHERITS/PARTITION OF. Hai thứ tự migration trên DB thật chưa chạy. | `migration_scope_check.py`, `14_schema_policy_manifest.sql` |
| PB-06 | Policy v2, CI gọi `ci_ownership.py`. Canary GitHub chưa chạy. | `.github/workflows/ci.yml`, 648 unit pass |
| PB-07 | Offset, lite marker, sync thư mục stack. Hai stack đồng thời chưa đo lại. | `supabase_worktree.py`, `test_e2e_stack.py` |
| PB-08 | Extras knowledge/companion trong lock. Cài đặt sạch CI chưa có run mới. | `agent/pyproject.toml`, `uv.lock` |
| PB-09 | Chưa merge, chưa tag. | File này |

## C. B-01 đến B-11

| ID | Xử lý | Test |
|---|---|---|
| B-01 | CI và hook dùng `ci_ownership.py`; tên nhánh cũ bị exit 2. | `test_ci_ownership.py` |
| B-02 | Checkout PR head SHA; base là ancestor tag. `--base` không ancestor exit 2. | `test_explicit_nonancestor_baseline_is_rejected` |
| B-03 | Local override chỉ cho unstaged/uncommitted. | `test_local_overrides_are_only_uncommitted_and_not_staged` |
| B-04 | Allow-list phase trong `ownership.yaml`. | matrix ownership |
| B-05 | Slot `knowledgeSearch` và `companion` nullable; stream client dùng auth sẵn. | `composition.test.ts`, `client.stream.test.ts` |
| B-06 | `build_runtime`, `build_knowledge_retriever`, router đã đăng ký. | `backend/tests/test_app.py` |
| B-07 | `add_confirmed_event` chỉ `user_confirmed`. REST vẫn không nhận provenance đó. | `test_incident_confirmed_events.py` |
| B-08 | pgTAP không khóa đúng 22 bảng; knowledge được kiểm nếu tồn tại. | `00_rls_coverage.sql`, `05_grants.sql` |
| B-09 | Cổng theo offset; capability thay khẳng định AI mô phỏng vô điều kiện. | `test_e2e_stack.py` |
| B-10 | `uv sync --all-extras --locked` là lệnh CI. | workflow |
| B-11 | Receipt phase 23, `--include-all` chỉ khi apply, trùng version bị từ chối, history được đọc lại trước CLI. | `test_push_hosted.py` |

B-12 đến B-16 thuộc Phase 2 hoặc Phase 3, không làm trong PB.

## D. Source

Seam frontend/backend, confirmed event, hosted tooling, SQL scope, ownership, E2E isolation, extras. Không có migration Phase 2/3. Không có Agent HTTP server.

## E. Handoff

- `12-PHASE-2-GROK-EXECUTION-HANDOFF.md`
- `13-PHASE-3-OPUS-EXECUTION-HANDOFF.md`
- `14-INTEGRATION-AGENT-EXECUTION-HANDOFF.md`

## F. Test đã có số

`uv run pytest scripts/tests scripts/db/tests -q --tb=line` → 648 passed, exit 0.

Chưa gắn số cho `verify_phase1.py`, pgTAP hai stack, demo E2E đồng thời, hay CI.

Mục tiêu retrieval và eval vẫn UNMEASURED: 180 query, Recall@5 ≥ 0.80, no-result ≥ 0.90, citation integrity 100%. Không có điểm đo.

## G. Git

Preparation branch: `integration/pre-branch-readiness`. Commit tài liệu đầu: `7bc37ce7d05b182bcee9e21217cc0be6a45e6ddf`. Commit source: `a620718069c86accf9dfcb40d2dc2a37a65dcfc6`. Target remote lúc fetch: `1aec4078f2852720479e183d10c7cc086b6d6a3f`. Main: `8b329980af4038f4c2a565a6472fd01472fbdfef`. Tag Phase 1 peeled: `763dcdd66ba8dbbfd691ad8541db21062ac06772`.

PR, merge, CI run và tag `baseline/phase-2-3-start`: chưa có.

## H. Worktree owner

Chưa cung cấp lệnh để chạy. Xem `16` khi mục YES đủ bằng chứng.

## I. Owner tạo hai worktree chưa?

**NO.**

## J. Việc còn thuộc owner, không phải phần source PB

- API key Voyage và OpenAI khi bắt đầu live.
- Budget `.local/eval-budget.json` với trần USD, token, số call, scope và hạn.
- Quyết định giấy phép UNICEF/WHO nếu muốn nâng khỏi `reference_only`.
- Xác minh nguồn pháp lý đang 403 khi Phase 2 bắt đầu.
- Không cần owner để sửa ba lỗi scope/history/ancestor; phần đó nằm trong diff PB.
