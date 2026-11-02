# Validation và benchmark protocol

Phân biệt ba loại kết quả: **MEASURED** từ evidence có SHA/run/environment; **ESTIMATE** là target trước implementation; **NOT_RUN/BLOCKED/UNKNOWN** không bao giờ đổi thành pass. Audit chỉ chạy collection/offline/synthetic no-DB checks, không full local browser/hosted mutations/deploy.

## Refresh audit evidence an toàn

Từ repository root, Windows PowerShell, dùng interpreter/dependencies hiện có; không cài mới hoặc resolve lockfiles để chỉ audit. `collect_pytest.py` và scanner không execute test bodies. Pytest conftest scrub provider config lúc collection. Nếu implementation thêm import side effects, phải review lại trước collect.

```powershell
git status --short
git branch --show-current
git rev-parse HEAD

$auditRoot = 'E:\MoodPrint\docs\implementation-plans\ci-test-suite-refactor'
$env:PYTHONDONTWRITEBYTECODE = '1'
Push-Location backend
& .venv/Scripts/python.exe ../docs/implementation-plans/ci-test-suite-refactor/collect_pytest.py --output "$auditRoot/evidence/pytest-manifest.json"
Pop-Location

Push-Location frontend
node node_modules/vitest/vitest.mjs list --no-staticParse --json="$auditRoot/evidence/vitest-collection.json"
node node_modules/@playwright/test/cli.js test --list --reporter=json > "$auditRoot/evidence/playwright-e2e-collection.json"
node node_modules/@playwright/test/cli.js test --config playwright.fullstack.config.ts --list --reporter=json > "$auditRoot/evidence/playwright-fullstack-collection.json"
Pop-Location

python docs/implementation-plans/ci-test-suite-refactor/audit_inventory.py --evidence-dir "$auditRoot/evidence" --output-dir "$auditRoot/evidence"
python docs/implementation-plans/ci-test-suite-refactor/benchmark_metadata.py --evidence-dir "$auditRoot/evidence"
```

Để giữ original baseline, thay mọi collector output và cả `--evidence-dir`/`--output-dir` bằng cùng một fresh run directory; không chỉ đổi output của scanner. Hai flags tách input khỏi output để tránh trộn stale manifests với source mới. PowerShell5 redirection có thể tạo UTF16; scanner đọc cả UTF8-BOM/UTF16, repository evidence cuối được normalize UTF8. `benchmark_metadata.py` cần saved GitHub JSON; không tự gọi API hoặc suy `updatedAt` là duration.

Read-only remote metadata commands (save output với UTF8 đúng chỗ; không đưa token vào args/logs):

```text
gh run list --repo mhiu05/MoodPrint --workflow verify.yml --limit 35 --json databaseId,headSha,headBranch,event,status,conclusion,createdAt,startedAt,updatedAt,url,displayTitle
gh api repos/mhiu05/MoodPrint/actions/runs/RUN_ID/jobs?per_page=100
gh api repos/mhiu05/MoodPrint/branches/main/protection
gh api repos/mhiu05/MoodPrint/rules/branches/main
```

Paginate runs/jobs khi vượt limit; current snapshot mỗi run chỉ1job và35runs đủ cho sample đã công bố. Log excerpts có timestamp/subsuite summaries, không persist entire logs chứa environment/config. CI after refactor phải record all attempts và pagination đầy đủ.

## Commands verification hiện tại, trước refactor

Linux CI/shell dưới đây là **commands để implementer chạy ở môi trường disposable**, không khuyến khích copy destructive DB commands vào hosted terminal. Provision qua `scripts/disposable_postgres.py`, đọc environment file do run tạo và export chính xác run ID/URL. Không dùng `backend/.env`, `DATABASE_MIGRATION_URL` hosted hoặc Supabase credentials cho tests/reset.

