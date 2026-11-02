# Handoff cho coding agent triển khai tiếp theo

Copy prompt dưới đây vào session mới **khi người dùng đã yêu cầu implementation**. Audit hiện tại không cho phép production mutations, deploy, paid evaluations hoặc thay repository settings.

```text
Triển khai MoodPrint theo docs/implementation-plans/ci-test-suite-refactor/.

1. Bắt đầu và scope
- Đọc AGENTS.md/instructions; không tự sửa .gitignore.
- Kiểm git status --short, git branch --show-current, git rev-parse HEAD.
- Làm trên branch hiện tại. Không tạo/switch branch/worktree, stash/reset hoặc overwrite changes.
- Audit source baseline: a3af3d4cef1c7de75b2ec2b65ea5743640fbb853.
  Nếu HEAD khác, đọc diff và refresh collector manifests; counts không là source truth vô thời hạn.
- Đọc00–05, task plan06, protocol07 và evidence/README.md.
- Dùng executing-plans task-by-task; chỉ delegation nếu execution session cho phép.

2. Invariants
- Giữ verify.yml, workflow name Verify local application, ID394882427, final check/job verify.
- Main push luôn full; skipped PR lanes chỉ theo explicit selection policy.
- Publisher/poller vẫn yêu cầu current-main SHA, successful push-main/same repository,
  expected workflow ID/path, manual owner approval, publication hold, immutable digest refs,
  manifest/OCI attestations và repeated latest-main rechecks.
- CI xanh không chứng minh hosted compatible. Audit hosted revision0020, source accepted0024.
- Giữ owned disposable DB guards, fake SDK required CI, privacy/auth/18+/quota/migration tests.
- Audit chưa chứng minh test nào có thể xóa. Không dựa tên legacy hoặc coverage percentage.
- Không dùng retry/delay/fill để che keyboard-picker failure.

3. Thứ tự triển khai
- P0-01 instrumentation và failed-run receipt trước; không đợi green baseline để diagnose.
- P0-02 điều tra full-stack V3-D (v3.spec.ts:150), GroupChat.tsx deferred caret;
  sửa hai historical docs links. Nếu business bug ngoài scope, giữ assertion và handoff bugfix riêng.
  Sau khi xử lý đúng scope mới thu successful control runs.
- P0-03 release-contract negative tests và required-check inventory.
- P1 trigger/concurrency, npm duplicate audit cleanup.
- P2 taxonomy theo fixture closure + self-managed DB, helper extraction, invariant map.
  Optional reset experiment không là blocker cho parallelization.
- P3 independent full lanes + fail-closed verify, rồi caches đã đo net savings.
- P4 selection shadow/canary PR, main full; synthetic performance và live evaluation riêng.
- P5 risk priority P0: có thể bắt đầu sau P0-03, trước performance work nếu sắp release.
  Shared schema contract/read-only CLI → candidate preflight trước active write → worker health/smoke.
- P6 parity/fault injection/matched benchmark → canary rollout/ownership/runbooks.
- P5 phải xong trước deploy candidate0024 vào target đang0020.

4. Files và interfaces
-06 chứa18tasks, exact affected files, dependencies, interfaces, steps, tests, acceptance và rollback.
- CI: verify.yml; proposed scripts/ci/{benchmark,gate,selection,collect_tests}.py,
  dependencies.json, test-ownership.json và scripts/ci/tests/.
- Helper edges87/47files và marker gaps154/12files trong classification-facts.json.
  Còn self-managed DB case trong test_database_operations.py phải classify explicit.
- Unit + integration manifests phải union toàn bộ1715baseline identities.
  Hosted live-only probe không có postgres marker vẫn thuộc integration manifest với skip_opt_in;
  required CI không bật live/load flags, giữ4intentional skips.
- Compatibility: new app/core/compatibility.py, backend/compatibility.json,
  scripts/export_compatibility.py và negative tests; main/worker/readiness consume chung.
- Host: deploy/aws/deploy.sh, poll_release.py, tests/docs; giữ manifest schema1 ban đầu.
- Hosted smoke runner/guards mới, không tự gọi reset-fixture-pair.
- Files ghi Create trong06 là future files, không là missing-source defects.

5. Commands và verification
- Python3.12.13/uv0.11.14, uv sync --locked, Ruff exact workflow scope, mypy app.
- Collect bằng audit collector; compare node-ID union/intersection và skip reasons.
- Full pytest với verified owned DB/run ID: uv run --locked pytest -q
  --durations=30 --junitxml=<owned output path>.
- Alembic upgrade/current/check trên separate scratch DB, không hosted DSN cho reset.
- Frontend Node22/lockfile: npm ci --no-audit --no-fund; npm audit --audit-level=low;
  contracts generation + OpenAPI/TypeScript diff, typecheck, npm test, npm run build.
- Dynamic Vitest list; Playwright lists. Baseline217Vitest +1Node;398mock +50full-stack.
- Full-stack từ backend: uv run --locked python ../scripts/test_fullstack.py,
  workers1/fake SDK/owned targets.20fresh canary runs khi kiểm flake/order, không shared-state rerun sai.
- Linux python3 -m unittest discover -s deploy/aws/tests -v; native Windows thiếu fcntl.
- New CI unit tests, actionlint, SQL/docs checks, cả ba Docker contexts/Compose/Caddy/proxy guards.
- Protocol07:≥10matched full samples/config, cold/warm/cache/queue/runner-cost/failures riêng.
  Selection shadow≥10representative changes; unknown path/base/diff error→full.

6. Stop/Hold
- Overlapping user changes không preserve được hoặc unexplained source drift.
- Missing critical coverage, unexplained node/skip reduction, shared-DB order dependence.
- Planner error hoặc selected failed/cancelled/skipped lane làm verify xanh.
- Release provenance/hold/digest/attestation semantics bị nới ngoài approved design.
- Real provider/hosted writes bị kích hoạt trong required offline CI.
- Schema0020/false head/missing catalog/ACL/worker unhealthy được chấp nhận.
- Thiếu authorized synthetic target/accounts/mutation budget: BLOCKED/NOT_RUN, không PASS.
- Previous image chưa chứng minh compatible current DB: Hold, không auto downgrade/stamp/migrate.
- Product bug cần business change ngoài scope: report evidence và giữ regression.

7. Commit và rollout
- Một task hoặc independent helper family mỗi commit sau meaningful verification.
- Stage exact files, inspect diff/status; không reset branch hoặc sửa .gitignore để lộ evidence.
- Baseline immutable, experiment outputs vào fresh run directory. Scanner phải đọc đúng
  --evidence-dir và ghi --output-dir đã chọn, không trộn manifests cũ/source mới.
- Không push/PR/merge/deploy/settings mutation khi chưa được yêu cầu.
- Rollback bằng task-specific revert/force-full selection, giữ release/schema safety gates.

8. Final report bằng tiếng Việt
- Tasks done/deferred/blocked, files/commits, commands/exit codes/run links.
- Measured before/after p50/p90 wall-clock, runner-seconds/cache cost/counts/flake rates;
  ESTIMATE và failed/cancelled samples tách riêng.
- Invariant parity, selection false negatives và exact-main release negative matrix.
- Hosted schema/image/runtime proof thực sự đã đo; phần NOT_RUN và limitations.
- Risks còn lại, rollback switches và next concrete step.
```

Bắt đầu bằng P0-01–P0-03. Không có implementation/refactor/deploy nào được thực hiện chỉ vì prompt handoff này đã được viết.
