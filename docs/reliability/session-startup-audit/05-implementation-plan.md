# Session startup reliability — Kế hoạch triển khai

> **Cho agent triển khai tương lai:** thực hiện từng task bằng workflow executing-plans, hoặc subagent-driven-development nếu người dùng chọn delegation. Checklist dưới đây chỉ là kế hoạch; audit này không thực thi. Không deploy production nếu chưa được phê duyệt rõ ràng.

**Goal:** loại bỏ connection refusal do budget sai và giúp session startup/revalidation hồi phục có giới hạn, giữ nguyên authorization/privacy.

**Architecture:** giữ modular monolith và một Uvicorn worker. SessionRoot sở hữu một vòng kiểm tra phiên; backend trả failure contract đúng loại; tất cả consumers tuân budget role/pooler/DB đo được.

**Tech Stack:** React 19, Vite, TypeScript, Vitest, Playwright, FastAPI, SQLAlchemy async, psycopg, Supabase PostgreSQL/Auth, Docker Compose, Caddy, EC2.

**Spec:** [RCA](01-root-cause-analysis.md), [architecture audit](02-architecture-and-reliability-audit.md), [test matrix](03-reproduction-and-test-plan.md), [optimization proposal](04-optimization-proposal.md).

## Global constraints

- Bắt đầu feature branch từ latest **reviewed** `origin/main`; baseline audit là `57b3f7f…`. Nếu main đã đổi, re-review diff auth/session/deploy trước khi code.
- Giữ nguyên những thay đổi chưa commit của người dùng; dùng worktree/checkout riêng nếu cần, không stash/reset tùy tiện.
- Không tự ý sửa `.gitignore`; không refactor ngoài phạm vi, không thêm dependency nếu stack hiện tại đủ.
- P0/P1 không yêu cầu DB schema migration, tăng role/global connection limit hay đổi credential production.
- Ops containment/configuration trên production, consumer shutdown, AWS/Supabase changes và rollout đều cần phê duyệt riêng sau khi có diff/runbook cụ thể.
- Không log raw exception/SQL/params/URL/headers/cookie/token/PII. Không dùng stale session để authorize writes.
- Giữ provider-session live check, auth_version/revocation, CSRF/origin, guest deadline/output fences và consent/eligibility server-side.
- Local tests chỉ dùng mocks hoặc DB loopback disposable `_test`. Không đưa DATABASE_URL hosted sang TEST_DATABASE_URL.

## Review focus

1. 401/403/guest T phải thắng late success, kể cả đang retry/backoff và có hai tab.
2. Grace timer không được reset khi focus/online/retry hoặc GuestHost remount với serverTime cũ.
3. Abort caller/StrictMode cleanup không được xuất hiện như timeout; timer và listener phải cleanup.
4. New-connection failure theo role khác với pool wait timeout; không che programming errors thành retryable.
5. Rollback/deploy overlap và local consumers cũng tính budget; readiness 200 không xác nhận headroom.

## Thứ tự và ưu tiên

| Mức | Deliverable | Độ phức tạp | Tác động dự kiến | Dependency |
|---|---|---|---|---|
| P0.1 | Inventory/isolation/budget connection | Thấp–vừa, có ops review | Xử lý refusal đã chứng minh | Operator xác nhận consumer/target |
| P0.2 | Frontend không full-screen vì transient revalidation; terminal clear đúng | Vừa | Giảm gián đoạn/mất draft ngay | P0.1 không chặn viết/test local |
| P1.1 | DB 503 classification + safe request correlation | Vừa | Chẩn đoán/correct retryability | Exception samples đã có |
| P1.2 | Bounded retry + dedupe + abort/generation tests | Vừa | Hồi phục network/deploy, ít duplicate calls | P0.2, contract P1.1 |
| P1.3 | Pool/query measurements và local/staging 50-user validation | Vừa | Chốt capacity từ số đo | Budget, telemetry và tests |
| P2 | Query projection/index/pooling/deploy availability theo benchmark | Vừa–cao, tùy nhánh | Giảm latency/capacity cost nếu đúng bottleneck | P1 evidence, review riêng |

