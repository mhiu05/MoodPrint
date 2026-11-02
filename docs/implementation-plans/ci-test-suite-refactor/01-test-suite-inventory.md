# Inventory và coverage audit

Đọc cùng [scope và số liệu](00-executive-summary.md). Source, không phải tuổi file, quyết định relevance. [JSON inventory](evidence/test-inventory.json) và [CSV](evidence/test-inventory.csv) có 291 rows với path, framework, layer, feature, CI execution, collection count, runtime nếu đo được, dependencies/fixture closure, relevance và recommendation.

## Phương pháp và ranh giới độ chính xác

`audit_inventory.py` chỉ đọc `git ls-files`, AST/source và collector evidence; không import application, không truy cập DB/network. `collect_pytest.py` dùng hook `pytest_collection_finish` để lấy node IDs, markers và closure fixture sau collection thực tế; không execute test body/DB fixture. CSV gắn feature/layer bằng heuristic và giữ null runtime nếu chưa đo; không dùng heuristic làm test selector.

Vitest dùng **dynamic collection `--no-staticParse`**: static list ban đầu chỉ thấy 155 declarations, bỏ expansion của parameterized tests; collection cuối và execution đều có 217 cases. Playwright JSON `--list` đánh dấu các tests chưa chạy là `skipped`; không được cộng chúng vào CI skip count. `source_test_functions` không bao gồm param expansion. `collected_cases=null` ở custom/unittest có nghĩa chưa được collector tương ứng đo, không phải dead.

Inventory bao gồm 25 eval implementation modules và 24 custom entrypoints, không gọi chúng là 49 test files được pytest collect. Imports eval là active gián tiếp, paid/live CLI là manual; import analysis chỉ chứng minh dependency, không chứng minh mọi branch đã execute. Helpers, config, fixtures, migrations, Docker và workflow được phân tích dưới đây nhưng không tính vào số test-file rows.

## Phạm vi execution thực tế

| Framework/lane | Discovery | Cases/files | CI và điều kiện |
|---|---|---:|---|
| Pytest | `backend/pyproject.toml`: `testpaths=["tests"]`, mặc định `test_*.py`, bao gồm `tests/live/` | 1.715 / 158 | `uv run pytest -q`, có disposable URL trong GitHub CI |
| Vitest | `vite.config.ts`: chỉ `src/**/*.test.ts` và `tests/artifacts.test.ts` | 217 / 34 | `npm test` |
| Node test | `frontend/scripts/redocly-minimatch.test.cjs` | 1 / 1 | Chạy sau Vitest qua `npm test`; không thuộc Vitest |
| Playwright mock UI | `playwright.config.ts` allowlist 23 specs dưới `tests/e2e` | 398 / 23 | `npm run test:e2e`, Chromium, Vite; chủ yếu API routes giả |
| Playwright full-stack | `playwright.fullstack.config.ts`, mặc định mọi `*.spec.ts` dưới `tests/fullstack` | 50 / 18 | `scripts/test_fullstack.py`, local FastAPI/DB, fake SDK, một worker |
| Tour compatibility | thêm `onboarding-compatibility.spec.ts` qua env | +5 / 1 | Không được workflow bật; cần inspected Driver.js fixture directory |
| Manual browser configs | `playwright.live.config.ts`, `.provider.config.ts`, `.supabase.config.ts`, `.visual.config.ts` | 4 spec files ngoài required collection | Không workflow step; live/hosted có guard/credentials; không execute trong audit |
| Owned mock config | `playwright.owned.config.ts` kế thừa allowlist mock, Vite riêng 5190 | Cùng suite, không một coverage lane mới | Manual review/debug; không CI step |
| unittest | `python3 -m unittest discover -s deploy/aws/tests -v` | 19 source methods / 3 | Main CI logs xác nhận 19; local Windows import `fcntl` fails, không gọi đó là 19 pass local |
| Direct custom checks | Danh sách dưới | Không cộng vào cases | Mỗi entrypoint có acceptance riêng |

Không có tracked `src/**/*.test.tsx` trong snapshot; include hiện tại sẽ bỏ qua file `.test.tsx` được thêm sau này. Khi bổ sung React component tests phải cập nhật include và sentinel test discovery; không cần thêm jsdom nếu chưa có test cần DOM.

### Custom entrypoints và evals

Required verify gọi trực tiếp: `scripts/disposable_postgres.py` (provision/remove), `export_openapi.py`, `load_chat_memory.py`, `load_social_mood.py`, `test_fullstack.py`, `check_reviewed_artifacts.py`, `check_docs.py`, `test_staging_proxy.sh`; workflow gọi Alembic upgrade/check, npm audit và actionlint trực tiếp. Đây là dependency graph thật, không chỉ list file tên test.

