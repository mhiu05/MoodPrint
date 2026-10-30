# Tái hiện, kiểm thử và thu thập bằng chứng

Ngày 30/10/2026, UTC+7. Audit không thêm test vào application source, không chạy load test production, không sửa schema. Kết quả đã chạy và kế hoạch chưa chạy được phân biệt bên dưới.

## 1. Kết quả kiểm thử đã thực hiện

| Kiểm tra | Lệnh/phương thức | Kết quả thực tế | Giới hạn |
|---|---|---|---|
| Frontend unit | Từ `frontend`: `npm.cmd test -- --reporter=dot` | **21 files, 103 tests passed**, exit 0 | Workspace hiện có thay đổi UI của người dùng; không chứng minh network/DB production |
| Backend selected suite | Lệnh dưới bảng | **25 passed, 38 skipped**, exit 0 | TEST_DATABASE_URL rỗng có chủ đích; auth/DB integration chưa được chạy |
| Existing Playwright session unavailable/retry test | `real.spec.ts`, grep theo tên dưới đây | **1 passed**, exit 0, khoảng 2.8 s | Local Vite, mock HTTP; không gọi backend/Supabase |
| Ad hoc browser reproduction | agent-browser, init script tạm ngoài repo, mock `window.fetch` trên local port 5189 | Tái hiện authenticated → focus/500 → full-screen error; API phục hồi nhưng chưa có trigger thì vẫn lỗi; focus/200 phục hồi; focus/401 bỏ private navigation và về auth | Đây là kiểm tra hành vi local, không phải automated regression test được commit |
| Fresh DB connect từ EC2 | Bounded read-only diagnostic qua SSM | **Thất bại**: OperationalError, `too many connections for role` | Bằng chứng failure hiện tại, không gọi là test pass |
| DB metadata | Read-only transaction qua cấu hình owner đã có | Role 10/10; 25 activity rows, snapshot phân loại có 17 client backends/max_connections 60; revision 0019 | Không benchmark query, không đọc dữ liệu người dùng |

Backend command đã chạy từ `backend` bằng interpreter hiện có, không sync/update dependencies:

```powershell
$env:TEST_DATABASE_URL=''
.\.venv\Scripts\python.exe -m pytest -q tests/test_auth_flows.py tests/test_guest_auth.py tests/test_readiness.py tests/test_database_operations.py tests/test_production_settings.py tests/test_ops_config.py tests/test_public_headers.py -ra
```

Các skip là thiếu PostgreSQL disposable, không phải tests thành công. Không chạy fixture `database()` trên database đang dùng: nó drop/create tables. Không gọi provider, không ghi Supabase trong unit/browser tests kể trên.

Playwright test đã chạy có tên:

```text
an unavailable session remains an explicit error until retry succeeds
```

Audit dùng config tạm trong OS temp directory, trỏ `testDir` tới `frontend/tests/e2e`, chỉ chọn `real.spec.ts`, `baseURL=http://127.0.0.1:5189`, một worker, outputDir trong temp, không webServer tự tạo. Local Vite được mở bởi audit và đã dừng; browser session riêng của audit đã đóng. Không dừng backend local đang giữ DB connections.

## 2. Tái hiện tối thiểu lỗi frontend

Không cần DB hoặc tài khoản thật. Trong local browser harness:

1. Mock mọi `/api/v1/*` để không có request vượt sang proxy thật. `/session` trả SessionView registered hợp lệ; `/bots` trả array; preferences/history trả đúng DTO tổng hợp.
2. Mở `/#/`, đợi private navigation và heading trợ lý.
3. Đổi mock `/session` thành 500 với `{error:{code:'INTERNAL_ERROR',message:'Chưa hoàn tất yêu cầu. Vui lòng thử lại.',retryable:true}}`.
4. Dispatch `window.dispatchEvent(new Event('focus'))` khi document visible.
5. Hiện tại: sau debounce 100 ms, heading **“Chưa thể mở MoodPrint”**, private tree unmount.
6. Đổi mock về 200 nhưng chưa dispatch event/click: hiện tại error vẫn giữ. Không có automatic retry timer.
7. Dispatch focus: session thành công, private tree remount.
8. Đổi mock thành 401 SESSION_EXPIRED, dispatch focus: private tree biến mất, auth screen xuất hiện. Đây là behavior bảo mật phải giữ.

