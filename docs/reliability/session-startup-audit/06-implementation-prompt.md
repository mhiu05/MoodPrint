# Prompt độc lập cho Claude Code — task triển khai tương lai

Sao chép phần nội dung dưới đây cho Claude Code ở một task riêng. **Không chạy prompt này như một phần của audit.**

---

Bạn là kỹ sư phụ trách triển khai cải thiện session reliability cho MoodPrint. Repository: `https://github.com/mhiu05/MoodPrint`. Stack: React/Vite/TypeScript, FastAPI, SQLAlchemy async + psycopg, Supabase PostgreSQL/Auth, Docker Compose/Caddy trên một EC2, GitHub Actions và release poller. Giữ kiến trúc modular monolith, một Uvicorn worker trừ khi có scope/phê duyệt riêng.

## Nhiệm vụ

Triển khai **Option B theo từng focused tranche** trong audit, ưu tiên connection-budget containment có review và frontend session lifecycle. Mục tiêu là giảm database connection refusal và hồi phục từ lỗi tạm thời mà không làm lỏng authentication, authorization, guest expiry hoặc privacy. Không chỉ thay message lỗi.

Đọc trước toàn bộ các tài liệu:

1. `docs/reliability/session-startup-audit/01-root-cause-analysis.md`
2. `docs/reliability/session-startup-audit/02-architecture-and-reliability-audit.md`
3. `docs/reliability/session-startup-audit/03-reproduction-and-test-plan.md`
4. `docs/reliability/session-startup-audit/04-optimization-proposal.md`
5. `docs/reliability/session-startup-audit/05-implementation-plan.md`

Thực hiện quy tắc repository/AGENTS.md, đặc biệt **không tự ý sửa `.gitignore`**. Audit chỉ có tài liệu; chưa có fix đã triển khai.

## Bằng chứng baseline cần hiểu đúng

Audit ngày 30/10/2026 UTC+7 xác nhận API/web runtime cùng SHA `57b3f7fbf91967f329a80fd344421f24ff6c5e52`, khớp GitHub main tại thời điểm đó. Local branch main và workspace HEAD khác; đừng mặc định chúng là production.

- Fresh connection từ API container EC2 bị từ chối tại connect với OperationalError, phrase `too many connections for role`, role khớp `moodprint_backend`.
- Catalog chỉ đọc cùng target xác nhận role cap **10**, role connections **10**, max_connections **60**. Snapshot bổ sung có 17 client backends trong 25 activity rows (gồm background processes). Đây là role saturation, chưa phải global exhaustion.
- Production pool là **5+5 overflow**, timeout 10 s; code defaults 8+4 vượt role cap nếu overrides mất.
- EC2 có 5 DB sockets, một backend local có 5 sockets tới cùng pooler; endpoint fingerprints khớp. Local contention rất có khả năng, nhưng attribution role cho từng socket chưa chứng minh hoàn toàn. Đừng trình bày suy luận đó như quan sát trực tiếp.
- Current-container logs có 48 request_failed OperationalError và worker errors cùng class; không có endpoint nên không được gọi tất cả là `/session`. Có 2 Caddy 502 trong startup; phần lớn request errors cách xa deploy.
- Không có restart/OOM trong scope kiểm tra; CPU/credits không ủng hộ giả thuyết host quá tải. Không có bằng chứng phải tăng EC2/Supabase tier.
- SessionRoot `catch → setError → if(error)` biến một background session check lỗi thành full-screen và unmount private app. Local browser đã tái hiện authenticated → focus 500 → error; API trở lại 200 chưa đủ tự recovery nếu chưa có trigger.
- GET `/session` đã dùng cùng AsyncSession cho auth/view. Không “sửa” lại tối ưu đã có, không bỏ provider helper. Static SQL count khoảng 6–7 registered, 9 guest, chưa tính renewal/pre-ping; phải đo trước tối ưu query.
- Audit đã chạy frontend 103 tests passed, selected backend 25 passed/38 skipped, một existing Playwright test passed. Các skip không phải integration pass; chưa có 50-user production benchmark.

Revalidate thông tin có thể thay đổi bằng diagnostics chỉ đọc; không tái tạo connection storm trên production để chứng minh lại.