## Task 1 — P0.1: inventory và budget không thay limits mù quáng

**Files dự kiến:** `deploy/runtime.env.example`, `deploy/README.md`, `docs/backend/configuration.md`, `backend/tests/test_ops_config.py`; tạo runbook `docs/reliability/session-connection-budget.md` trong task tương lai nếu cần vận hành lâu dài. Không sửa runtime.env thực trong repo.

**Interfaces:** đầu vào là role limit 10, observed 10 role connections, production 5+5, consumer inventory; đầu ra là bảng max-connections cho từng environment/process, headroom và preset đã review. Topology change không nằm trong task này.

- [ ] Xác nhận latest runtime SHA/target/role limit bằng lệnh chỉ đọc ở [03](03-reproduction-and-test-plan.md); lưu sanitized evidence.
- [ ] Inventory local backend và EC2 pool; xác minh ownership/role của các connections nếu có thể, ghi rõ attribution chưa chắc.
- [ ] Định nghĩa budget tổng ≤10 có headroom, gồm deploy overlap. Benchmark ứng viên production 5+0 **sau khi local không còn dùng cùng role**; không tự áp dụng khi còn consumer chưa rõ.
- [ ] Viết config/runbook tests kiểm tra preset và warning defaults 8+4 không phù hợp role 10. Không viết test chỉ so nguyên văn implementation.
- [ ] Review concrete containment action: tách local target/role và/hoặc giảm pool maximum. Đưa diff cấu hình, ảnh hưởng, cách xác minh và rollback cho operator phê duyệt trước thao tác production.
- [ ] Trên local/staging, chứng minh fresh connect thành công, request/worker wait chấp nhận được và không vượt budget. Nếu release consumer chưa làm server slots giảm do pooler retention, chẩn đoán tiếp; không terminate tùy tiện.

**Acceptance:** mọi consumer được ghi hoặc đánh dấu unresolved; không preset nào khai báo max vượt budget; runtime change được xác minh riêng. Không gọi task ops complete chỉ vì docs đã viết.

## Task 2 — P0.2: tách bootstrap/revalidation và giữ privacy

**Files:** sửa `frontend/src/features/real/RealApp.tsx`, `frontend/src/features/guest/useGuestLifecycle.ts`, `frontend/src/components/ErrorNotice.tsx` nếu cần controlled retry UI, `frontend/src/features/real/real.css` cho banner tối thiểu. Test `frontend/tests/e2e/session-reliability.spec.ts` mới và `frontend/tests/e2e/guest-expiry.spec.ts`; đăng ký file mới trong `frontend/playwright.config.ts` vì testMatch là allowlist.

**Interfaces:** SessionRoot tiếp tục cung cấp `api`, `session`, `receive`, `logout` cho context; bổ sung một trạng thái session reliability/trigger revalidation có type rõ ràng. Guest hook tiêu thụ callback revalidation từ owner thay vì tự tạo request `/session`; giữ nguyên monotonic expiry và BroadcastChannel behavior.

- [ ] Viết test failing: authenticated → focus 500; assert private tree không unmount, draft tổng hợp không mất trong grace; bootstrap 500 vẫn không có private content.
- [ ] Viết test failing: 401, ACCOUNT_SUSPENDED 403, guest T, logout và late 200 phải clear/không resurrect; error→retry không tái neo guest deadline.
- [ ] Chạy các tests mới để xác nhận fail đúng behavior hiện tại, không fail do fixture/UI selector.
- [ ] Implement state transition tối thiểu: bootstrap unavailable khác degraded, grace 30 s từ failure đầu, terminal clear; writes và new private reads/streams bị pause khi degraded. Không persist private snapshot.
- [ ] Giữ timer guest ở owner sống xuyên mọi error UI; không remount bằng old serverTime để cấp lifetime mới. Nếu chọn content-free unavailable sớm hơn grace cho guest, bảo đảm countdown/expired state vẫn chính xác.
- [ ] Manual retry không reset grace và không remount private content sau khi đã clear cho đến server 200 hợp lệ.
- [ ] Chạy targeted Playwright, guest expiry suites và frontend unit/typecheck. So sánh DOM, state và số network calls, không chỉ text lỗi.
- [ ] Commit focused frontend lifecycle change sau khi tests pass; chưa deploy.