Bootstrap development có hai mock session calls do StrictMode. Từ trạng thái ổn định, focus registered tạo thêm một call trong thử nghiệm. Không dùng số calls development để suy ra production. Khi viết regression tests, kiểm tra cả production build và StrictMode/cancellation.

Nếu dùng Playwright route interception, chỉ intercept dev/staging do mình sở hữu; không chèn lỗi vào production. Screenshot/HAR phải là dữ liệu tổng hợp; không lưu HAR có cookie/token của người dùng.

## 3. Ma trận acceptance cho giải pháp tương lai

Các kỳ vọng là **thiết kế đề xuất**, chưa có trong code. Giá trị retry/deadline phải được xác nhận bằng staging measurements theo [04](04-optimization-proposal.md).

| ID | Scenario | Bootstrap mong muốn | Revalidation mong muốn / assertion quan trọng |
|---|---|---|---|
| S01 | 401 AUTH_REQUIRED/SESSION_EXPIRED | Auth screen, không render private | Clear session/private caches/CSRF; reset epoch; abort pending reads; không retry 401 |
| S02 | 401 GUEST_EXPIRED | Content-free expired screen | Cùng tab và tab khác clear ngay; không dựng lại guest từ response cũ |
| S03 | 403 ACCOUNT_SUSPENDED | Blocked screen | Clear private content; không giữ snapshot như lỗi transient; không auto retry |
| S04 | 403 khác ở `/session` | Fail closed, thông báo phù hợp | Không coi mọi 403 là network outage; writes CSRF_DENIED có flow riêng |
| S05 | 429 + Retry-After | Retry có giới hạn và tôn trọng delay | Một retry cycle, không storm; parse seconds và HTTP-date; nếu delay quá budget thì dừng và cho manual retry |
| S06 | JSON 500 retryable | Loading/retry bounded, sau cùng unavailable | Giữ snapshot đã cho phép trong grace có giới hạn; không unmount vì một lỗi; disable writes và stop new private reads/streams |
| S07 | Non-JSON 502/503/504 | Không throw JSON parse ngoài kiểm soát; recovery bounded | Không giả định mất auth; không retry writes; preserve request ID nếu có |
| S08 | DB không nhận connection mới | 503 retryable theo hợp đồng mới, không 401 | Exception category connection_limit; log route/ID/SHA; khôi phục khi slot sẵn sàng |
| S09 | Network offline/Failed to fetch | Thông báo connectivity | Online trigger dùng chung coordinator, không nhiều retries; bounded grace rồi clear private |
| S10 | Fetch quá timeout | REQUEST_TIMEOUT riêng | Tách timeout khỏi caller abort; tổng session-read deadline không kéo dài vô hạn |
| S11 | Effect cleanup, route unmount, reset | Cancellation im lặng | Không toast/full-screen vì abort; cũ không sửa state của epoch mới |
| S12 | Focus + visibility + online liên tiếp | Không áp dụng khi chưa auth ngoài bootstrap | Một in-flight session read/epoch, coalesce event burst; guest không gọi lần thứ hai |
| S13 | Success cũ tới sau 401/logout | Không restore identity cũ | Request generation + epoch chặn success và failure cũ |
| S14 | Session mới nhận từ login khi bootstrap cũ pending | Identity mới thắng | Không cho late result ghi đè user, csrf, consent hoặc status mới |
| S15 | HTTP 200 JSON sai/thiếu csrf/guest claims sai | INVALID_SESSION, không mở private | Code override status-based retry; không dùng malformed projection như session mới |
| S16 | Backend restart khi đang dùng | Retry bounded nếu đang bootstrap | Pending read phục hồi an toàn; authenticated state không bị ghi nhầm thành logout vì 502 |
| S17 | Network chậm, nhiều revalidation | Loading có hạn và có phản hồi | Không một timer mỗi event; tổng budget và số attempts hữu hạn |
| S18 | Liên tiếp thất bại | Sau tối đa 3 attempts/cycle, explicit retry | Grace hết hạn clear private; online/focus không reset grace hoặc tạo loop vô hạn |
| S19 | Refresh browser trong deployment | Cold bootstrap không dùng private cache | Có thể gặp 502 nhưng retry được; không dùng localStorage snapshot để “đăng nhập” |
| S20 | Guest T xảy ra trong retry/backoff | Không extend trial | Original monotonic deadline còn sống qua error UI; kết thúc đúng T dù app hidden/offline |
| S21 | GuestHost từng unmount rồi retry | Không render guest từ anchor cũ | Test deadline không được tái neo bằng serverTime cũ; T vẫn authoritative |
| S22 | Consent/eligibility revoked khi session read lỗi | Không làm lỏng server checks | Mọi write/private fetch mới vẫn bị server deny; confirmed revocation clear đúng scope |
| S23 | 401 REAUTH_REQUIRED từ action step-up | Không liên quan bootstrap | Không global logout do step-up; không replay write tự động |
| S24 | Retry-After rất lớn/malformed/clock skew | Thoát bounded | Không negative timer, không vượt deadline, manual retry có state rõ ràng |
| S25 | Lazy chunk thiếu sau deploy | Recoverable app boundary | Controlled reload/retry; không vòng reload; không gộp thành “DB lỗi” |