## Git và phạm vi làm việc

1. Kiểm tra status, giữ nguyên uncommitted changes của người dùng. Dùng worktree riêng nếu cần; không stash/reset/overwrite tùy tiện.
2. Fetch và xác định latest **reviewed** `origin/main`, review delta so với audit SHA ở auth/session/guest/database/deploy. Nếu implementation assumptions đã thay đổi, cập nhật plan dựa trên evidence trước khi code.
3. Tạo feature branch, ví dụ `fix/session-startup-reliability`, từ reviewed main đó. Không triển khai trực tiếp trên main.
4. Minimal focused changes, không unrelated refactoring, redesign UI, dependency upgrade, generated churn hoặc P2 architecture changes không có benchmark.
5. Không tự tạo/sửa DB role/schema/index, credentials hay AWS/Supabase configuration. Nếu cần thao tác vận hành, hoàn tất code/tests/diff/runbook cụ thể trước rồi xin approval riêng cho đúng thao tác.

## Yêu cầu triển khai

### A. Budget và isolation

- Inventory mọi process/environment dùng runtime role, gồm local development và deploy overlap. Dùng role/pooler/global capacity thực tế, không chỉ `pool_size` của một process.
- Đề xuất tách dev khỏi production target/credential và preset có headroom. 5+0 cho production sau khi dev tách là **ứng viên benchmark**, không tự động là cấu hình tối ưu.
- Không tăng role/max_connections/pool/workers mù quáng. Không dừng backend local, terminate DB sessions hoặc sửa production env nếu chưa được phê duyệt cụ thể.
- Cập nhật example config/runbook/tests liên quan; rollback config cũng phải tuân budget tổng.

### B. Session lifecycle và recovery

- Tách cold bootstrap khỏi revalidation của session đã xác thực.
- Bootstrap không render private trước server 200 + validateSession hợp lệ.
- Một transient revalidation failure không unmount private tree ngay; state degraded chỉ giữ snapshot đã được phép trong memory, grace tối đa 30 s từ failure đầu. Không reset grace bởi focus/online/manual retry.
- Trong degraded, disable writes và stop new private reads/streams; session retry là luồng riêng. Hết grace clear private content. Không persist private snapshot/CSRF vào browser storage.
- 401/session revoked/logout/guest T clear session/private caches/CSRF ngay, abort requests/timers, invalidate epoch/generation. Session authorization 403/ACCOUNT_SUSPENDED phải blocked/clear, không coi như outage.
- Đừng biến mọi 403 của một business action thành global logout: phân biệt CSRF_DENIED, REAUTH_REQUIRED và domain deny theo contract.
- Giữ guest monotonic deadline và cross-tab signals sống qua error UI; không remount bằng serverTime cũ rồi gia hạn trial. Server T/output guard không đổi.
- Một owner/coordinator cho focus/visibility/online/guest revalidation; coalesce event burst và một in-flight read/lifecycle. Không còn hai `/session` checks từ root + guest.
- Generation + api epoch phải chặn cả late success và late failure sau logout/revocation/new login/consent receipt. Giữ AbortController và existing anti-resurrection guards.
- Recovery messages bằng tiếng Việt, không hứa draft đã lưu nếu chưa có persistence evidence.

### C. Transport/retries

- ApiError giữ thêm retryable và requestId/header X-Request-ID, tương thích call sites cũ.
- Timeout có REQUEST_TIMEOUT riêng; caller abort/cleanup im lặng. Không bỏ timeout hoặc đổi global timeout của SSE/AI/upload.
- Chỉ retry GET session: tối đa 3 attempts/cycle, total budget 20 s, mỗi attempt ≤min(8 s, remaining), exponential full jitter; tham số là baseline đề xuất cần đo lại ở staging.
- Retry transient network/timeouts, 502/503/504, 500 khi retryable; 429 tôn Retry-After seconds/date trong remaining budget. Không retry 401, authorization 403, INVALID_SESSION, validation bug hay caller cancellation.
- Không generic retry writes/login/guest creation/AI/upload/streams. Không replay ambiguous write; giữ idempotency keys hiện tại.
- Tránh nhân retry giữa browser/proxy/backend; chưa thêm backend transaction retry trong tranche đầu.

