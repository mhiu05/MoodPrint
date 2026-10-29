# Đề xuất tối ưu reliability và so sánh giải pháp

Ngày 30/10/2026, UTC+7. Đây là đề xuất cho task triển khai riêng; audit chưa thay đổi bất kỳ cấu hình/source/runtime nào. Căn cứ: [01 RCA](01-root-cause-analysis.md), [02 architecture](02-architecture-and-reliability-audit.md), [03 tests](03-reproduction-and-test-plan.md).

## 1. Quyết định khuyến nghị

Chọn **Option B theo từng bước nhỏ**: trước hết khép ngân sách connection của role đang chạm 10/10 và xử lý đúng revalidation transient; tiếp theo bổ sung failure classification, retry bounded, correlation và tests. Chưa đổi Supabase tier, chưa tăng role/global limits, chưa thêm worker, Redis, Kubernetes hoặc microservices.

Phải tách hai loại kết quả:

- **Giảm/eliminate connection refusal:** kiểm soát mọi consumer, tách dev/prod và chốt budget dựa trên giới hạn role/pooler/DB đã đo. Đây là xử lý failure mechanism có bằng chứng.
- **Giảm tác động user-visible:** giữ đúng session lifecycle, retry reads và recovery banner. Đây không làm database bớt đầy connection; không được gọi nó là đã sửa nguyên nhân hạ tầng.

## 2. Ba mức giải pháp

| Tiêu chí | A — tối thiểu | B — khuyến nghị | C — chỉ khi nhu cầu tăng |
|---|---|---|---|
| Thay đổi | Containment budget có review; phân biệt initial/revalidation; giữ security terminal paths; banner và manual retry | A + một coordinator revalidation, bounded read retry, timeout/cancel distinction, DB exception classification, safe telemetry, tests/lab/load và query profiling | B + cân nhắc transaction pooling, lightweight session projection/enrichment, blue/green trên cùng host, rồi mới shared state/multi-process nếu có số liệu |
| Lợi ích | Tránh một lỗi transient làm mất UI; giảm cạnh tranh quota sau containment được xác minh | Hồi phục có giới hạn, xác định đúng lỗi/endpoint, kiểm chứng capacity/security cho 50 users | Giảm network/DB round trips và deployment gap; tăng capacity theo bottleneck thực tế |
| Độ phức tạp | Thấp–vừa; khoảng 1–2 ngày kỹ thuật sau khi chốt operational scope | Vừa; khoảng 3–6 ngày gồm staging/benchmark, không phải cam kết thời gian | Cao; nhiều milestone theo điều kiện, không ước lượng khi chưa có nhu cầu |
| Rủi ro implementation | Sai terminal classification, giữ private UI quá lâu, giảm pool quá mạnh | Retry storm/races, retry nhầm write, timeout không hủy sạch DB, log nhạy cảm | Thay semantics pooling, nhân DB clients khi blue/green/multiworker, shared in-memory semantics bị phá |
| Bảo mật | 401/403 authoritative và guest T clear ngay; không persist private snapshot | Giữ toàn bộ revocation/CSRF/consent/guest output fences; terminal thắng late success | Không được bỏ provider-session check; tách enrichment không được làm stale authorization |
| Performance | Ít UI remount/refetch hơn; pool nhỏ hơn có thể tăng queue wait, phải đo | Ít duplicate checks, ít attempts khi cùng lỗi; có thêm telemetry overhead nhỏ | Chỉ giảm load đáng kể nếu measured query/RTT/deploy bottleneck đúng |
| Rollback | Revert focused UI commit; hoàn nguyên config chỉ sau khi inventory budget để không trở lại incident | Image pair trước đã review; revert từng tranche/config; không schema downgrade | Mỗi change có rollback độc lập; tránh đưa schema breaking vào cùng release |
| Hạ tầng/chi phí thêm | Không bắt buộc | Không cần dịch vụ mới; nếu bật CloudWatch hiện có thì có phí ingest/retention phải review trước | Có thể vẫn một host; tách project, instance/tier tăng, monitoring hoặc shared state có thể có phí |
| Chứng cứ hiệu quả | Role có headroom + fresh connect thành công; focus transient không full-screen | Correlation logs/metrics + failure injection + 50-user mix + security regression | Before/after benchmark; deploy gap/capacity improvement đủ bù complexity |

Option A là containment có thể làm trước; không coi chỉ đổi copy/error banner là đủ. Option C không phải điều kiện để có một MVP đáng tin.

## 3. P0: khép connection budget trước khi thay limits

### Invariant