## 4. Coverage hiện có và khoảng trống

| Tầng | Coverage đọc trong repo | Thiếu quan trọng |
|---|---|---|
| Vitest client | `frontend/src/api/client.test.ts:13–77`: idempotency key 5xx/4xx, non-JSON error fallback, network message | Timeout vs abort, retryable/requestId, Retry-After parsing, read retries bounded |
| Vitest session | `frontend/src/api/session.test.ts`: validator guest/registered | Coordinator state machine, single-flight/epoch và bounded grace |
| Playwright real | `frontend/tests/e2e/real.spec.ts:322–352`: bootstrap 503/manual retry; focus/consent tests khác | Already-authenticated focus 5xx không phá draft; timeout recovery; burst dedupe |
| Guest E2E | `frontend/tests/e2e/guest-expiry.spec.ts`: pending focus/deadline, cross-tab expiry, late response | Transient error làm GuestHost unmount rồi remount với anchor cũ; root+guest duplicate reads |
| Backend auth | `backend/tests/test_auth_flows.py`: sliding, revoked, reset, CSRF/origin, last_seen cadence | Pool acquisition/DB connection limit failure không bị biến thành 401; query-count budget |
| Guest backend | `test_guest_auth.py`, guest deadline/output/inflight suites | Giữ security invariant trong retry/cancellation mới |
| Readiness | `test_readiness.py`: migration revision gating | Readiness có thể 200 trong khi fresh runtime connect từ chối; helper existence khác executable privilege |
| Logging | `test_ops_config.py`, `test_guest_log_privacy.py` | Safe category + route template + duration + SHA; không leak raw exception/SQL/credentials |
| Fullstack/load | `scripts/load_social_mood.py`, `load_chat_memory.py`, `load_guest_experience.py`; `.github/workflows/verify.yml` | Role cap giống production, consumers ngoài process, focus burst/partial connectivity, long soak |

CI có synthetic load một worker/10 users và fullstack với fake model. Nó hữu ích nhưng không xác minh budget role 10 khi local và EC2 cùng kết nối. Không báo lại các file kết quả cũ trong docs như phép đo của audit. Không chạy lại toàn bộ suite chỉ để lấy nhiều test counts khi không có disposable DB.

## 5. Lệnh kiểm thử cho task triển khai tương lai

### Unit và browser

```powershell
# Từ frontend; dùng mock fixtures, không credentials thật.
npm.cmd test
npm.cmd run typecheck
npm.cmd run build
npm.cmd run test:e2e -- --grep 'session|unavailable|expiry|expired|focus'
```