Không có direct workflow execution: `load_guest_experience.py`, `load_session_startup.py`, `load_proactive.py`, `check_sse_timing.py`, `collect_implementation_checks.py`, `verify_*`, `check_config.py`, `smoke_providers.py`, `run_live_browser.py`, `test_supabase_fullstack.py`, `test-fullstack.ps1`, `frontend/tests/perf/{motion-perf,raf-diagnose}.mjs`. Một số script được unit tests import/kiểm tra hoặc là wrapper cho harness được CI dùng; vì vậy **manual/indirect ≠ dead**. Đặc biệt `test_supabase_fullstack.py` có optional reset fixture pair và hosted flows ghi dữ liệu: không dùng script đó cho production inspection read-only.

`backend/evals/` chứa dataset/checker, matching, conversation/live/judge/report, multi-message, proactive, collaboration và V3. Tests `test_eval_preparation.py`, `test_live_evals.py`, `test_conversation_eval_gate.py`, `test_matching_eval.py`, `test_proactive_eval.py`, `test_collaboration_eval.py`, `test_multi_message_eval.py` bảo vệ offline harness/metrics/exit gates; tên `live` không có nghĩa required CI gọi model thật. `test_v3_live_eval.py` thực sự opt-in live; hai load files `test_collaboration_load.py`, `test_v3_load.py` cũng skip khi chưa opt-in. Hosted anonymous probe là skip thứ tư; guard case của nó vẫn chạy. Không có xfail/skip vô điều kiện được xác nhận là test chết.

### DB, migration và packaging

- Function fixture `database` trong `backend/tests/conftest.py` đăng ký ORM models, verify owned loopback target, drop/create metadata, cài private functions/guest/auth guards. **991 collected cases** phụ thuộc fixture đó; nhiều API/integration tests có fixture `clients` đi qua nó.
- 867 cases có marker `postgres`, 154 DB-fixture cases trong 12 files chưa có marker. Hai tập này không là phần bù: một số tests tự tạo owned scratch DB hoặc có marker mà không dùng fixture chung. [Manifest](evidence/pytest-manifest.json), [facts](evidence/classification-facts.json).
- Alembic có linear chain 0001–0024. CI upgrade từ DB rỗng và `alembic check`; tests migration như `test_guest_schema.py`, `test_journal_migration.py`, `test_private_profile_retirement_review.py`, `test_proactive_migration.py`, `test_collaboration_migration.py`, `test_v3_migration.py` kiểm constraints/ACL/data preservation. Một số rewind từ ORM schema rồi chạy upgrade; không thay thế rehearsal từ deployed revision bằng chain thực.
- API dùng DB runtime role riêng; phần lớn API fixture chạy role owner. Tests schema/role có bảo vệ ACL, nhưng không thể suy hosted runtime grants từ owner-run API tests.
- `backend/Dockerfile`, `frontend/Dockerfile`, root `Dockerfile`, `deploy/compose.{local,staging}.yml`, `deploy/Caddyfile` đều có giá trị riêng. Root image tích hợp SPA/API vẫn được verify dù publisher dùng API/web pair. Không xác nhận variant nào retired.

## C01–C08: candidates phải review, không phải danh sách xóa