Với session-pooler topology hiện tại, cần kiểm tra thực tế mapping client/server rồi quản lý budget bảo thủ:

```text
Tổng mức tối đa của mọi process/môi trường dùng role
+ chẩn đoán/migration hoặc overlap cần dùng cùng role
+ operational headroom
<= role connection limit
<= capacity thích hợp của pooler và PostgreSQL
```

Migration hiện dùng owner khác nên không tính vào cap runtime role 10, nhưng vẫn tính vào global DB capacity. Blue/green overlap và Uvicorn workers phải nhân pool per-process. Không coi 50 concurrent users là 50 concurrent DB checkouts.

### Hành động được đề xuất cho task vận hành có phê duyệt riêng

1. Inventory API production, local backend, staging, scripts và mọi process đang dùng runtime role. Socket evidence hiện có khiến backend local là đối tượng cần kiểm tra đầu tiên.
2. Tách local development khỏi production runtime credentials/target. Dùng local disposable stack hoặc project môi trường khác thích hợp; một role khác trên cùng DB chỉ tách quota/identity, **không** tự tách dữ liệu hay global capacity.
3. Chỉ operator được phê duyệt mới dừng/đổi cấu hình consumer không cần thiết. **Audit này không dừng backend local**. Sau release/close, đo role connections và fresh-connect recovery; đừng giả định pooler giải phóng server connections tức thì.
4. Chốt production pool với headroom. **Ứng viên benchmark**, sau khi dev tách khỏi role: `pool_size=5`, `max_overflow=0` thay cho 5+5, để lại 5 slots cho headroom/consumer có inventory. Không tự áp dụng giá trị này khi chưa đo worker/API wait và xác minh các consumer còn lại.
5. Nếu local 5 connections bắt buộc vẫn giữ, tổng production maximum phải thấp hơn 5 để còn headroom; ví dụ cap 4 + 5 local + 1 reserve = 10. Đây là budget minh họa, không phải preset tối ưu cho 50 users. Ưu tiên isolation thay vì chia sẻ lâu dài.
6. Đo pool acquire wait và peak checked_out trước/sau. Nếu queue tăng thì tối ưu thời gian giữ connection/request mix trước; chỉ xem xét tăng role limit khi có số liệu global/pooler headroom và được phê duyệt riêng.

Mặc định code 8+4 lớn hơn role cap 10 là rủi ro deployment drift. Làm rõ runtime.env.example/runbook, thêm config test cho preset đã chốt; không thêm một check đơn lẻ rồi tuyên bố kiểm soát được mọi external consumer.

## 4. Frontend lifecycle đề xuất

### States và recovery policy

| State | Private content | Writes / private network | Chuyển tiếp |
|---|---|---|---|
| bootstrap | Không có | Chỉ session read | 200 hợp lệ → ready; 401 → anonymous; terminal 403 → blocked; hết retry → unavailable |
| ready | Theo session đã xác thực | Server vẫn authorize mọi action | focus/visibility/online → revalidate; giữ UI trong lúc read pending |
| degraded transient | Chỉ snapshot đã được phép, trong memory và grace có hạn | Disable writes, dừng new private reads và streams; retry session riêng | 200 → ready; 401/403 → clear/terminal; hết grace → clear private, unavailable |
| anonymous / expired / blocked | Clear private tree/caches/CSRF | Chỉ public/auth flow phù hợp | Không tự retry auth loss; guest không được gia hạn |

**Giá trị đề xuất để triển khai/test, chưa phải SLO đã đo:** grace tối đa 30 giây từ lỗi transient đầu tiên, không reset bởi focus/retry; total session-read budget 20 giây/cycle, tối đa 3 attempts. Khi hết grace phải clear private content kể cả retry cycle chưa xong. Không background cache private snapshot trong localStorage, Service Worker hoặc query cache bền vững.

Grace không có nghĩa user vẫn được authorize thêm 30 giây. Server authorization không đổi, UI chỉ giữ data đã nhận; mọi hành động phát sinh private data mới bị chặn ở degraded state. Confirmed revocation từ **bất kỳ private response** phải kết thúc grant ngay, thắng mọi late success.

Guest deadline phải tồn tại độc lập với việc hiển thị error panel. Không remount hook từ `serverTime` cũ rồi cấp lại thời gian; original monotonic anchor và BroadcastChannel expiry phải luôn hoạt động. Timer không dừng khi app hidden/offline.

### Revalidation và concurrency