**Acceptance:** S01–S04, S06–S09, S13–S15, S20–S23 ở test matrix đạt; 401/authz403 clear ngay; không thêm write retry hay private persistence.

## Task 3 — P1.1: DB errors và correlation đúng loại

**Files:** sửa `backend/app/core/errors.py`, `backend/app/main.py`, `backend/app/core/logs.py`; tạo `backend/app/infrastructure/database/errors.py` và `backend/tests/test_session_reliability.py`. Sửa `backend/app/core/config.py`, `deploy/compose.staging.yml`, `deploy/runtime.env.example`, `docs/backend/configuration.md` nếu thêm release SHA field; cập nhật config/privacy tests tương ứng.

**Interfaces đề xuất:**

```python
def database_failure_category(error: Exception) -> str | None:
    # Chỉ trả enum nội bộ: connection_limit, connection_unavailable,
    # pool_timeout, hoặc None; không trả message/DSN.
    ...
```

DomainError/ErrorDetail tiếp tục có `retryable` và `requestId` như contract hiện tại. Codes có thể thêm `DATABASE_BUSY`/`DATABASE_UNAVAILABLE` nhưng không đổi semantics 401/403.

- [ ] Viết test failing với driver SQLSTATE 53300; connect error `sqlstate=None` chứa phrase role refusal; SQLAlchemy QueuePool timeout; ProgrammingError/unknown lỗi. Assert 503 chỉ cho allowlist transient, unknown vẫn 500.
- [ ] Viết privacy tests nhét URL/password/token/PII canaries vào exception: response và logs tuyệt đối không chứa canaries/raw SQL/message.
- [ ] Implement classifier ưu tiên SQLSTATE + type, fallback phrase allowlist trong memory. Không broad catch mọi DB exception thành retryable.
- [ ] Emit đúng một request completion/failure event: request ID, route template, status, duration, category, exception type/SQLSTATE và release SHA. Không raw URL/path chứa ID, query string, headers/body.
- [ ] Wire RELEASE_SHA từ compose interpolation đang có trong release state tới API environment/settings để app log được actual release; test deployment fixture/rollback compatibility, không đọc Docker socket từ app.
- [ ] Test fresh-connect refusal trong local saturation lab trả 503 retryable/Retry-After thay vì 401; giữ readiness distinction. Không backend automatic transaction retry trong tranche này.
- [ ] Chạy backend targeted tests + privacy/auth/guest/readiness integration trên DB disposable; ruff/mypy với các file/suite liên quan.

**Acceptance:** lỗi refusal có category rõ, code/retryable/requestId nhất quán; unknown bug không bị che; không leak; authoritative auth behavior giữ nguyên.

## Task 4 — P1.2: retry, dedupe và cancellation có giới hạn

**Files:** sửa `frontend/src/api/client.ts`, `frontend/src/features/real/RealApp.tsx`, `frontend/src/features/guest/useGuestLifecycle.ts`; tạo `frontend/src/api/sessionPolicy.ts`, `frontend/src/api/sessionPolicy.test.ts`; mở rộng `frontend/src/api/client.test.ts`, `frontend/tests/e2e/session-reliability.spec.ts`.

**Interfaces đề xuất:**

```typescript
type SessionFailureKind = 'unauthorized' | 'forbidden' | 'transient' | 'invalid' | 'cancelled';
type SessionFailure = { kind: SessionFailureKind; retryAfterMs?: number };
export function classifySessionFailure(reason: unknown, nowMs: number): SessionFailure;
export function sessionRetryDelayMs(attempt: number, random: number): number;
```

