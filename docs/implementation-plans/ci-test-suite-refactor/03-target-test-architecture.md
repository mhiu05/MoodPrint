# Kiến trúc testing mục tiêu

Thiết kế đề xuất, chưa thay đổi suite. Mục tiêu là dễ chọn tests, dễ xác định owner và giữ behavioral guarantees; không ép mọi file chuyển thư mục. [Inventory](01-test-suite-inventory.md) là nguồn node IDs hiện trạng, [tasks](06-refactor-implementation-plan.md) quy định thay đổi.

## Layers và blocking policy

| Layer | Scope/placement | External dependencies | PR / main / release |
|---|---|---|---|
| Backend unit/contract | Giữ `backend/tests/test_*.py`, marker/layer manifest theo case; pure policy/DTO/SDK fake adapters | Không DB hoặc provider thật | Selected PR; toàn bộ main |
| Backend integration | API/ASGI + real PostgreSQL, workers/locks/persistence, migration/privacy | Owned isolated DB; provider fakes | Selected PR theo dependency closure; toàn bộ main |
| Migration/security contract | Chain từ rỗng + từ supported prior revisions, constraints, ACL/runtime role, data preservation | DB riêng, pgvector đúng version; không hosted writes | Blocking nếu migrations/database/auth/security/shared changed; luôn main và release prerequisite |
| Frontend unit | `src/**/*.test.ts`, artifact routing và Node regression; mở rộng `.test.tsx` khi có nhu cầu | Node, deterministic input; không network | Selected PR; luôn main |
| Mocked browser | `tests/e2e`, ưu tiên fault injection/reconciliation/keyboard/accessibility | Owned Vite/Chromium, routes fake; abort unhandled network | Selected PR; đầy đủ main |
| Real local full-stack | `tests/fullstack` | Real HTTP/API/DB + fake Agents SDK/CAPTCHA, một worker/DB | Dependency closure PR; đầy đủ main; không thay bằng mock UI |
| Packaging/runtime | Dockerfiles, Compose, Caddy/proxy/security checks | Docker, no production credentials | Required infra/cross-stack PR; luôn main |
| Synthetic load/perf | Existing custom scripts + opt-in load cases | Disposable DB, fake latency, supported single-worker topology | Schedule/manual, trend nonblocking ban đầu; small load main giữ nguyên đến khi parity đủ |
| Live model evaluation | `backend/evals` runners, explicit opt-in test | Approved synthetic dataset, target/model/budget | Không thuộc required PR/main; manual hoặc separately authorized budgeted run |
| Hosted compatibility/smoke | New preflight + synthetic smoke runner | Real candidate/runtime role; allowlisted synthetic accounts | Read-only preflight blocking deploy; smoke blocking release activation sau authorization |

Nonblocking là lane riêng ngoài publish-eligible verify workflow khi failure chỉ là trend. Trong `verify.yml`, một job `continue-on-error` hoặc skipped blanket không được dùng để biến mandatory regression thành green. Required CI không tự đọc developer `.env` để lấy API keys.

## Tổ chức files và ownership

Giữ test paths hiện tại để giảm rename/import churn. Đề xuất metadata `scripts/ci/test-ownership.json` (file mới khi implement), keyed by existing path, fields `owner`, `layer`, `features`, `requires_db`, `requires_network`, `protected_invariants`. Owner là vai trò/module, không đoán GitHub handle.

| Owner đề xuất | Production modules | Test families |
|---|---|---|
| auth/session | `app/modules/auth`, `app/core/security.py`, frontend API session | auth_flows, session_reliability, eligibility/global_adult/staff_eligibility, frontend auth/session |
| guests | `app/modules/guests`, `app/jobs/retention.py` | guest_* backend/mock/full-stack |
| journal | `app/modules/journal`, frontend journal | journal_* + storage/privacy/AI context |
| AI runtime | `app/ai`, `app/jobs/proactive.py` | SDK/context/memory, multi_message, collaboration/orchestration/groups/proactive, V3 |
| social/matching | `app/modules/social`, `app/modules/matching`, activities/moderation | matching/social/profile/activities/focus/safety |
| platform/release | infrastructure database, Alembic, deploy, scripts | database safety/migrations/readiness/production configs/poller/packaging |
| frontend foundations | API client/stream, navigation/motion/components | src unit, e2e state/reconciliation/a11y |

Cross-feature tests có primary owner và dependency tags; không nhân đôi file chỉ để mỗi feature có một bản. CODEOWNERS optional sau owner mapping được duyệt, không tự gán người.

Naming: backend `test_<behavior>_<condition>_<outcome>` khi thêm mới; frontend unit `*.test.ts[x]`; browser `*.spec.ts`, tên case mô tả observable behavior. Không rename hàng loạt chỉ vì tên cũ. Markers dự kiến `postgres`, `live`, `load`, `migration`, `security`; marker không thay thế assertion/security review. Không dùng tên file `test_live_evals.py` để tự quyết external network.

## Fixture và dependency strategy