### D. Backend classification và observability

- Map đúng connection-limit refusal, transient connection unavailable, pool acquisition timeout sang 503 retryable theo stable code và Retry-After hợp lý. Unknown/programming errors vẫn 500; không broad catch mọi SQLAlchemyError.
- Ưu tiên SQLSTATE, fallback allowlist phrase matching trong memory cho connect errors có sqlstate=None. Không in raw driver exception/SQL/params/DSN.
- Request events có UTC timestamp, request ID, route template, status, duration, release SHA và safe category/type/SQLSTATE. Không user IDs, raw path/query, headers/body/cookies/tokens.
- Wire release SHA từ deployment state tới app qua config/compose thay vì đọc Docker socket. Test compatibility của rollout/rollback.
- Đo pool occupancy và acquisition duration; phân biệt wait/connect/pre-ping. Query counts registered/guest/renewal phải đo được; không mở nhiều sessions song song để tối ưu khi cap đang đầy.
- Không cache/bỏ provider-session/revocation/consent/eligibility checks. Chưa thêm index hoặc đổi pooling mode trước khi benchmark chứng minh cần.

## Tests bắt buộc

Tạo failing regression tests trước implementation và xác nhận chúng fail vì đúng behavior. Theo test matrix của audit, tối thiểu phải có:

- Bootstrap/revalidation 401, 403, 429, 500, HTML 502/503/504, malformed JSON/session, network và timeout.
- Focus+visibility+online burst, duplicate guest checks, bounded retries/deadline/Retry-After/jitter bằng fake timers.
- Caller abort, StrictMode cleanup, epoch reset, logout, new login và late success/failure races.
- Guest deadline trong pending request/backoff/error/remount/cross-tab; không một private guest byte/unauthorized write được phép vượt server policy.
- Secret canaries trong exception; response/logs không leak và không hide programming errors thành transient.
- Local role-limit lab: cap 10, hai consumers synthetic; connection thứ 11 bị từ chối, endpoint 503 không 401; release slots → recovery không restart.
- Full relevant auth/guest/CSRF/revocation/readiness/backend integration, frontend unit/typecheck/build, browser tests và local fullstack. Đăng ký spec mới trong Playwright testMatch allowlist.

Dùng riêng PostgreSQL loopback disposable `_test`; đọc guard/fixtures trước chạy vì chúng reset schema. Không dùng hosted DB cho test suite. Fake model/STT, không spend provider budget thật. Báo riêng pass/fail/skip/not-run, không gọi skip là pass.

Staging: xác nhận target/budget và synthetic identities, chạy 1/10/25/50 users với ≥1.000 session reads, warm/cold pool, renewal và worker mix; đo percentiles/counts đúng cách. Acceptance đề xuất: p95 <2 s/p99 <5 s, không unexpected 5xx ở successful-path run, controlled errors/recovery ở injected-failure run, có headroom. Nếu chưa đạt, phân tích số đo thay vì nới limits.

## Release và rollback

- Hoàn tất local + staging verification, code review, exact-SHA CI và báo cáo trước khi đề nghị rollout.
- **Production deployment chỉ sau explicit approval.** Approval đọc AWS của audit không phải approval deploy/change env/DB cho task này. Không tự merge, publish/deploy hay migrate.
- Cung cấp concrete diff, image digests, config budget, known risks, verification commands và rollback trước approval.
- Rollback bằng previous reviewed API/web image pair, giữ DB revision compatibility, không downgrade schema/nới readiness. Config rollback vẫn dưới connection budget.
- Rollback/stop rollout nếu có private resurrection, guest T extension, unauthorized write, secret leak, retry storm hoặc session error/latency vượt ngưỡng operator đã chốt.

## Báo cáo cuối task triển khai

Viết tiếng Việt: thay đổi nào sửa connection refusal, thay đổi nào chỉ giảm tác động UI; files/commits; evidence/tests với số pass/fail/skip; local/staging capacity trước/sau; phần attribution còn chưa chắc; production có được thay đổi hay chưa; rollback thực hiện được thế nào. Nếu còn bước cần approval, chuẩn bị kết quả review được rồi nêu đúng action cần phê duyệt. Không tuyên bố incident đã hết chỉ dựa trên readiness 200.
