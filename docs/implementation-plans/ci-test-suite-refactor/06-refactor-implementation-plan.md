# CI/Test Suite Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` task-by-task. Use subagent-driven-development only when the execution session authorizes delegation. Checkboxes are future tasks, not changes executed in this audit.

**Goal:** Giảm CI wall-clock và maintenance cost, giữ security/regression coverage và exact-main release safety.

**Architecture:** Freeze evidence → taxonomy/ownership → independent full lanes → fail-closed PR selection. Main luôn full; hosted preflight dùng candidate image/runtime role trước activation. P5 có risk priority P0, có thể triển khai sớm sau safeguards dù phase numbering theo yêu cầu.

**Tech stack:** Python3.12.13/uv0.11.14, FastAPI/SQLAlchemy/Alembic/pytest9.1.1, React/Vite/TypeScript/Node22 CI/Vitest5.0.5/Playwright lockfile, PostgreSQL17/pgvector0.8.2, GitHub Actions/Docker/Caddy/EC2.

**Spec:** [Audit](00-executive-summary.md), [test architecture](03-target-test-architecture.md), [CI architecture](04-target-ci-architecture.md), [compatibility](05-production-compatibility-gates.md), [validation](07-validation-and-benchmark-plan.md).

## Global constraints

- Branch hiện tại; không tạo branch/worktree/switch/stash/reset hoặc overwrite uncommitted changes; không tự sửa `.gitignore`.
- Source baseline `a3af3d4cef1c7de75b2ec2b65ea5743640fbb853`. HEAD CI có C08 failure; không giả green control run.
- Evidence trước deletion/merge; security/privacy/auth/18+/migration và fake-SDK regressions giữ nguyên.
- Giữ workflow name/path/ID394882427 và check `verify`; exact successful push/current-main/same-repo/full verification, publication hold/digest/attestation/poller semantics không đổi.
- DB reset chỉ owned disposable loopback. Audit production inspection chỉ read-only. Deploy/migration/settings mutation/paid calls cần scope phù hợp ở session sau.
- Không đưa runtime secrets, tokens, raw hosted data hoặc signed URLs vào artifacts. Required CI real AI calls0.
- Một task hoặc independent helper family mỗi commit sau verification; không push/PR/merge/deploy khi chưa được yêu cầu.

## Review focus

1. Mixed unit/DB và self-managed scratch tests không được mất coverage do marker selection (P2-01).
2. Unknown/renamed paths, missing base, planner failure, cancelled/skipped selected lanes không được silent green (P4-01).
3. Main docs-only vẫn full; PR/dispatch/wrong-SHA success không thành release eligibility (P0-03/P3-01).
4. Claimed0024 thiếu catalog/ACL và worker heartbeat sống dù schema lỗi phải fail gate (P5-01/02).
5. Keyboard race không che bằng retry/delay; previous image không compatible current DB không gọi rollback success (P0-02/P5-02).

## Dependency order

```text
P0-01 → P0-02, P0-03
P0-03 → P1-01 → P1-02
P0-01 + P0-02 → P2-01 → P2-02 → P2-03
P2-01 + profiling → P2-04 (optional)
P1-02 + P2-01 + P0-03 + green control → P3-01 → P3-02
P3-01 + P2-02 → P4-01 → P4-02
P0-03 → P5-01 → P5-02 → P5-03
P3-02 + P4-02 + P5 guards → P6-01 → P6-02
```

P0-01 chỉ hoàn tất instrumentation, không yêu cầu successful control runs trước khi P0-02 được phép diagnose failure. P0-02 nếu xác nhận product bug ngoài scope thì handoff bugfix riêng và giữ blocker trước CI cutover. P5 phải xong trước deploy candidate0024 vào project đang0020; không chờ hết performance work nếu release sắp tới.

### P0-01 — Baseline và measurement safeguards

- **Priority:** P0
- **Objective:** Có timing, test identities và environment provenance trước tối ưu.
- **Files:** Create `scripts/ci/benchmark.py`, `scripts/ci/tests/test_benchmark.py`; modify `.github/workflows/verify.yml`. Tham khảo audit collectors hiện có.
- **Dependencies:** None; kiểm tra status/branch/HEAD trước khi sửa.
- **Interfaces:** `summarize_runs(runs: list[dict], jobs: list[dict]) -> dict`; schema1 có source SHA, checkout tree SHA, attempt/event, queue/workflow/job/step seconds và cache/tool versions. Missing/negative timestamps phải unavailable, không phải 0.

**Implementation steps:**