Sau khi có files mới theo implementation plan, chạy trực tiếp chúng thay vì chỉ grep và kiểm tra không có test cần thiết bị bỏ sót. Thử production preview ngoài Vite dev cho chunk/StrictMode behavior.

### Backend integration / fullstack

Chỉ trên PostgreSQL local disposable riêng, hostname loopback và database kết thúc `_test`; `tests/database_target.py` phải chấp nhận target trước khi chạy. Không lấy `DATABASE_URL` hoặc hosted Supabase URL gán sang TEST_DATABASE_URL.

```powershell
# TEST_DATABASE_URL do operator/harness cấp cho database disposable.
cd backend
uv run --locked pytest -q tests/test_auth_flows.py tests/test_guest_auth.py tests/test_readiness.py tests/test_session_reliability.py tests/test_guest_inflight.py tests/test_guest_log_privacy.py
uv run --locked python ../scripts/test_fullstack.py
```

`test_session_reliability.py` là file **đề xuất**, chưa tồn tại trong audit. Scripts fullstack/load seed và reset schema chỉ trong local test target; audit này không chạy chúng.

### Tái hiện connection saturation trong local lab

1. Tạo PostgreSQL test riêng với LOGIN role cap 10 và schema/fixtures tổng hợp, trong task triển khai tương lai.
2. Hai process cùng role/DB: giữ 5 connections/process; xác nhận connection thứ 11 bị từ chối. Không dùng `pg_terminate_backend` trên hosted DB.
3. Giữ 5 connections cho process B; cho process A pool `5+5` và nhiều request/auth workers đồng thời. Ghi rõ borrowed connections, overflow và exceptions.
4. Assert endpoint lỗi 503 retryable/category connection_limit, không 401; mọi session trả pool sau lỗi/cancel.
5. Release connections của B trong lab; xác minh A phục hồi mà không restart service và frontend không infinite retries.
6. Kiểm tra renewal branch + provider revocation ở thời điểm đang retry, để tối ưu không che auth loss.

Đây là test cần setup lab/schema mới nên **chưa được thực hiện** trong audit.

## 6. Load test phù hợp mục tiêu 50 users

Không mở 50 DB connections để mô phỏng 50 người dùng. Chạy tuần tự 1/10/25/50 virtual users, một Uvicorn process, pool nhỏ đã chốt budget; mix bootstrap, focus, resource polling, guest cleanup, simulated AI latency. Model/STT phải fake, mọi actor tổng hợp. Gồm warm pool, cold pool, renewal window, 2-tab guest, backend restart trong lab và role competition có kiểm soát.

Đo session success rate (loại các 401/403 chủ động theo expected scenario), p50/p95/p99, connection acquire latency, connect failures, checked_out/overflow, event-loop lag, worker queue lag, transaction age/locks và resource headroom. Ghi sample size, số requests thực tế và percentile method; không gọi max của vài requests là p95 đáng tin.

Mục tiêu đề xuất cho staging: session p95 <2 s/p99 <5 s ở mix 50 users, không unexpected 5xx trong ít nhất 1.000 session reads, bounded failure recovery, không vượt role budget. Đây là acceptance target cần benchmark, **không phải cam kết hiệu năng hiện tại**. Synthetic soak 30–60 phút ở staging chỉ sau khi xác nhận target/budget; không chạy trên production trong task audit.

## 7. Runbook chẩn đoán chỉ đọc cho operator

### Runtime identity và container state — chạy trong shell EC2 được ủy quyền

```bash
docker ps --filter label=com.docker.compose.project=moodprint-staging --format '{{.Names}} {{.Status}}'
API_ID=$(docker ps -q --filter label=com.docker.compose.project=moodprint-staging --filter label=com.docker.compose.service=api)
WEB_ID=$(docker ps -q --filter label=com.docker.compose.project=moodprint-staging --filter label=com.docker.compose.service=web)
docker inspect --format '{{index .Config.Labels "org.opencontainers.image.revision"}} {{.RestartCount}} {{.State.OOMKilled}} {{.State.Health.Status}}' "$API_ID" "$WEB_ID"
docker stats --no-stream --format '{{.Name}} {{.CPUPerc}} {{.MemUsage}}' "$API_ID" "$WEB_ID"
systemctl is-active amazon-cloudwatch-agent
```