ApiError giữ constructor cũ tương thích, thêm optional retryable/requestId metadata; request options có optional timeout budget để chỉ session override. State/coordinator nằm tại SessionRoot; không đưa generic retry vào mọi ApiClient request.

- [ ] Viết unit failing cho JSON/non-JSON 500/502/503/504/429; retryable false; INVALID_SESSION 502; network; caller abort vs REQUEST_TIMEOUT; Retry-After seconds/date/malformed.
- [ ] Fake timers/random: tối đa 3 attempts, total deadline 20 s, mỗi attempt ≤min(8 s, remaining), full jitter delay tối đa 500/1000 ms; khi delay Retry-After vượt remaining budget thì stop. Assert không timer/listener leak.
- [ ] Browser tests focus+visibility+online burst: một in-flight session check; guest không gọi endpoint lần thứ hai; epoch invalidation cancel request/backoff.
- [ ] Implement per-lifecycle in-flight guard và request generation; explicit invalidate sau consent/eligibility response không để late bootstrap ghi đè receipt mới.
- [ ] Preserve idempotency intent semantics hiện có; assert login/guest creation/writes/AI/upload/stream không tự retry.
- [ ] Test StrictMode effect cleanup và production preview; aborted old request không dùng lại làm request hiện tại, terminal loss thắng mọi pending success.
- [ ] Chạy frontend unit, typecheck, build, targeted browser và guest/auth regression; commit riêng tranche retry/dedupe.

**Acceptance:** S05–S19, S24 đạt; recovery bounded, không infinite loops, tổng attempts/counts kiểm chứng được; không làm yếu Task 2 security gates.

## Task 5 — P1.3: đo, benchmark và staging verification

**Files:** `backend/app/infrastructure/database/connection.py` nếu thêm safe pool events, `backend/app/modules/auth/routes.py` nếu đo acquire phase; tạo `scripts/load_session_startup.py` và test fixture `backend/tests/session_load_server.py` khi harness hiện tại chưa đủ; cập nhật `docs/reliability/session-startup-results.md` trong task tương lai. Không đổi query/index chỉ để instrument.

**Interfaces:** report JSON gồm release SHA, topology/budget, request counts, expected/unexpected status counts, latency percentiles, acquisition duration, checked_out/overflow/connect failures, transaction age và scope limitations. Không user IDs/URL credentials.

- [ ] Chốt baseline registered/guest/renewal SQL counts qua local engine instrumentation; xác minh static 6–7/9 và nhánh commit/recheckout.
- [ ] Pool events đo occupancy; timed session connection acquisition có thể gồm queue/connect/pre-ping, phải đặt tên đúng, không gọi toàn bộ thời gian này là pure queue wait.
- [ ] Tái hiện role cap 10 với hai synthetic consumers trên local lab như [03](03-reproduction-and-test-plan.md). Release slots trong lab rồi xác minh recovery không restart.
- [ ] Chạy 1/10/25/50 virtual users, ≥1.000 session reads, fake providers, registered + guest focus bursts và workers; ghi percentile method/sample size.
- [ ] Staging được xác nhận target/budget: refresh trong deployment, backend replacement, offline/online và slow network; synthetic identities không quyền trên production users.
- [ ] Acceptance target: p95 <2 s/p99 <5 s cho staging session mix, không unexpected 5xx trong successful-path run, không vượt budget; failure-injection run assert đúng error/recovery/security thay vì đòi zero errors.
- [ ] Nếu không đạt, dùng category/acquire/query evidence để chọn bước tiếp; không mặc định tăng pool hoặc workers.

**Acceptance:** report có raw counts tổng hợp và limitations, safety scenarios pass, role headroom được xác nhận; có concrete diff/config/rollback review trước xin production approval.

## Task 6 — P2: chỉ tối ưu khi benchmark chỉ ra bottleneck