- [ ] Viết reducer tests cho overlapping jobs, queue, failed/cancelled/retried attempts và timestamps lỗi. Wall-clock và sum runner-seconds phải khác nhau đúng cách.
- [ ] Tách timer cho Ruff/mypy/pytest/OpenAPI export, npm install/audit/tsc/unit/build, browser install/E2E, full-stack, Alembic và Docker; giữ nguyên commands và exit codes.
- [ ] Thêm pytest JUnit/setup-call-teardown durations và fixture closure manifest; upload content-free timing/count artifacts trên `always()`, raw failure evidence theo retention hiện có.
- [ ] Hoàn tất instrumentation và thu receipt cho baseline đang fail. Chuyển successful control sampling sang P0-02 sau khi failure được giải thích/xử lý; P6 mới yêu cầu10 matched samples. Không overwrite original baseline.

- **Acceptance criteria:** Node IDs/counts và semantics không đổi; có timing receipt cả khi failure; tách được queue, suite time và runner sum.
- **Tests to run:** `python -m unittest discover -s scripts/ci/tests -p test_benchmark.py -v`; actionlint và full verify commands ở07.
- **Expected impact:** Có cơ sở đo; overhead mục tiêu ESTIMATE <10s/run.
- **Risks:** Instrumentation có thể che original exit code hoặc upload secrets; chỉ lưu allowlisted metrics.
- **Rollback:** Revert timing/upload commit, giữ raw baseline artifacts và original commands.

### P0-02 — Chốt nguyên nhân baseline failures

- **Priority:** P0
- **Objective:** Giải thích V3-D failure và sửa hai documentation links đã đứt trước benchmark.
- **Files:** Inspect `frontend/tests/fullstack/v3.spec.ts`, `frontend/src/features/real/groups/GroupChat.tsx`, `mentions.ts`, `mentions.test.ts` trong cùng groups directory. Docs: `docs/implementation-plans/proactive-multi-agent-companion/01-current-codebase-audit.md`, `docs/supabase/journal-storage.md`. Test edits chỉ sau root cause.
- **Dependencies:** P0-01.

**Implementation steps:**

- [ ] Inspect synthetic trace run41410267512. Reproduce V3-D trong 20 fresh owned harness/DB runs, worker1; record key/input/caret/rAF ordering và first-attempt failures.
- [ ] Thêm focused keyboard-picker regression giữ expected text/caret/member. Chỉ sửa test synchronization nếu chứng minh test chờ sai observable. Nếu source có real user-facing race ngoài scope, dừng và handoff business bugfix riêng.
- [ ] Sửa hai links bằng maintained guide/source hoặc mô tả historical artifact unavailable; không tạo evidence PASS giả, không restore cả thư mục đã xóa.
- [ ] Sau khi nguyên nhân được xử lý trong scope phù hợp, chạy focused canary và whole full-stack; giữ nguyên assertions của journey.
- [ ] Sau khi có green control run, thu ít nhất5 successful full runs cho baseline kiểm soát; retain failed samples riêng. Việc này không là điều kiện để bắt đầu diagnosis.

- **Acceptance criteria:** Root cause có evidence; full green control run hoặc blocker explicit. `check_docs.py` không còn hai broken targets sau task docs repair. Không tăng retry/timeout để che lỗi.
- **Tests to run:** Từ backend: `uv run --locked python ../scripts/test_fullstack.py v3.spec.ts --grep 'V3-D'`; lặp bằng 20 fresh owned targets theo07. Whole full-stack và `python scripts/check_docs.py`.
- **Expected impact:** Baseline đáng tin; giữ high-value regression.
- **Risks:** Repeat trên cùng account state có thể tạo order dependence. Không thay keyboard typing bằng `fill` khi behavior cần bảo vệ là picker/caret.
- **Rollback:** Revert diagnostic/test/doc changes riêng; giữ original failing assertion và report blocker.

### P0-03 — Khóa release provenance contract

- **Priority:** P0
- **Objective:** Bảo vệ exact-main release semantics trước khi sửa CI DAG.
- **Files:** Modify `deploy/aws/tests/test_poll_release.py`, `test_guest_release_hold.py`; create `scripts/ci/tests/test_release_workflow_contract.py`. Inspect hai workflows, `deploy/aws/poll_release.py`, `release_hold.py`; không rewrite publisher.
- **Dependencies:** P0-01.

**Implementation steps:**

- [ ] Bổ sung negative fixtures: PR success, wrong/current-main-moved SHA, wrong workflowID/path/repo, cancelled CI, publication hold, tampered digest/ref/revision/attestation, stale publish run.
- [ ] Test workflow/gate có mandatory lane fail/cancel/skip: không được tạo successful publish-eligible verification.
- [ ] Mock manual-dispatch CI-run lookup: command phải explicit GET khi có `-f` fields. Test phải fail với command hiện tại, trước fix trong P1-02; không gửi POST hoặc dispatch thật để verify.
- [ ] Đọc classic protection và effective rules; ghi exact check name. Viết owner instruction để set required `verify` sau canary; không tự đổi settings.