Không dùng `docker inspect` không lọc hoặc `docker compose config` để chia sẻ output: chúng có thể in runtime env/secret. Không `cat` runtime.env/staging.env toàn bộ. Chỉ lấy SHA/image digests bằng allowlist như audit.

### Phân loại lỗi logs mà không xuất nội dung thô

```bash
docker logs --since '2026-10-29T15:48:00Z' --timestamps "$API_ID" 2>&1 | python3 -c '
import sys,re,collections,json
counts=collections.Counter()
for line in sys.stdin:
    m=re.search(r"request_failed.*error_type=(\w+)",line)
    if m: counts[m.group(1)]+=1
print(json.dumps(dict(counts)))
'
```

Đổi time window theo sự cố; ghi cả container start/rotation boundary. Để correlate request IDs, chỉ trích timestamp + UUID + exception class bằng regex allowlist, không in nguyên log line. Code hiện tại không thể hồi phục route/duration/underlying message đã không được log.

### Metadata role cap — chạy từ `backend` trên máy operator có cấu hình đã được review

```python
from dotenv import dotenv_values
from sqlalchemy.engine import make_url
import psycopg

v = dotenv_values('.env')
target = make_url(v['DATABASE_MIGRATION_URL'])
# Chỉ dùng credential đã có để đọc catalog; không gọi migration script.
with psycopg.connect(target.set(drivername='postgresql').render_as_string(hide_password=False),
                     connect_timeout=5, prepare_threshold=None) as db:
    db.execute('SET TRANSACTION READ ONLY')
    db.execute("SET LOCAL statement_timeout='3s'")
    print(db.execute("select rolconnlimit from pg_roles where rolname='moodprint_backend'").fetchone())
    print(db.execute("select state,wait_event_type,count(*) from pg_stat_activity where usename='moodprint_backend' group by 1,2").fetchall())
    print(db.execute("select count(*),count(*) filter(where state='idle in transaction') from pg_stat_activity").fetchone())
    print(db.execute("select current_setting('max_connections')").fetchone())
```

Không in target URL, exception thô, `pg_stat_activity.query`, client IP hoặc user data. Nếu cần fresh-connect probe, dùng runtime URL trong memory, timeout 5 s, chỉ `SET TRANSACTION READ ONLY; SELECT 1`; log type/SQLSTATE và boolean khớp phrase `too many connections for role`, đóng/dispose trong finally. Một probe mỗi lần chẩn đoán; không tạo reconnect storm khi role đã đầy.

### AWS public telemetry — từ shell local

```powershell
aws logs describe-log-groups --profile moodprint --region ap-southeast-2 --log-group-name-prefix /moodprint --no-cli-pager
aws cloudwatch describe-alarms --profile moodprint --region ap-southeast-2 --query 'MetricAlarms[].{Name:AlarmName,State:StateValue}' --no-cli-pager
```

EC2 ID lấy bằng `describe-instances` với tag Name=moodprint-staging; dùng `get-metric-statistics` cho CPUUtilization Average/Maximum, CPUCreditBalance Minimum và StatusCheckFailed Maximum, dimension InstanceId, period 300, time window incident UTC. Không suy ra memory/OOM từ CPU metric; không thấy log groups trong một region không có nghĩa toàn account không có logging.

## 8. Những việc audit không làm

Không sửa source để chèn faults/instrumentation; không tạo DB/role/index; không chạy EXPLAIN ANALYZE trên traffic production; không restart/redeploy để thử hồi phục; không dùng tài khoản thật để tạo session; không terminate connection của backend local. Những phép thử cần các hành động đó đã được đưa vào kế hoạch riêng với local/staging scope.