**Files có thể đổi, cần scope riêng:** `backend/app/modules/auth/routes.py`, `backend/app/ai/persistence.py`, `backend/app/core/security.py`, `backend/app/modules/guests/deadlines.py`, `backend/app/infrastructure/database/connection.py`, `deploy/Caddyfile`, `deploy/aws/deploy.sh`, `deploy/compose.staging.yml`.

- [ ] Nếu RTT/query projection chiếm phần lớn: benchmark hợp nhất projection hoặc enrichment riêng, giữ consent/eligibility/provider/auth checks authoritative. Test response contract và revocation race.
- [ ] Nếu AiRun count scan đắt: review EXPLAIN trên staging và đề xuất index migration riêng kèm size/write cost; không auto-migrate production.
- [ ] Nếu session pooling giữ quá nhiều server slots: đánh giá transaction mode với driver/SET LOCAL/helper behavior và explicit connection budget, không chỉ đổi DATABASE_POOL_MODE string.
- [ ] Nếu deploy gap gây gián đoạn đáng kể: thiết kế blue/green same-host có readiness-before-switch và draining; tính hai pools/containers trong budget và RAM trước.
- [ ] Chỉ cân nhắc shared state/multiworkers khi single-worker measured capacity không đủ; đánh giá rate limits/stream slots/temporary state trước.

**Acceptance:** mỗi nhánh có before/after benchmark và rollback riêng, không gộp thành refactor lớn; nếu chưa có evidence thì hoãn P2 là kết quả đúng.

## Deployment verification sau khi được phê duyệt riêng

1. Review branch diff, CI trên exact SHA, generated contract drift chỉ khi contract thực sự đổi; không có `.gitignore`, secrets hay schema DDL ngoài scope.
2. Lưu previous API/web digests và approved pool preset/headroom trước rollout. Các thông tin rollback không bao gồm plaintext runtime secrets trong artifacts.
3. Sau rollout: OCI label + release SHA + log SHA khớp; hai health probes; thêm authenticated synthetic session canary có quyền hạn chế theo scope đã duyệt, không chỉ readiness.
4. Xác minh role budget/fresh read-only connect, session 5xx/category/acquire latency, focus/online recovery, 401/revocation và guest T.
5. Quan sát ít nhất một chu kỳ workload đại diện có workers và focus bursts; ghi duration/traffic sample thay vì “healthy một lần”. Không tạo load 50-user trên production khi chưa có approval riêng.

## Rollback procedures

- Rollback app bằng previous reviewed image pair qua cơ chế hiện có; check compatibility revision 0019, không downgrade DB schema hoặc nới readiness để ép chạy.
- Rollback config phải vẫn thỏa connection budget đã review. Không phục hồi 5+5 một cách máy móc khi consumer local vẫn giữ slots.
- Có thể revert từng focused commit/tranche frontend/classifier/telemetry độc lập; không tắt auth fences để chữa availability.
- Trigger rollback/stop rollout nếu có private data resurrection, guest deadline extension, unauthorized write, secret leak, retry storm, unexpected 5xx kéo dài hoặc latency vượt threshold đã chốt với operator.
- Nếu previous image cũng failure vì role cap, coi đây là incident capacity cần containment có thẩm quyền, không lặp redeploy/restart vô hạn.

## Dependencies và unresolved questions

- Operator chốt local consumer ownership, role attribution, environment isolation và budget reserve; socket evidence chưa đủ gán role cho từng consumer.
- Cần runtime failure category trên process chính và request ID của incident user để liên kết toàn chuỗi lịch sử.
- Runtime role statement/query/lock timeout, Supavisor client/server limits và mapping chưa đo đầy đủ.
- Policy grace 30 s, retry budget 20 s và staging latency targets là đề xuất cần review/benchmark; không thay security invariant.
- Monitoring thresholds/window/retention/cost cần owner quyết định; hiện agent/log groups/metric alarms chưa active trong scope đã kiểm tra.
- Không có approval triển khai production trong task audit này. Prompt handoff ở [06-implementation-prompt.md](06-implementation-prompt.md).