- **Acceptance criteria:** Supported release fixtures pass, negative matrix refuse. Giữ workflow name/path/ID394882427, push-main/currentSHA, owner approval, hold, digest/OCI/manifest và permissions separation.
- **Tests to run:** Linux `python3 -m unittest discover -s deploy/aws/tests -v`; new workflow contract unit tests; actionlint và actual failure-path canary lúc P3.
- **Expected impact:** Không giảm runtime; tránh release safety regressions.
- **Risks:** Textual YAML snapshots có thể chỉ mirror code. Cần semantic fixtures và actual injected-failure canary, không chỉ regex.
- **Rollback:** Sửa/revert test expectations sai; không nới production gate để làm test xanh.

### P1-01 — Trigger cleanup và PR-only cancellation

- **Priority:** P1
- **Objective:** Giảm duplicate push/PR work mà không cancel main/release.
- **Files:** `.github/workflows/verify.yml`, workflow contract tests, `docs/development.md`.
- **Dependencies:** P0-03.

**Implementation steps:**

- [ ] Chuyển push trigger chỉ main, giữ pull_request và thêm workflow_dispatch full cho branch chưa có PR. Giữ workflow name/path/ID.
- [ ] Dùng PR-number concurrency và unique run group cho non-PR; cancel-in-progress chỉ true cho PR theo04. Giữ publisher concurrency hiện tại.
- [ ] Canary cùng PR update tạo một verification event; superseded PR bị cancel, hai main runs không hủy nhau, manual branch không publish-eligible.

- **Acceptance criteria:** Main push full còn được tạo và completed; PR merge-ref coverage được giữ; feature branch chưa PR có hướng dẫn local/manual rõ ràng.
- **Tests to run:** Workflow contract/actionlint, event fixture matrix, actual PR canary và two-main event simulation; Linux release tests.
- **Expected impact:** Bỏ extra feature push work; hai push jobs trong successful pairs của sample là47:47 runner-time cơ hội. Không hứa giảm latency một run.
- **Risks:** Branch chưa mở PR không có automatic full push checks; đây là trade-off cần ghi rõ.
- **Rollback:** Revert triggers/concurrency; giữ main release contract và không dispatch release ngoài scope.

### P1-02 — Cleanup npm audit và manual CI lookup

- **Priority:** P1
- **Objective:** Bỏ network work lặp và sửa method lookup read-only, giữ security/release policy.
- **Files:** `.github/workflows/verify.yml`, `.github/workflows/deploy-staging.yml`; workflow command-policy tests.
- **Dependencies:** P1-01.

**Implementation steps:**

- [ ] Đổi required frontend install thành `npm ci --no-audit --no-fund`; giữ `npm audit --audit-level=low` blocking.
- [ ] Xác minh lockfile không đổi và explicit audit chạy một lần; fake nonzero audit vẫn fail workflow.
- [ ] Thêm `--method GET` vào `gh api .../runs` manual lookup có fields; giữ head_sha/branch/event/status/workflowID/path/repository/current-main checks. Verify bằng fake `gh`/command contract, không chạy publish thật.

- **Acceptance criteria:** Audit threshold và drift/type/unit/build checks nguyên vẹn; install không gửi audit request lặp. Manual lookup tạo GET query đúng filters và vẫn từ chối wrong-SHA/non-push CI.
- **Tests to run:** Node22 CI install, explicit audit, typecheck/unit/build và full verify; command contract test.
- **Expected impact:** Tiết kiệm network nhỏ, chưa định lượng trước benchmark.
- **Risks:** Vô tình bỏ explicit security gate.
- **Rollback:** Revert từng command-only commit nếu có lỗi; không giảm audit threshold hoặc bỏ provenance filters. Giữ manual publication Hold nếu chưa có verified lookup.

### P2-01 — Taxonomy, markers và collection parity

- **Priority:** P1
- **Objective:** Tách unit/integration đúng behavior trước split CI.
- **Files:** `backend/pyproject.toml`, `backend/tests/conftest.py`; exact12 fixture-gap files trong `evidence/classification-facts.json`, thêm `backend/tests/test_database_operations.py` cho self-managed DB case. Create `scripts/ci/test-ownership.json`, `collect_tests.py`, `tests/test_test_classification.py` dưới scripts/ci. `frontend/vite.config.ts` chỉ mở `.test.tsx` khi có sentinel/nội dung cần thiết.
- **Dependencies:** P0-01 + P0-02.
- **Interfaces:** Collected item có nodeid/owner/layer/requires_db/live/load/migration/protected_invariants; fixture closure cộng explicit metadata cho raw/scratch DB. Unknown classification phải fail hoặc full fallback.

**Implementation steps:**