| ID / phân loại | Exact evidence / paths | Đề xuất và acceptance trước thay đổi | Rủi ro |
|---|---|---|---|
| C01 — Refactor taxonomy | `classification-facts.json` liệt kê chính xác 12 files/154 cases: feedback_privacy, proactive_api/executor/policy/worker/journal/context/privacy, sharing_api, ai_inbox, matching_compatibility, auth_flows | Mark theo case thực sự dùng DB; helper/sentinel bảo đảm không có DB fixture trong unit lane. So tập node IDs bằng full collect | Mark cả file có mixed unit sẽ làm unit lane thiếu coverage hoặc chậm |
| C02 — Refactor helpers | 87 imports trong 47 files; ví dụ `collaboration_helpers.py` import `test_chat_persistence.enable` và `test_proactive_api.settings_body`; recovery import cleanup test helpers | Extract helper bodies vào feature helper modules; danh sách exact files trong facts. Giữ nguyên test names, signatures và assertions; reject cycle mới | Import side effects/monkeypatch binding khác hoặc mất tests khi di chuyển |
| C03 — Overlapping but valuable | `e2e/merge-readiness.spec.ts` 39, `ux-redesign.spec.ts` 69, `real.spec.ts` 29; cancellation/New/history/session UI xuất hiện nhiều nơi | Lập assertion matrix theo precondition, action, outcome, viewport, transport; gộp setup trước. Chỉ merge assertion thực sự tương đương sau mutation probe | Các race canonical URL, cancel-vs-finish, scroll/unread, a11y không tương đương happy path |
| C04 — Expensive setup candidate | `conftest.py:51` function reset toàn metadata; 991 cases, pytest main 524,90 s (gồm calls/setup/teardown) | Profile `--durations=0` + JUnit setup/call/teardown. Thử reset rẻ hơn chỉ DML family; DDL/role/migration/lifecycle giữ isolated reset | Schema/functions/triggers/transaction locks khác thật; chưa đo tỷ lệ setup, không hứa tốc độ |
| C05 — Manual spike / uncertain | `e2e/onboarding-compatibility.spec.ts`: comment opt-in package spike, fixture `MOODPRINT_TOUR_SPIKE_DIR`, 5 cases chỉ collect khi bật env | Gắn owner, purpose, expiry/revalidation; giữ manual spike hoặc archive nếu maintainer chứng minh sản phẩm không dùng dependency | Không coi việc không chạy default CI là đủ để remove |
| C06 — Intentional conditional/live/perf | `test_collaboration_load.py`, `test_v3_load.py`, `test_v3_live_eval.py`, hosted anonymous probe; manual load/perf scripts | Tách owned deterministic scheduled load và live model evaluation có budget. Không activate paid path trong required CI | Cost, data mutations, accidental real provider; opt-in skip phải báo gap |
| C07 — Legacy supported, KEEP | `test_eval_preparation.py`, `test_live_evals.py`, `fullstack/local-mvp.spec.ts`, `test_three_agents.py`, `e2e_server.py:94–98` | Giữ off/cohort/legacy read-only tests: users 60–69 ở V3 cohort, users 45/46 vẫn năm companion. Dataset năm bot có thể dùng baseline, không chứng minh V3 quality | Xóa theo chữ `legacy` sẽ mất rollout/rollback và history compatibility |
| C08 — High-value failing regression, KEEP | HEAD run `41410267512`, `fullstack/v3.spec.ts:127–150`, `groups/GroupChat.tsx:164–174` | Reproduce keyboard picker dưới load; trace event/caret/rAF. Root cause chưa chốt. Tách case nhỏ để chẩn đoán nếu giữ nguyên journey assertions | Có thể là real user-facing race; `fill`, delay/retry tùy tiện có thể che lỗi |

Không phát hiện exact duplicated Python test bodies theo AST. Đây chỉ là negative syntactic evidence, không chứng minh không redundant behavior. **Confirmed Redundant = 0; confirmed Outdated = 0; confirmed Dead = 0; Remove candidates được chứng minh = 0.** Các nhóm trên ưu tiên maintainability, không phải tiết kiệm bằng giảm assertions.

## Feature-level coverage