- SessionRoot là owner duy nhất của network session check. Focus/visibility/online và guest lifecycle gửi yêu cầu cho cùng owner; không có request thứ hai từ guest hook.
- Coalesce focus+visibility burst, một in-flight read cho một lifecycle; event đến lúc đang đọc không mở request mới. Cho phép explicit invalidation sau consent/eligibility mutation cần đọc mới, tránh bỏ mất update quan trọng.
- Capture generation + api epoch. Logout/401/guest end/identity replacement invalidates generation và abort in-flight reads/retry timers. Late success/failure không thay state/csrf của identity mới.
- Giữ anti-resurrection guards đã có. Không sửa bằng cách bỏ AbortController, StrictMode, validator hoặc onUnauthorized.

### Retry contract

- Chỉ retry **GET session** có semantics read, dù hiện tại server có sliding renewal idempotent. Không áp retry chung cho login, guest creation, writes, AI calls, uploads hoặc streams.
- Retry network/timeout, HTTP 502/503/504 và 500 khi server cho phép retry. 429 tuân Retry-After; delay vượt remaining budget thì dừng và cho manual retry.
- Không retry 401, account/authorization 403, validation/contract INVALID_SESSION hay caller cancellation.
- Dùng exponential backoff với full jitter; ví dụ attempt delay tối đa 500 ms rồi 1000 ms, có cap, một retry cycle tổng 20 s. Mỗi request dùng min(8 s, remaining cycle budget) và timer cleanup trong finally. Tham số phải được đo lại để không che session latency regression.
- Khi online trở lại, trigger qua cùng coordinator, không tự động replay ambiguous writes; Retry-After và cooldown vẫn áp dụng.
- `ApiError` giữ thêm retryable/requestId từ payload hoặc X-Request-ID; phân biệt REQUEST_TIMEOUT với AbortError do caller. Giữ constructor cũ tương thích.

Thông báo nên tách bootstrap unavailable và revalidation degraded, ví dụ “Kết nối đang gián đoạn. MoodPrint đang kiểm tra lại phiên.” Không hứa đã lưu draft nếu chưa xác minh persistence.

## 5. Backend và database

### Phân loại lỗi

Giữ 401 cho auth loss thực, 403 cho deny thực. Classify connect refusal/transport unavailable thành **503**, `retryable=true`, stable code ví dụ `DATABASE_BUSY`/`DATABASE_UNAVAILABLE` và bounded Retry-After. Pool queue timeout cũng là overload/503 nếu đúng loại; đừng catch tất cả SQLAlchemyError thành retryable. ProgrammingError, integrity/contract bug hoặc unknown exception vẫn cần 500 và alert.

Classifier phải ưu tiên driver SQLSTATE (ví dụ 53300 khi có), rồi dùng allowlist message matching **trong memory** cho trường hợp psycopg connect failure có `sqlstate=None` như đã quan sát. Không đưa exception text vào logs/response. Có unit test dùng secret canaries để bảo đảm không leak.

Không retry transaction đã có writes/commit không rõ kết quả. Session-only read có thể retry toàn bộ transaction tối đa một lần ở backend chỉ nếu sau này đo thấy cần và đã bảo đảm sliding renewal/idempotence; **khuyến nghị đầu tiên là không thêm backend retry tự động**, để tránh nhân retry tầng browser/proxy.

### Query/transaction optimization theo evidence

1. Giữ GET session dùng chung AsyncSession, provider helper và revocation checks như hiện tại.
2. Instrument số top-level SQL và checkout duration theo registered/guest/renewal để kiểm tra count tĩnh 6–7/9.
3. Benchmark hợp nhất scalar projections (age/staff/warning/quota) hoặc đưa enrichment không quyết định quyền ra sau bootstrap. Không dùng `asyncio.gather` trên cùng AsyncSession; không mở nhiều DB sessions song song để “tăng tốc” khi role đang đầy.
4. Xem query plan của daily AiRun count; chỉ đề xuất `(user_id, created_at)` nếu measured plan/cost cần. Consent/eligibility/suspension/provider checks không được downgrade thành stale cache.
5. Chỉ giảm clock round trips guest khi chứng minh vẫn có fresh database clock tại authorization/final dispatch và output deadline không được kéo dài. Không tái sử dụng clock cũ qua awaited queue.
6. Phân tích renewal update race và user lock contention trên lab. Không loại last_seen/renewal chỉ để vượt benchmark.

Đặt deadline cho session read theo số đo và budget; SQL/lock bounds nên nhỏ hơn tổng request deadline, frontend có thêm khoảng cho transport. Audit chưa biết runtime role statement_timeout nên không chốt các giá trị global. Dùng SET LOCAL đúng transaction, giữ rollback/close khi cancel. Không đổi global timeout cho AI/SSE/upload.