- [ ] Viết classification tests cho indirect DB fixture, mixed unit/DB file, raw TEST_DATABASE_URL/scratch, hosted live guard và opt-in load. No-DB lane không được skip DB cases rồi gọi coverage đủ.
- [ ] Mark theo từng case; chỉ module-mark khi đồng nhất. Register load/migration/security. Không dựa filename `test_live_evals.py` để quyết real network.
- [ ] Collect unit và integration node-ID lists tường minh từ classification manifest, không dùng hai marker expressions không bù nhau. Gán hosted live probe và ba opt-in load/live cases vào integration manifest với required_execution=skip_opt_in; required CI scrub opt-in variables/egress để chúng giữ4skips, không thực sự gọi provider. Unit + integration union bằng1715 baseline IDs, intersection rỗng.
- [ ] Thêm discovery sentinel phát hiện new unclassified browser spec và `.test.tsx`; policy include phải được kiểm chứng, không thêm DOM library khi chưa cần.

- **Acceptance criteria:** 991 DB-fixture cases và self-managed DB cases đều vào lane có DB; không mất parameters/node IDs; no unexplained skip. Integration selection bao gồm live-only opt-in node dù nó không có marker postgres; full required run vẫn báo4intentional skips.
- **Tests to run:** Full collect, classified unit không DB với zero unexpected skips, integration trên owned DB; dynamic Vitest/PW list; classification unit tests.
- **Expected impact:** Enables safe split; metadata tự nó chưa bảo đảm nhanh hơn.
- **Risks:** Mixed file và self-managed DB không nằm trong fixture closure; phải review cả source lẫn runtime manifest.
- **Rollback:** Tạm chạy full pytest trên một DB lane, revert selector adoption; giữ baseline manifest.

### P2-02 — Extract feature-owned helpers

- **Priority:** P1
- **Objective:** Bỏ dependency từ helper sang test modules.
- **Files:** Create `backend/tests/chat_helpers.py`, `proactive_helpers.py`, `memory_helpers.py`, `support.py`. Modify exact47 consumer files/87 edges trong classification-facts; dùng existing feature helper modules khi phù hợp. Guard trong `scripts/ci/tests/test_test_classification.py`.
- **Dependencies:** P2-01.
- **Interfaces:** Giữ source signatures của enable/key/conversation/settings_body/seed_proposal/claim/provider_rows/seed_owned/user_reference_counts. Đọc definition trước move; qualified imports khi tên trùng.

**Implementation steps:**

- [ ] Một feature family mỗi commit: move utility bodies vào helper không có test definitions và không import test modules.
- [ ] Update callers/monkeypatch binding targets; AST guard reject `from tests.test_` trong helpers/consumers, trừ exception được giải thích cụ thể.
- [ ] Chạy affected consumers và full collection mỗi commit; whole backend sau khi family complete.

- **Acceptance criteria:** 87 import edges về0 hoặc explicit reviewed exceptions; giữ test names/assertions, không cycle/import side effects mới.
- **Tests to run:** Classification AST guard, Ruff/current mypy scope, whole backend owned DB; đặc biệt guest cleanup/recovery, chat/memory, proactive/collaboration/orchestration.
- **Expected impact:** Giảm maintenance cascade; runtime savings chưa đo.
- **Risks:** Monkeypatch binding/import order đổi dù helper body như cũ.
- **Rollback:** Revert từng family commit, restore original signatures/imports, không reset user branch.

### P2-03 — Browser invariant ownership

- **Priority:** P2
- **Objective:** Dọn repeat setup, chỉ merge behaviors thực sự tương đương.
- **Files:** `frontend/tests/e2e/merge-readiness.spec.ts`, `ux-redesign.spec.ts`, `real.spec.ts`, `ux-fixtures.ts`; create `docs/testing/browser-invariant-map.csv`; optional new `frontend/tests/e2e/chat-fixtures.ts` setup helper.
- **Dependencies:** P2-02; C08 baseline resolved/handoff trước full cutover.
- **Interfaces:** CSV old_nodeid/invariant/preconditions/transport/viewport/new_nodeid/mutation_probe/decision.

**Implementation steps:**

- [ ] Map137 cases của ba files; phân biệt URL/history/New/cancel/scroll/privacy/a11y và viewport/race window.
- [ ] Extract repeat route/session setup trước; không bỏ assertions để giảm count.
- [ ] Chỉ đề xuất merge sau equivalent preconditions/action/outcome/layer/viewport và deliberate fault làm replacement fail; thiếu evidence thì Keep.
- [ ] Nếu split file theo owner, cập nhật Playwright allowlist/discovery sentinel cùng commit.