| Feature / ownership đề xuất | Bảo vệ hiện tại, source test tiêu biểu | Gap / trường hợp CI xanh vẫn lỗi | Quyết định |
|---|---|---|---|
| Auth/sessions — backend auth + frontend session | `test_auth_flows.py` login/sliding/revoke/password/reset/age/provider errors; `test_session_reliability.py` SQLSTATE/timeout; `src/api/session*.test.ts`, `e2e/auth.spec.ts`, full-stack login | Hosted Auth config, password policy/email redirect và runtime connection ACL không được mock chứng minh | Giữ API+UI khác lớp, thêm authorized hosted synthetic smoke |
| Guest — guests lifecycle | provider/provisioning, expiration, quota/budget/paid_dispatch, inflight/voice revocation, cleanup recovery; browser guest/expiry + full-stack guest journeys | Hosted CAPTCHA/anonymous provider chỉ opt-in; stale quotas/real project settings có thể khác; load_guest không required | Blocking quota/expiry/privacy; nightly synthetic capacity trước khi promote |
| 18+ — auth/security | `test_global_adult_policy.py`, `test_eligibility.py`, `test_adult_visibility.py`, `test_staff_eligibility.py`, `e2e/eligibility.spec.ts` | Clock/year/self-attestation + every new endpoint phải preserve guard; historical underage sharing fix có test `test_sharing_api::test_under_18_account_cannot_enable` | Không cắt negative eligibility để giảm CI |
| Journal/storage — journal | owner CRUD/contracts, upload reservation/replay/privacy/expiry/cleanup; `test_journal_ai.py`; mock journal UI và full-stack persistence | Storage bucket/TUS/signed URL policies thực tế không được fake storage chứng minh; migration owner khác runtime privileges | Giữ security tests, stage smoke chỉ owned synthetic objects |
| AI/memory — AI runtime | fake SDK adapter/accounting, context selection/privacy, embeddings, cancellation/recovery/persistence, SSE contracts, `test_orchestration_sdk.py`, `test_scoped_mood_tool.py`, specialists | Fake model không chứng minh model reasoning; role/feature off phải có tests; baseline 5-bot eval không là V3 quality gate | Offline contract blocking; bounded live eval riêng |
| Proactive/jobs — jobs + AI | lease fencing, two-worker exactly-once, retries/backoff, quiet times/timezones/DST, privacy/cost, worker heartbeat/pool | Compose deploy check bỏ worker; manual `load_proactive.py` không required; app startup schema guard không nằm trong dedicated worker loop | Blocking policy/lease/privacy + host preflight/worker health |
| Matching/messages/groups — social/AI groups | retrieval eligibility/query-count, v2 scorer/evals, durable connection/history, block/report/unread, aliases; groups owner/member/mention/handoff/receipts + V3 full-stack | Group keyboard failure tại HEAD; multi-process capacity/manual V3 loads chưa được required CI đo | Giữ query-bound old retrieval test và v2 exclusions vì khác invariant |
| Supabase/RLS — infrastructure/migrations | guest/journal/proactive/collaboration/V3 constraints, roles and private-schema ACL, reviewed SQL hashes, disposable target safety | ORM create_all ≠ migrations, owner connection ≠ runtime, head string ≠ complete catalog, offline review manifest chỉ đến 0019 + pending0020 | Giữ cả chain và preservation tests, thêm preflight catalog/permissions |
| API contracts — backend/frontend API | export actual OpenAPI → openapi-typescript → git diff; strict DTO/SSE parser tests; unified errors | Export không gọi DB; schema đúng vẫn hosted login lỗi; unchecked extra fields/transport state cần contract tests | Contract lane độc lập; change taxonomy/DTO kéo cả frontend/backend/full-stack |
| Deployment/config — deploy owners | production settings/import isolation, poller 19 tests, Caddy proxy, Compose config, secret/sourcemap/UID image checks | `test_staging_proxy.sh` cố ý mong ready503 khi không có DB; không là healthy production proof. Image base/download changes khác thời điểm verify/publish | Giữ packaging gates; thêm exact candidate preflight và post-deploy attestable identity |

Các regression có bằng chứng lịch sử: `git log` có `0400235a` keyboard radio stabilization, `e1a8de1f` underage sharing response, `41199819514` build-context taxonomy boundary. Tests đã bảo vệ các vùng này; không tuyên bố chúng chưa từng được detect. Sự cố schema do người dùng cung cấp và hosted metadata mới chứng minh **gap giữa môi trường**. HEAD group mention failure chứng minh suite có thể phát hiện race, không phải lý do loại bỏ suite.

## Determinism, fixtures và tài liệu cũ

`database_target.py` kiểm URL loopback, actual peer, run ID, owner/session_user/comment marker trước destructive reset; giữ nguyên. Không chạy xdist chung database. Browser mock config `reuseExistingServer: !PLAYWRIGHT_PORT` và không `forbidOnly`/`failOnFlakyTests` explicit: CI cần owned port, refuse pre-existing server, sentinel `.only`, và không coi retry xanh là ổn định. Fixed waits có trong motion/expiry UX và media capture; chỉ thay bằng observable readiness khi giữ mục đích quan sát, không xóa tất cả sleeps theo regex.

`docs/verification.md` còn snapshot head0015, không là baseline0024. `check_docs.py` trước khi tài liệu mới hoàn tất báo 2 broken links có sẵn: `docs/implementation-plans/proactive-multi-agent-companion/01-current-codebase-audit.md` → diary text-only contract đã xóa; `docs/supabase/journal-storage.md` → hosted storage smoke artifact đã xóa. Không tạo evidence giả để làm links xanh. [Baseline output](evidence/docs-baseline.txt) còn một link tạm tới file07 chưa được viết tại thời điểm chạy; link tạm này được kiểm tra lại sau khi hoàn tất bộ plans.

## Evidence và refresh

[Pytest node manifest](evidence/pytest-manifest.json), [dynamic Vitest list](evidence/vitest-collection.json), [mock browser list](evidence/playwright-e2e-collection.json), [full-stack list](evidence/playwright-fullstack-collection.json), [tour list](evidence/playwright-tour-collection.json), [local pytest no-DB](evidence/pytest-local-no-db.txt), [local Vitest](evidence/vitest-local-run.json), [Linux main excerpts](evidence/main-ci-log-excerpts.txt). Commands và exit-code semantics ở [07](07-validation-and-benchmark-plan.md).