| Scope | Command / precondition | Expected |
|---|---|---|
| Backend install | `cd backend && uv sync --locked --python 3.12.13` | Lockfile unchanged |
| Ruff | `uv run --locked ruff check app tests evals alembic ../scripts/load_chat_memory.py ../scripts/apply_supabase_review.py ../scripts/provision_supabase_runtime.py ../scripts/check_reviewed_artifacts.py ../scripts/test_supabase_fullstack.py ../scripts/load_social_mood.py ../scripts/test_fullstack.py ../scripts/load_guest_experience.py ../scripts/prepare_guest_migration_review.py ../scripts/verify_guest_migration_review.py` | Exit0 |
| Type checking | `uv run --locked mypy app` | Exit0 |
| Full pytest | Owned DB + run ID, `uv run --locked pytest -q --durations=30 --junitxml=OWNED_OUTPUT/pytest.xml` | Baseline1715 collect; same source normally1711pass/4intentional skip; investigate delta |
| Migration | Separate owned scratch DB; clear runtime `DATABASE_URL`; migration URL points only to scratch. `uv run --locked alembic upgrade head`, `alembic current`, `alembic check` | Single0024head, no new upgrade ops; preservation tests also pass |
| Contract | `uv run --locked python ../scripts/export_openapi.py`; frontend `npm run contracts:generate`; root `git diff --exit-code -- backend/openapi.json frontend/src/api/generated/schema.d.ts` | No drift; generators legitimately rewrite files identically, inspect diff |
| Frontend | `npm ci --no-audit --no-fund`, `npm audit --audit-level=low`, `npm run typecheck`, `npm test`, `npm run build` | 217Vitest+1Node, type/build/audit exit0 onNode22 |
| Mock browser | Install Chromium; owned port; `npm run test:e2e` | 398 cases; no unintended skip/only/flaky; route leakage tracked |
| Full-stack | From backend with ownedDB/runID, `uv run --locked python ../scripts/test_fullstack.py` | 50 cases, fakeSDK; HEAD known1failure must resolve before green baseline |
| Custom loads | Separate owned scratch URLs, exact verify.yml `load_chat_memory.py --workers 1 --users 10 --crash-kill` and `load_social_mood.py --users 10` args/env | Workload/report acceptance preserved, no paid provider |
| Offline policy | Root `python scripts/check_reviewed_artifacts.py`, `python scripts/check_docs.py` | Exit0; current baseline docs2knownbrokenlinks before repair task |
| Release | Linux `python3 -m unittest discover -s deploy/aws/tests -v` | 19 baseline methods, newtests may increase; Windows fcntl limitation not patched away |
| Syntax/package | Pinned actionlint command and both Docker packaging steps copied from verify.yml | API/web/combined image, Compose/Caddy/proxy/secret/sourcemap/UID guards all pass |

No extra coverage percentage target. Do not introduce pytest-cov/xdist or another test framework just to report a metric. New selector/gate/compatibility tests are necessary negative tests, not implementation mirrors.

## Before/after controlled experiment

1. **Freeze input:** same application/test tree, lockfiles, exact Python/uv/Node/PW versions, runner OS/arch/CPU class, PostgreSQL/pgvector version, worker counts, load users/holds/timeouts, external egress policy. Record code SHA and actual checkout tree SHA separately; PR merge ref can differ from source head. Use audit SHA plus subsequent approved test/bugfix mapping, not unequal workload silently.
2. **Freeze protocol trước chạy:** ≥10 successful full runs/configuration for latency p50/p90; include all failed/cancelled/retried samples in reliability/cost totals. Cold/warm at least5each để nhìn cache trade-off; cache namespace isolation thay vì destructive shared cache eviction. Warm-up counted separately, không cherry-pick best run.
3. **Measure:** run created/start/end, sum job exec seconds, critical path graph, step/suite/setup/call/teardown durations; dependency installs/cache restore-save; Docker contexts/image base IDs; payload/count/seed/load percentiles. Main publish pipeline measured separately from verify; don't hide build/publish rebuild time trong verify improvement.
4. **Compare:** p50/p90 full wall-clock, queue distribution, runner-seconds/cost per change, failure/flake/skip rates, workload fingerprint và protected-invariant matrix. Median step sums không là median critical path. Confidence ranges/variation reported nếu sample nhỏ; không claim causation từ historical eight-run sample.
5. **Selection evaluation:** shadow full with planned subset, replay representative historical diffs and fault injection. Tính missed critical failures ngoài selection; zero observed không chứng minh mathematically complete, vì vậy unknown paths full fallback và mainfull còn bắt buộc.

## Coverage parity và deliberate regressions

Lưu manifests baseline/final node IDs theo framework. Union unit/integration/full-stack selection phải match expected identities; no duplicate execution khi split trừ overlapping layers có chủ đích. Với rename/merge, map old→new + invariant/preconditions/transport/viewport và mutation evidence. Intentional opt-in skips phải có reason/owner; unexpected skip increase blocks.