- **Acceptance criteria:** Protected invariants còn negative probes; mọi old node có mapping/decision; mặc định không remove.
- **Tests to run:** Dynamic mock collection, full mocked E2E, affected repeat canaries; full-stack chat/V3 journeys; invariant matrix review.
- **Expected impact:** Maintainability trước, speed chưa định lượng vì workers/file scheduling có thể đổi.
- **Risks:** Gộp các race windows khác nhau hoặc làm mất parameterized coverage.
- **Rollback:** Revert candidate commit, restore old tests; giữ matrix và evidence.

### P2-04 — Fixture reset experiment có giới hạn

- **Priority:** P2
- **Objective:** Giảm DB setup nếu profiler chứng minh chi phí đáng kể.
- **Files:** `backend/tests/conftest.py`; giữ guards trong `database_target.py`. Create `backend/tests/database_reset.py`, `test_database_reset_isolation.py`; old fixture tiếp tục phục vụ DDL/role/migration.
- **Dependencies:** P2-01 + P0 profiling. Optional, không blocker P3.
- **Interfaces:** `async reset_dml_database(engine) -> None`; explicit function-scoped `dml_database`; không mặc định share async engine qua incompatible loop scopes.

**Implementation steps:**

- [ ] Profile setup/call/teardown; chọn một DML-only family, không thay global default.
- [ ] Viết contamination tests cho rows/sequence/function/trigger/settings/leaked task/connection; DDL catalog mutation không được vào DML reset lane.
- [ ] Implement explicit reset với owned target checks. Không dùng outer rollback mặc định vì app có nhiều committed connections/background tasks.
- [ ] So forward/reverse/seeded shuffle với old full reset trên fresh DB/resource tương đương.

- **Acceptance criteria:** Zero order dependence/contamination; constraints và safety refusal parity. Chỉ adopt nếu net setup giảm≥20% trong experiment;20% là target ESTIMATE.
- **Tests to run:** New isolation tests, guest cleanup/recovery, proactive lock/lease, migration và whole backend representative permutations; JUnit durations.
- **Expected impact:** Chưa đo; không report target như measured saving.
- **Risks:** Cao với multi-connection app và persistent private functions/triggers.
- **Rollback:** Route thử nghiệm về original fixture; tạo fresh owned target sau failure, chỉ cleanup exact owned scratch DB.

### P3-01 — Parallel full lanes và aggregate verify

- **Priority:** P1
- **Objective:** Rút critical path, giữ full regression và release eligibility.
- **Files:** `.github/workflows/verify.yml`; create `scripts/ci/gate.py`, `tests/test_gate.py`; workflow contract tests và development docs. Publisher/poller chỉ cần contract verification.
- **Dependencies:** P1-02 + P2-01 + P0-03 + clean control run P0-02.
- **Interfaces:** `evaluate_gate(selection: dict[str,bool], results: dict[str,str], *, full_required: bool) -> tuple[bool,list[str]]`; workflow gọi helper thật bằng JSON needs. Initial selection all true.

**Implementation steps:**

- [ ] Tests selected lane fail/cancel/skip/missing, planner failure, all-success, main partial refusal.
- [ ] Move exact commands vào lanes04; DB service/run identity riêng cho backend integration, migration/load, full-stack; static không DB.
- [ ] Giữ final ID/name verify, if always, needs tất cả lanes; không continue-on-error cho mandatory lane. Cleanup always chỉ owned targets.
- [ ] Full-stack workers1/mock workers2 ban đầu; giữ3 Docker contexts/proxy/low audit và no artifact trust shortcut.
- [ ] Inject failure/cancel/skip trên PR canary, chứng minh workflow không success/publisher refuse; remove injected fault trước commit.

- **Acceptance criteria:** Full node/skip semantics parity; main bắt buộc mọi lane; workflow ID/provenance giữ nguyên; không shared DB race.
- **Tests to run:** Gate/contract/actionlint tests, all current commands, actual canary, Linux release tests, fresh DB Alembic chain.
- **Expected impact:** ESTIMATE full median11–15min; repeated setup có thể tăng runner cost.
- **Risks:** Skipped-needs thành green, runner quota/queue, duplicate installs.
- **Rollback:** Revert DAG commit về sequential verify, external required check name vẫn verify.

### P3-02 — Cache có net savings được đo

- **Priority:** P2
- **Objective:** Giảm repeated setup, giữ reproducible installs và trust boundary.
- **Files:** Verify workflow; deploy-staging workflow chỉ cache flags sau provenance tests. Dockerfiles chỉ cache mounts không đổi recipe semantics nếu cần; benchmark cache metadata.
- **Dependencies:** P3-01.

**Implementation steps:**