1. **Taxonomy trước split:** derive fixture closure bằng collection hook; mọi case có fixture `database` phải thuộc DB lane. Cases self-managed scratch DB được tag explicit. Unit lane fail nếu DB fixture/target/network unexpectedly activated; no DB URL không được tạo155skip rồi gọi là unit coverage đủ.
2. **Helpers theo feature:** tạo `tests/chat_helpers.py`, `tests/proactive_helpers.py`, `tests/memory_helpers.py`, `tests/support.py`; dùng existing `guest_helpers`, `social_helpers`, `collaboration_helpers`, `orchestration_helpers`, `group_helpers`. Danh sách import edges87 trong facts là exact change list, không wildcard rewrite. Tests không import một test module khác để dùng utility.
3. **DB isolation:** một disposable run identity/database cho mỗi CI lane; mỗi scratch DB tạo bằng ownership helper. Giữ actual loopback peer, marker, session_user/owner checks. Không tái sử dụng database từ khác job/run. Full-stack một worker tới khi fixture accounts và mutable controls có namespace theo test.
4. **Thử nghiệm reset có giới hạn:** profile trước. Nhóm DML-only có thể dùng clean migrated baseline + ordered truncate/reset functions sau mỗi test; DDL, advisory locking, roles, migration rewind và multi-connection lifecycle dùng database isolation cũ. Không mặc định outer-transaction rollback vì application sessions commit nhiều connection/background task. Chỉ chấp nhận nếu contamination/shuffle/reverse order parity chứng minh tương đương.
5. **Lifecycle:** close HTTP clients/AI tasks/pools trước cleanup; fail on leaked task/socket/connection, không để teardown rơi vào worker khác. Không share async engine qua incompatible event loops. Clock/UUID injected cho pure policy; expiry SQL/lease tests vẫn dùng real DB clock khi đó là invariant.

## Deterministic browser và fake provider boundaries

- CI dùng dedicated port và `reuseExistingServer=false`; refuse process không thuộc run. Full-stack harness đã refuse occupied8002/5174 và chỉ terminate owned PIDs, giữ behavior đó.
- Mock suite thêm catch-all no-external-network sentinel, dùng routes explicit; hiện log có `public/experience` proxy ECONNREFUSED dù case xanh, cần làm rõ intentional error-state test với unhandled fallback.
- `forbidOnly` trong CI, no accidental `.skip` hoặc unexpected count reduction; Playwright retry0 để đo flake ban đầu, khi dùng retry chẩn đoán phải fail on flaky hoặc xuất trend không gọi green-stable.
- Thay waits bằng UI/server observables nếu có; giữ audio capture observation window và motion negative assertions cần thời gian. Fake clock không được thay SQL expiry truth.
- Không thay `pressSequentially` bằng `fill` trong C08 trước khi biết lỗi: picker keyboard/caret chính là behavior đang được test.
- SDK required tests dùng `make_test_model`, `MoodE2EModel`, fake streaming/usage và canary data. Egress guard ngăn accidental provider calls; monkeypatch/fake failure không được fallback sang paid model.

## Regression guarantees bắt buộc

Không promote refactor nếu bất kỳ invariant dưới đây mất owner/assertion:

- Session/CSRF/provider revoke/sliding lifetime; under18 denied nhưng export/withdraw/delete an toàn; guest quota atomic reservation, time authority DB, cleanup fencing/provider orphan recovery.
- Journal/memory/peer isolation, signed capability boundaries, no private data trong logs/traces/artifacts, owner-scoped group/history/consultation receipts.
- Consent revoked giữa start/provider/commit phải fence paid dispatch và persistence; lease stale worker không finalize; concurrent operations exactly-once và lock budgets.
- V3 on/off/cohort, five-bot rollback mode, readable read-only legacy history; handoff permissions, allowed tools, journal-only specialist scope.
- Migration upgrades/preservation/constraints/ACL/runtime role, refusal of unknown/old readiness revision, exact-main release provenance, malicious manifest/digest/attestation refusal.
- Keyboard picker, New/cancel-vs-finish, draft preservation/scroll/unread and accessibility/reduced-motion/viewport contracts.

Mỗi proposed merge cần matrix `{old_nodeid, invariant, preconditions, layer, new_nodeid, mutation_probe}`. Giữ exact old node IDs trong baseline; nếu rename đã được review, map old→new; count không phải bằng chứng parity duy nhất. Không remove test chỉ do source filename cũ hoặc covered percentage tăng.

## Live evaluations và performance

Giữ offline checker khác semantic quality. Tạo matrix riêng: baseline five companions versus V3 planner/coordinator/specialists/group turns; không dùng heldout đã thấy để tune prompts. Live run requires target/model/version/budget và approved synthetic content, hard cap trước call tiếp theo, content-free report, no secrets/raw transcripts trong artifacts; quality/privacy failures không được gọi pass chỉ vì spend cap đạt.

Synthetic load scheduled initially nonblocking: record p50/p95/p99, error counts, pool peak/lease lag, compare same users/concurrency/worker/resources/seed. Small current main loads giữ nguyên trước khi chạy shadow và đồng ý chuyển lịch; migrations/security không đi cùng heavy-load downgrade.