| Negative probe trên disposable/fakes | Gate phải bắt |
|---|---|
| Remove/block session revoke/CSRF/18+ guard; peer journal access; guest quota double-spend | Backend + affectedUI/fullstack security |
| Delay cancel/final, expired guest provider dispatch, lease stale worker finalization | Persistence/worker/privacy regressions |
| Group mention typing immediately after keyboard choice | Focused group UI + full-stackV3-D; no fill/delay workaround |
| OpenAPI/TS artifact drift hoặc shared taxonomy change | Contracts + frontend/backend consumer lanes |
| Schema0020,0023,unknown, twoheads; stamped0024missingorigin/jobtable/Authhelper/grants | CLI/readiness/preflight reject before active state write |
| Owner DB passes but runtime role cannot access required object | Runtime-role integration/preflight failure |
| WrongmainSHA/workflow/repository/event, cancelledverify, held publication, digest/attestation mismatch | Aggregate/publisher/poller refusal |
| APIhealthy but proactiveunhealthy; previousimage rejects currentDB | Faileddeploy/explicitHold, no false healthy/rollback success |
| Unknown/missing diff/base, rename across modules, selectedlane skipped/cancelled | Fullfallback or aggregatefail, never silentgreen |
| Hosted smoke missing target/account approval; raw password/signed URL in fake report | Refusal/redaction; NOT_RUN/BLOCKED notpass |

Chạy probes bằng temporary patch trong isolated authorized validation context hoặc mocks, restore only exact own patch; không reset/stash current workspace hay chạm real runtime. Do not commit injected bugs. A coding agent phải dừng nếu không thể giữ nguyên user changes khi undo probe.

## Flake/order detection

- Group picker canary20 independent fresh harness/DB runs, same synthetic actors/worker1, record failcount/trace; test `--repeat-each` trên một DB chỉ dùng nếu idempotence được chứng minh. Không đánh đồng retry-success với stable.
- Mock UI suspect families20repeats, viewport/reducedmotion matrix giữ đúng; event synchronization based on observable state, count first-attempt failures.
- Backend forward/reverse và seeded shuffled representative DML/DDL/worker subsets; harness tạo new owned DB cho each order. No blanket pytest-random plugin installation cần thiết nếu explicit node list đủ.
- Full-stack `fullyParallel=false/workers1` giữ nguyên cho đến namespaced accounts/controls; suite nhiều journeys có global mutable controls và intentionally long interactions.
- Timeout budgets không tăng trong performance task khi chưa root cause. Trend report flaky/nonblocking khác release verification mandatory.

## Success/failure criteria

| Metric | Acceptance / target |
|---|---|
| Protected security/regression invariants | 100% parity, zero known critical misses; blocking |
| Unexplained missing/skip cases | 0; 4 baseline opt-in skips report separately |
| Required CI real AI calls / hosted DB writes | 0 |
| Main release semantics | Exact currentmain push successfulfullverify, SHA/digest/attestation/hold negative tests100% refusal |
| Schema preflight | Known0020→0024 mismatch blocked beforecutover; readiness/worker failclosed |
| Full verify latency | **ESTIMATE** p50≤15min (aspirational11–15), p90≤18min onmatched10+ samples |
| Selected PR / docs-only | **ESTIMATE**3–7min / <2min, criticalpathdependent |
| Runner cost | **ESTIMATE**≤120% matchedbaseline full runner-seconds; also reduce duplicatepushwork |
| Flake | Zero unexplained recurrence in20canarycases; overallfirst-attempt failure rate notworse matchedbaseline |
| Cache | Measurednet savings; miss/restorefallback stillcorrect |

Missed critical regression, silent selectedskip, schema gate bypass, unexpected hosted/provider call, lost release provenance hoặc testcoverage reduction = **STOP/HOLD**, ngay cả khi CI nhanh hơn target. Latency target chưa đạt nhưng correctness/cost tốt có thể giữ fullparallel và thử profiling; ghi rõ measuredresult, không đổi target sau phép đo để gọi success.

## Verification của chính audit deliverables

- Kiểm9required Markdown files có nội dung, mọi relative links trong bộplans/evidence tồn tại, mỗi task có11fields user yêu cầu và DAG acyclic, every referenced current source path exists (futurefiles labeledcreate).
- JSON/CSV parse, framework totals match actualcollectors; `audit_inventory.py` deterministic với cùng inputs; noheuristiclabel được nói như measuredruntime.
- `git diff --check`, inspect scope onlydocs/audit tools/evidence; no `.gitignore`/workflow/businesslogic change. Baseline unrelatedbrokenlinks/fcntl limitation ghi rõ, không che bằng fabricatedpass.
- Ghi finalverificationreceipt, commit trên branchhiện tại; no push/PR/merge/deploy. [Handoff](08-agent-implementation-handoff.md) chứa exactstopconditions.