- [ ] Pin reviewed setup-uv/cache action SHA, uv0.11.14/Python3.12.13; key OS/arch/lock, cache downloads/wheels, luôn locked sync.
- [ ] Giữ npm cache; thử Playwright browser-only versioned cache, vẫn install system deps. Không cache env/auth state/traces/node_modules mutable.
- [ ] BuildKit scopes api/web/combined riêng; release cache chỉ trusted main write; runtime secrets không vào args/layers/cache.
- [ ] Đo ít nhất5cold+5warm paired samples; chỉ adopt nếu restore+save+miss overhead nhỏ hơn saved work. Image reuse giữa verify/publish là project khác.

- **Acceptance criteria:** Lock drift0; cache hit/miss/overhead rõ; cache absent vẫn pass; untrusted cache không quyết released source/digest.
- **Tests to run:** Full cold/warm verify, secret/sourcemap/UID/Caddy checks, release contracts; missing/corrupt cache canary.
- **Expected impact:** Tùy measurement, chưa có numeric claim.
- **Risks:** Cache poisoning, contention và restore/save overhead.
- **Rollback:** Disable cache restore/save/scope đã thêm; giữ pinned versions/full commands.

### P4-01 — Dependency selection fail-closed

- **Priority:** P2
- **Objective:** Skip unrelated PR lanes sau shadow validation.
- **Files:** Create `scripts/ci/dependencies.json`, `selection.py`, `tests/test_selection.py`; modify verify workflow/gate/development docs; consume ownership manifest.
- **Dependencies:** P3-01 + P2-02.
- **Interfaces:** `select_lanes(paths: list[str], *, event: str, base_available: bool, complete_diff: bool) -> Selection`; schema1 boolean lanes/reason codes, main push/manual full always full.

**Implementation steps:**

- [ ] Encode path matrix04 và transitive closure. Diff từ merge base, đủ history, old+new rename paths; unknown/fetch/truncation errors full fallback.
- [ ] Tests docs/frontend/backend/auth/guests/privacy/migrations/Storage SQL/taxonomy/locks/CI/deploy/test helpers, rename/delete/empty diff/base missing/traversal/unicode.
- [ ] Tests main docs-only all true, selected cancelled/skipped missing fail; không dùng PR artifacts không trusted làm release evidence.
- [ ] Shadow≥10 representative changes: full run và planned subset; sửa edges nếu critical failure ngoài subset trước enable.
- [ ] Canary selected PR only; final verify luôn xuất hiện; main full giữ exact push release eligibility.

- **Acceptance criteria:** Protected dependency closure đầy đủ; no observed critical false negatives; workflow-level paths filters không làm required check pending.
- **Tests to run:** Selection/gate/contract unit tests; actual fixture PR runs và historical changeset replay.
- **Expected impact:** ESTIMATE selected PR3–7min, docs-only<2min; critical mixed changes vẫn full.
- **Risks:** False-negative cao; new module chưa map phải full, không chỉ xét extension.
- **Rollback:** Force full planner cho mọi event; giữ aggregate/trigger contract, sửa missing edge trước bật lại.

### P4-02 — Synthetic performance và live evaluations riêng

- **Priority:** P2
- **Objective:** Mở coverage manual mà không kích hoạt paid/flaky work trong required CI.
- **Files:** Create `.github/workflows/synthetic-performance.yml`; optional manual-only `live-evaluation.yml`. Markers/dev/evaluation docs; existing load scripts, collaboration/V3 load/live tests và eval runners.
- **Dependencies:** P4-01; giữ small main loads ban đầu.

**Implementation steps:**

- [ ] Schedule deterministic owned synthetic load, fixed seed/resources/topology; nonblocking trends ở workflow riêng.
- [ ] Chỉ move current small chat/social loads khỏi main sau negative-probe parity và agreed budget; migrations luôn blocking. Default giữ chúng tới P6 review.
- [ ] Live manual runner refuse missing approved target/model/budget/accounts; hard cap và content-free artifacts. Không schedule paid calls khi chưa có authorization.
- [ ] Report five-companion baseline và V3 cases riêng; heldout không dùng tune.

- **Acceptance criteria:** Required CI real provider calls0; NOT_RUN không thành PASS; performance workflow không thay successful full verify.
- **Tests to run:** Offline harness/guard tests: live_evals, eval_preparation, conversation_eval_gate, V3 coded judge; missing budget dry run phải refuse, không cần paid call.
- **Expected impact:** Capacity/quality visibility; chưa claim main savings khi chưa chuyển load.
- **Risks:** Accidental paid call hoặc hosted write; tách workflow permissions/targets.
- **Rollback:** Disable new schedule/entrypoint; giữ offline contracts và original small main loads.

### P5-01 — Shared compatibility contract và CLI