## 6. Infrastructure và observability

### Tối thiểu đủ dùng cho một EC2

- Một structured request event cho session: UTC timestamp, request_id, route template cố định, method, status, duration_ms, release_sha, error_category, exception class, driver SQLSTATE khi có. Không raw path/query string/headers/body/SQL params.
- Pool metrics tổng hợp: checked_out, overflow, acquire/connect failure count, checkout wait histogram; gắn process/release, không user ID hay DB URL. Snapshot checked_out không thay thế latency measurement.
- Bổ sung application_name không nhạy cảm cho mỗi môi trường để inventory consumers trong lần triển khai sau; không lưu hostname/người dùng cá nhân làm label.
- Ghi role/pooler/global budget trong runbook; sample role utilization read-only tần suất thấp, không dùng fresh connection dồn dập để “monitor” lúc đã đầy.
- Giữ request ID trên response header/error payload và UI support affordance chỉ có correlation ID.
- Nếu muốn bật CloudWatch agent/filters đã có, thực hiện như task ops riêng có approval và cost review. Chưa có dữ liệu active hiện tại; file JSON không phải monitoring đang chạy.
- Alert đề xuất: session 5xx/error category, p95 latency, pool wait/connect refusal, readiness và host resource. Chốt threshold/window với operator, không gắn alert phải dùng dịch vụ trả phí mới.

### Deployment availability

Option B trước tiên đo/ghi startup và release gap, thêm staging test refresh/revalidation trong replacement. Browser retry giúp vượt hai 502 ngắn đã quan sát nhưng không xóa outage server.

Không thêm proxy retry cho mọi method. Nếu cần GET-only retry ngắn, phải benchmark và tránh retry multiplication cùng frontend; một upstream không thể phục vụ trong suốt downtime chỉ nhờ cấu hình retry.

Option C có thể dùng hai slots API trên cùng host và switch Caddy sau readiness, có draining. Nhưng hai pools đồng thời có thể vượt role cap 10, đồng thời tốn RAM/CPU. Chưa triển khai blue/green cho đến khi dành đủ budget và xử lý in-process state. Session endpoint nhẹ hơn, transaction pooling hoặc multiworker chỉ được làm theo milestone riêng khi số liệu chứng minh cần.

## 7. Rủi ro và rollback

| Thay đổi | Rủi ro cần canh | Rollback an toàn |
|---|---|---|
| Budget/consumer isolation | Pool wait tăng, environment trỏ sai, server connections chưa được pooler trả | Restore config đã review nhưng vẫn dưới cap; kiểm tra target và fresh read-only connect; không terminate DB sessions tùy tiện |
| Degraded UI/retry | 401/403 bị che, guest time kéo dài, stale response hồi sinh user | Revert focused frontend commit/image; security regression chặn release nếu có lỗi |
| Error 503 mapping | Bug lập trình bị che thành transient, retry nhân load | Keep unknown 500; revert classifier độc lập; logs vẫn giữ safe category |
| Observability | Leak nội dung hoặc high-cardinality metrics | Disable/revert emitter; retain minimal safe request IDs; không bật raw access/SQL logging |
| Query change | Thiếu consent/projection, revocation chậm | Revert app-only projection; giữ DTO/backward compatibility; không schema downgrade |

Không coi rollback image pair là đủ cho incident: rollback về preset 5+5 trong khi local vẫn dùng role có thể tái tạo failure. Ops rollback phải kiểm tra budget tổng, không chỉ health endpoint.

## 8. Tiêu chí xác nhận hiệu quả

1. Mọi consumer và budget đã được ghi; role/pooler có headroom, fresh connect từ EC2 thành công ở thời điểm idle và controlled load.
2. Logs correlate được `/session` failure với category/status/request ID/SHA; không còn chỉ “OperationalError” vô ngữ cảnh.
3. Focus/visibility/network failure không unmount private tree trong grace; recovery bounded; terminal 401/403/guest T clear ngay, late response không khôi phục.
4. Test saturation trước/sau cho thấy giảm refusal nhờ budget, không chỉ đổi 500 thành 503.
5. Staging mix 50 users đạt targets ở [03](03-reproduction-and-test-plan.md), không retries vô hạn hay unauthorized writes.
6. Sau production rollout được phê duyệt riêng, quan sát thời gian đủ dài có cả idle, focus bursts và worker cycles; không dùng một readiness 200 để tuyên bố incident đã hết.