- **Priority:** P0
- **Objective:** Reject schema/version/catalog/config mismatch trước activation.
- **Files:** Create `backend/app/core/compatibility.py`, `backend/compatibility.json`, `scripts/export_compatibility.py`, `backend/tests/test_compatibility.py`; modify main/revisions/readiness tests, `backend/app/jobs/proactive.py`, `test_proactive_worker.py`, backend/root Dockerfiles và contract lane. Reuse inspect_database/check_config sanitized patterns.
- **Dependencies:** P0-03; có thể làm trước performance work.
- **Interfaces:** CompatibilityReport/inspect_compatibility và CLI0/2/3 theo05; source accepted revisions exact0024, generated contract checked với Alembic heads; CLI không startup app.

**Implementation steps:**

- [ ] Failing tests0020/0023/unknown/multihead, stamped0024 thiếu column/table/function/grant, complete0024 pass, unsafe config/timeouts sanitized.
- [ ] Implement bounded transaction READ ONLY bằng runtime credentials; pg catalog/has privilege checks, production Settings; không trial DML/grants/migrate.
- [ ] Export/check schema1 contract, copy vào attested candidate images. Readiness dùng shared checks, generic503; public liveness không thay readiness.
- [ ] Worker schema gate trước materialization, shared health checks; không đổi proactive policy behavior.

- **Acceptance criteria:** AI off vẫn không cho0020 pass; fake head không bypass; admin role không thay runtime ACL proof; no background/AI calls khi CLI import.
- **Tests to run:** Owned DB pytest compatibility/readiness/proactive_worker/production_settings/production_imports; Alembic+runtime-role tests, export --check, all Docker guards.
- **Expected impact:** Chặn known incident class; đo readiness overhead thực tế.
- **Risks:** Over-strict gate có thể từ chối fallback image; không broaden allowlist khi chưa rehearsal.
- **Rollback:** Giữ activation Hold/compatible old image; chỉ revert nếu có alternative safety proof, không disable readiness để unblock.

### P5-02 — Host preflight và API/web/worker health

- **Priority:** P0
- **Objective:** Preflight fail phải giữ active deployment; xác nhận exact candidate identity.
- **Files:** `deploy/aws/deploy.sh`, `poll_release.py`, Compose khi health integration cần; create `deploy/aws/tests/test_deploy_preflight.py`, `fixtures/fake-deploy-tools.py`; extend poller tests/README. Không đổi manifest schema1.
- **Dependencies:** P5-01 + P0-03.
- **Interfaces:** Sanitized receipt SHA/digests/schema/check booleans/reason codes/time; CLI0/2/3; fake Docker/SSM record command order/state writes.

**Implementation steps:**

- [ ] Failing tests pull/inspect/CLI trước active install/up; failure/unavailable không write active/previous hoặc stop old containers.
- [ ] So registry digest, labels, pulled/running IDs đúng loại hash; format inspect chỉ allowlisted fields.
- [ ] Run candidate CLI với root-owned0600 runtime file, bounded timeouts, cleanup owned temp files. Sau up chờ api/web/proactive và HTTPS ready.
- [ ] Tests API healthy/worker unhealthy, unsafe owner/symlink, initial failure, main moved, incompatible previous image Hold. Không weaken OCI/manifest verification.
- [ ] Rehearse exact previous/fallback images trên post-migration schema0024; no auto DB downgrade/stamp/grant.

- **Acceptance criteria:** Preflight fail không cutover; worker included; rollback success chỉ khi compatible pair health verified; no secret logs/false deployed state.
- **Tests to run:** Linux release/preflight unittests với fake executables; `bash -n deploy/aws/deploy.sh`; actionlint. Isolated host rehearsal chỉ khi authorized, không SSM production cho unit verification.
- **Expected impact:** Ngăn bad cutover; extra preflight budget ESTIMATE≤30s.
- **Risks:** Root host commands/temp state/rollback; phải kiểm actual command ordering, không chỉ AST.
- **Rollback:** Giữ publication/activation Hold khi restore tool version; không fall through deploy bỏ preflight, giữ active runtime files.

### P5-03 — Authorized hosted smoke và deployment receipt

- **Priority:** P0
- **Objective:** Chứng minh critical hosted flows trên synthetic scope được cấp phép.
- **Files:** Create `scripts/hosted_release_smoke.py`, `backend/tests/test_hosted_release_smoke_guard.py`; nếu browser cần, new `frontend/playwright.release.config.ts`, `frontend/tests/release/smoke.spec.ts`. Deploy post-health policy/docs; không auto reset hosted fixture pair.
- **Dependencies:** P5-02; real hosted execution cần authorized target/accounts/mutations ngoài audit.
- **Interfaces:** Allowlisted environment/domain/project + owned account markers; PASS/FAIL/BLOCKED/NOT_RUN report, SHA/digests/schema/boolean checks, no content.

**Implementation steps:**

- [ ] Guard tests unknown project/domain/account, arbitrary IDs, missing approval, mutation scope, trace/password/signed URL redaction.
- [ ] Implement login/session/owner read/peer denial/history/logout theo05; persistence writes chỉ explicit approved fixtures với cleanup report; no paid AI just to verify schema.
- [ ] Missing mandatory smoke config phải BLOCKED; read-only preflight khác stateful Auth smoke.
- [ ] Nếu cần smoke trước public traffic, thiết kế/test maintenance or blue-green traffic fence và worker control; không gọi Compose health-after-up là pre-traffic proof.

- **Acceptance criteria:** Hosted receipt gắn actual running digests; negative owner/peer checks; no real user data, failure giữ Hold theo policy.
- **Tests to run:** Guard unit tests/local fake-host simulations, browser --list without secrets; later authorized staging canary, không hosted writes trong audit.
- **Expected impact:** Bắt provider/config/RLS gaps ngoài disposable CI.
- **Risks:** Tokens/cleanup và traffic/worker coordination; default hosted traces/video/screenshots off.
- **Rollback:** Giữ mandatory smoke failure là Hold, không chuyển thành pass; retain schema/identity preflight.

### P6-01 — Parity, fault injection và matched benchmark

- **Priority:** P1
- **Objective:** Đổi ESTIMATE thành measured decision trước promote.
- **Files:** New dated `rollout-evidence/` dưới audit directory; scripts/ci tests/benchmark collector/invariant matrix. Remove canary faults trước final commit.
- **Dependencies:** P3-02 + P4-02 + P5 guard implementation; P2-04 optional.

**Implementation steps:**

- [ ] Protocol07:≥10 matched successful full runs/config; giữ failed/cancelled/retried samples trong reliability/cost, baseline immutable.
- [ ] Inject missing schema/catalog/ACL, privacy/18+/quota/cancel/lease/group mention/contract drift; expected lanes fail và publisher/poller refuse.
- [ ] PR diff matrix + main docs-only, cancelled/skipped selected lane; verify full fallback và no silent green.
- [ ] Compare p50/p90 wall-clock, queue, runner-seconds, cache overhead, flake/skip rates; invariant parity không chỉ count.

- **Acceptance criteria:** Protected invariants100%, unexplained lost cases0, critical misses0, required real AI calls0; release negative matrix pass. Targets07 đạt hoặc explicit Hold/decision.
- **Tests to run:** All existing/new required commands, CI unit tests, Linux release/preflight, disposable schema/readiness/fallback matrix; hosted smoke chỉ khi authorized.
- **Expected impact:** Evidence-based rollout; không cherry-pick fast green runs.
- **Risks:** Unequal workload hoặc đổi metric sau đo để gọi success.
- **Rollback:** Force full selection/giữ canary disabled; restore sequential CI nếu aggregate parity chưa chắc. Không tự rollback production.

### P6-02 — Canary rollout, ownership và runbooks

- **Priority:** P1
- **Objective:** Steady-state workflow có owner, required check và rollback rõ.
- **Files:** Verify selection policy; `docs/development.md`, `docs/verification.md`, `docs/agents/evaluation.md`, `deploy/aws/README.md`, audit roadmap status. Repository settings là explicit owner operation riêng.
- **Dependencies:** P6-01; release activation cần scope mới.

**Implementation steps:**

- [ ] Enable parallel full trước, selected PR canary sau; main full không đổi. Quan sát≥10 PR change classes và2main pushes có run links.
- [ ] Owner set required verify sau khi check đã xuất hiện và canary đúng; hướng dẫn manual full, force-full, cache bypass, Hold runbook.
- [ ] Rewrite verification docs thành dated snapshot/current commands, tách local/disposable/hosted proof, exact tool versions/accepted revision window.
- [ ] Final report tasks/commits/measured cost/parity/flakes/gaps/rollback; stage exact files, no push/merge/deploy ngoài request.

- **Acceptance criteria:** Stable check không pending do path filter, failed mandatory lanes block publication, every candidate có Keep/Merge/Defer và evidence.
- **Tests to run:** Docs/actionlint/contracts; final full verification dry-run và poller fixtures, không cần actual publication cho unit proof.
- **Expected impact:** Maintainable rollout và vận hành rõ.
- **Risks:** Set required check quá sớm hoặc đổi tên làm branch protection mất hiệu lực.
- **Rollback:** Force full selection ngay; revert segmentation nếu cần, giữ provenance/readiness/schema Hold guards.

## Ngoài phạm vi tối ưu ban đầu

Không xdist chung DB, không tăng full-stack workers, không wholesale test relocation, không remove supported legacy modes, không lấy coverage percentage làm deletion criterion, không auto migrate/stamp Supabase, không đổi release manifest version, không publish untrusted PR artifacts. Những ý tưởng này cần design/evidence riêng.
