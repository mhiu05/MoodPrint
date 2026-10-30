# MoodPrint: phân tích lỗi khởi động và kiểm tra lại phiên

Ngày audit: **30/10/2026, Asia/Bangkok (UTC+7)**. Các timestamp có hậu tố `Z` bên dưới giữ nguyên UTC từ logs. Phạm vi: điều tra, chẩn đoán chỉ đọc và lập kế hoạch; chưa triển khai sửa lỗi.

## 1. Kết luận điều hành

**CONFIRMED — giới hạn connection của database role đang bị chạm.** Một kết nối mới, có giới hạn thời gian, chạy từ chính API container trên EC2 thất bại tại bước `connect` với `OperationalError`; driver chứa thông báo **`too many connections for role`** và tên role được xác nhận bằng boolean là `moodprint_backend`. Không in exception thô hay credentials. Kiểm tra metadata chỉ đọc trên cùng database xác nhận `rolconnlimit=10` và **10 backend connections** của role này. Snapshot cuối có **17 client backends**, trong khi `max_connections=60`: bằng chứng hiện có chỉ ra hạn mức theo role, không phải hết toàn bộ 60 slots. Tổng 25 dòng `pg_stat_activity` còn bao gồm background processes, không được gọi toàn bộ là client connections.

**CONFIRMED — frontend khuếch đại lỗi tạm thời thành gián đoạn toàn màn hình.** `SessionRoot` dùng chung trạng thái lỗi cho bootstrap và background revalidation. Chỉ một lần `/session` lỗi khi quay lại tab cũng làm unmount cây ứng dụng đã dùng được. Thử nghiệm trình duyệt local tái hiện được cơ chế này với response 500 tổng hợp.

**PROBABLE — hai môi trường dùng chung ngân sách connection là tác nhân chính.** API production đang cấu hình pool `5 + 5 overflow`, giữ 5 TCP connections tới session pooler. Một process backend local `python -m app` cũng giữ 5 TCP connections tới đúng địa chỉ pooler trong cấu hình local; endpoint fingerprint của cấu hình local và EC2 khớp nhau. Tổng role connections quan sát được là 10. Tuy nhiên, TCP socket không chứng minh DB role của từng kết nối local, và Supavisor có thể che nguồn client trong `pg_stat_activity`. Attribution local → 5 role connections còn lại có độ tin cậy cao nhưng chưa hoàn toàn khép kín.

**Chưa xác nhận cho từng lần người dùng thấy màn hình:** không có timestamp/request ID của lần báo lỗi, và backend không log endpoint cho `request_failed`. Vì vậy không được gọi toàn bộ 48 request lỗi trong logs là 48 lần `/session` lỗi. Kết luận đáng bảo vệ nhất là: **role connection saturation đã được chứng minh trên runtime; nó rất có khả năng gây các lỗi DB gián đoạn đang quan sát; đường frontend biến lỗi revalidation thành màn hình lỗi đã được chứng minh riêng.**

## 2. Phiên bản thực sự được điều tra

| Nguồn | Kết quả |
|---|---|
| GitHub `main`, `git ls-remote` | `57b3f7fbf91967f329a80fd344421f24ff6c5e52` |
| OCI revision của container `api` và `web` | Cùng SHA `57b3f7f…`, lấy trực tiếp bằng Docker inspect qua SSM |
| `/opt/moodprint/staging.env`, chỉ đọc allowlist | `RELEASE_SHA=57b3f7f…`; image digests khớp container và release manifest |
| API image digest | `sha256:52d74edef5a3ecbcc43f03694973bf0cbffaf7784b9bb3bcd9ad5406c09e83d7` |
| Web image digest | `sha256:f6b1916820d9dd1c6e78a6aa2a5cd0eeca27a6b9bf69546646c76c6bb6d17949` |
| Publish workflow | Run `40904033069`, success; đây là bằng chứng publication, được kiểm tra thêm bằng runtime ở trên |
| Local HEAD | `e1fa5b08ae6c5f39b864d44adc10576f12008be6`, branch `test/local-feature-review-2026-10-29` |
| Local branch `main` | Cũ: `9ca7fc8…`; không dùng tên branch này làm chứng cứ production |

Primary target là **SHA đang chạy `57b3f7f…`**. `git diff` xác nhận backend, deploy, workflows, API client, session validator, ErrorNotice và main.tsx đang đọc khớp SHA này. Các thay đổi chưa commit ở AppEntry/public UI và phần trợ lý/journal trong workspace là công việc có sẵn/đang diễn ra của người dùng; audit không chỉnh sửa chúng. Phần `SessionRoot` được viện dẫn bên dưới khớp bản deployed.

[Release manifest đã xuất bản](https://github.com/mhiu05/MoodPrint/releases/tag/staging-57b3f7fbf91967f329a80fd344421f24ff6c5e52), [publish run](https://github.com/mhiu05/MoodPrint/actions/runs/40904033069).

## 3. Đường thực thi chính xác của màn hình lỗi

Tham chiếu dòng là của SHA `57b3f7f…`, trừ nơi ghi rõ workspace.

1. `frontend/src/main.tsx:9–16`: parse callback một lần, mount AppEntry trong StrictMode.
2. `frontend/src/AppEntry.tsx:28–42`: phân loại đường dẫn; protected app được lazy-load trong Suspense. Public landing có thể hoạt động dù protected session thất bại.
3. `frontend/src/features/real/RealApp.tsx:174–220`: `SessionRoot` gọi `api.request('/session')`. Response được `validateSession` kiểm tra rồi `receive` cài CSRF và session.
4. Cùng file `221–239`: `focus` và `visibilitychange`, khi visible và đã có session, debounce 100 ms rồi tăng `revision`; effect ở bước 3 chạy lại.
5. Cùng file `211–218`: chỉ HTTP 401 đi nhánh session loss; mọi exception khác đi `setError(reason)`.
6. Cùng file `258–271`: `if (error)` được xét **trước** session và cây private; render **“Chưa thể mở MoodPrint”** cùng ErrorNotice. Không cần lỗi xảy ra trong lần tải đầu tiên.
7. `frontend/src/components/ErrorNotice.tsx:12–19`: render `errorMessage(error)` và nút **“Thử lại”**.
8. `frontend/src/api/client.ts:106–131`: non-2xx → ApiError, ưu tiên `error.message`/`detail.message` của server. Vì vậy chuỗi **“Chưa hoàn tất yêu cầu. Vui lòng thử lại.”** khớp message do backend dựng tại `backend/app/main.py:270–279` và `backend/app/core/errors.py:65–70`.
9. Server exception trong request đi qua `request_boundary`, log **chỉ** request ID và exception class ở `main.py:264–269`, rồi chuyển thành generic HTTP 500. `OperationalError` không được phân loại thành database unavailable/503 riêng.

Chuỗi “Vui lòng” là gợi ý backend JSON generic 500; fallback của client dùng “Bạn hãy thử lại”. **Message tự nó không chứng minh HTTP status**; cần Network response/request ID cho lần lỗi thực tế.

Source chính: [SessionRoot](https://github.com/mhiu05/MoodPrint/blob/57b3f7fbf91967f329a80fd344421f24ff6c5e52/frontend/src/features/real/RealApp.tsx#L174), [client](https://github.com/mhiu05/MoodPrint/blob/57b3f7fbf91967f329a80fd344421f24ff6c5e52/frontend/src/api/client.ts#L95), [request boundary](https://github.com/mhiu05/MoodPrint/blob/57b3f7fbf91967f329a80fd344421f24ff6c5e52/backend/app/main.py#L245).

## 4. Bằng chứng runtime đã thực sự thu thập

AWS profile `moodprint` ban đầu hết hạn. Sau xác nhận của người dùng, đã chạy `aws login --profile moodprint` rồi dùng SSM Run Command cho các chương trình chỉ đọc. Không restart/stop container, thay env, sửa AWS/Supabase, terminate DB session hay migrate. AWS tạo execution record của lệnh chẩn đoán; workload/configuration không được thay đổi.

### 4.1. Public probes

| UTC 29/10/2026 | Probe không credentials | Kết quả |
|---|---|---|
| 18:35:14 | `/` | 200, khoảng 1250 ms; JS `/assets/index-Bi2jZ1fl.js` |
| 18:35:15 | `/api/v1/health/live` | 200, khoảng 844 ms; request ID `c9ffaca7-6d72-4f56-976c-f0dd076f8385` |
| 18:35:16 | `/api/v1/health/ready` | 200, khoảng 1593 ms; request ID `6c43f238-4d01-4e69-a09a-c2c80d6a1043` |
| Lần probe riêng sau đó | `/api/v1/session`, không cookie | 401 `AUTH_REQUIRED`; request ID `97f5a914-e071-4bb8-b345-eaeee81e4c93` |

Độ trễ trên là end-to-end từ máy audit, có DNS/TLS/network; không phải DB query time hay production p95. Không probe session bằng cookie của người dùng. `/release.json` trả HTML SPA fallback 200, không phải release metadata.

### 4.2. Container, logs và deploy

Snapshot host khoảng **18:41:30Z = 01:41:30 ngày 30/10, UTC+7**:

- EC2 `t3.small`, region `ap-southeast-2`; hai container running/healthy, restart count **0**, `OOMKilled=false`.
- API memory khoảng **148.7 MiB / 768 MiB**, CPU snapshot **1.54%**; web khoảng **12.55 MiB / 256 MiB**. Disk host dùng **15.5%**.
- Journal kernel trong khoảng được đọc từ `2026-10-28 18:00 UTC`: **0** dòng khớp mẫu OOM đã tìm. Không suy rộng ra toàn lịch sử instance.
- Hai container hiện tại bắt đầu **15:48:07–08Z**. Deployment journal xác nhận healthy SHA `57b3f7f…` lúc **15:48:35.953Z**.
- Caddy có **2 lỗi 502 `connection_refused`** lúc **15:48:14.792Z** và **15:48:16.603Z**, trong cửa sổ startup, trước healthy. URI đã bị lọc nên không gán chúng cho `/session`.
- API stdout và stderr đã được đọc trong process chẩn đoán, tail limit 20.000 dòng, số dòng dưới limit. Có **48 `request_failed`, tất cả `OperationalError`**, từ **16:48:16.533Z đến 18:23:23.776Z**; **51 `metric=http_5xx`** và **3 `metric=readiness_failed`** trong snapshot đầu.
- Worker retries: **18 embedding**, **12 deletion**, **6 guest**, đều `OperationalError`, `sqlstate=None`. Lỗi ở nhiều loại công việc củng cố giả thuyết phụ thuộc DB dùng chung.
- Ví dụ request lỗi lúc `18:23:14.866Z`, ID `3dc6f061-805f-4123-825b-4ffa5f89ba34`; log không có endpoint/status/duration để liên kết tới màn hình của người dùng.
- Log đọc thuộc container hiện tại, từ startup đến khoảng 18:43Z. Rotation và việc thay container giới hạn lịch sử; đây không phải tổng sự cố 24 giờ.

Các phút có request lỗi: `16:48(5), 17:16(2), 17:29(3), 17:34(4), 17:35(2), 17:41(1), 18:07(4), 18:09(1), 18:13(7), 18:14(5), 18:17(1), 18:18(7), 18:19(1), 18:23(5)` — UTC 29/10. Phần lớn lỗi cách xa deploy, nên downtime deploy không giải thích toàn bộ.

### 4.3. Connection limit được kiểm chứng

Khoảng **18:45–18:48Z**, các truy vấn catalog chạy trong **read-only transaction**, statement timeout 3–5 giây, qua credential đã có trong local configuration. Không chạy migration dù dùng trường cấu hình `DATABASE_MIGRATION_URL` để đọc catalog khi runtime role không thể mở connection mới.

| Quan sát | Giá trị |
|---|---|
| Endpoint fingerprint EC2/local | Khớp SHA-256 của host/port/database; không đưa URL hoặc password vào báo cáo |
| EC2 role và endpoint | Role khớp `moodprint_backend`; Supabase session pooler port 5432 |
| Production SQLAlchemy settings | `pool_size=5`, `max_overflow=5`, `pool_timeout=10` |
| Runtime role metadata | `rolconnlimit=10`, không superuser, không BYPASSRLS |
| `pg_stat_activity` cho runtime role | 10 connections; snapshot 8 idle + 2 idle in transaction |
| Transaction age ở snapshot sau | Max làm tròn **0 giây**; không chứng minh leak/transaction kéo dài |
| Toàn DB | 25 `pg_stat_activity` rows; snapshot phân loại sau có 17 client backends; `max_connections=60` |
| Schema revision | `0019_journal` |
| EC2 container TCP tới DB:5432 | 5 established sockets |
| Backend local TCP tới cùng pooler | 5 established sockets; process app, không phải synthetic test |
| Fresh connection từ EC2 | Bị từ chối sau khoảng 2101 ms; `too_many_connections_for_role=true`, `mentions_expected_role=true` |

Metadata probe xác nhận hạn mức và connection refusal hiện tại; **không phải quan sát trực tiếp pool occupancy của process Uvicorn**. Không có pool instrumentation đang chạy để đo checkout wait/overflow theo thời gian. Không thu query text, email, user IDs, cookies hay tokens.

Snapshot bổ sung lúc **19:03:30Z = 02:03:30 ngày 30/10, UTC+7** tách `backend_type`: 25 activity rows, 17 client backends, runtime role vẫn 10 connections, 0 runtime transactions có tuổi trên 5 giây. Đây là snapshot khác thời điểm với phép đo 18:45Z, không phải time series chứng minh không bao giờ có transaction dài.

Provenance chẩn đoán SSM (output đã sanitize trước khi trả về): `cc6fa73e-24b9-4073-be0e-161ad43091ce` cho container/log/deploy snapshot; `1b2ebfa6-d4c5-425d-8d5d-a77c7a3f6cd5` cho combined stdout/stderr và metadata probe thất bại; `06b4597d-e66a-430d-abab-be4fee51221a` cho connect-stage classification; `e7ffb5b6-87a4-4373-bde3-640041e1edd8` cho exact role refusal/target/socket confirmation. Catalog queries thành công được chạy riêng từ máy operator trong read-only transactions.

### 4.4. CloudWatch

Trong **region ap-southeast-2**, query log-group prefix `/moodprint` trả danh sách rỗng; `describe-alarms` không thấy metric alarms. Service CloudWatch agent không active (exit code 4). Các JSON cấu hình trong repo không chứng minh đã áp dụng.

EC2 metrics 24 giờ `2026-10-28T18:41:43Z–2026-10-29T18:41:43Z`, 288 điểm/metric, period 300 s:

- CPU: mean của các Average 5 phút **2.83%**, Average cao nhất **6.21%**, Maximum cao nhất **17.87%**.
- CPUCreditBalance Minimum **576** ở mọi điểm.
- StatusCheckFailed Maximum **0**.

Dữ liệu này làm giả thuyết EC2 CPU/credit/OOM yếu đi; không loại trừ mọi spike nhỏ hơn độ phân giải hoặc vấn đề ở region khác.

## 5. Vì sao có lúc vào được, lúc lại lỗi?

Pool có thể dùng lại các connection đã mở, trong khi một request khác cần connection thứ sáu/overflow hoặc thay connection invalidated thì bị role cap từ chối. Readiness có thể mượn một connection còn dùng được và chạy ba truy vấn nhẹ; `/session` có nhiều round trips hơn và cạnh tranh với background jobs. Do đó readiness 200 và fresh-connect failure có thể cùng đúng.

Budget cấu hình **chỉ riêng production đã cho phép 10 connections**, bằng toàn role cap và không còn headroom cho môi trường khác hay chẩn đoán bằng runtime role. Nếu các local connections dùng cùng role như cấu hình hiện có, production thực tế chỉ còn khoảng 5 slots; burst, revalidation hoặc worker checkout sẽ bộc lộ lỗi. Chưa đo được chính xác request nào kích hoạt lần mở connection mới trong process chính.

Frontend đọc lại session khi quay lại tab; guest có thêm một effect đọc cùng endpoint. Một lỗi tức thời vì vậy xuất hiện như lỗi “không mở được app” ngay cả sau nhiều phút sử dụng bình thường. Caddy còn có một cơ chế độc lập gây 502 trong lúc replace container.

## 6. Giả thuyết xếp hạng và điều kiện bác bỏ

| Hạng | Giả thuyết | Bằng chứng hỗ trợ | Giới hạn/điều kiện bác bỏ | Tin cậy |
|---|---|---|---|---|
| 1 | Role cap gây refusal khi mở DB connection mới | Fresh probe từ EC2 + exact driver phrase; role limit 10/10; OperationalError ở request và workers | Không gán được từng request lịch sử; cần exception category trên process chính | **CONFIRMED cho refusal hiện tại; PROBABLE cho chuỗi incident** |
| 2 | Backend local tranh chấp role budget với EC2 | 5 EC2 sockets + 5 local sockets; cùng endpoint; role 10/10 | Chưa gán DB role cho từng local socket; cần pooler client mapping/application_name | **PROBABLE, cao** |
| 3 | Frontend biến revalidation failure thành full-screen error | Code `catch → setError → if(error)`; browser local tái hiện | Không chứng minh nguyên nhân HTTP phía server | **CONFIRMED** |
| 4 | Cửa sổ deploy gây một phần 502 | Hai proxy refusal trong startup trước healthy | Request errors sau đó 1–2.5 giờ; không thể là lời giải thích duy nhất | **CONFIRMED, phạm vi hẹp** |
| 5 | SQLAlchemy pool queue đầy trong process | Nhiều DB consumers, 10 s wait, nhiều SQL/session | Logs là OperationalError, không phải QueuePool TimeoutError; chưa có checkout metrics | **POSSIBLE, chưa chứng minh** |
| 6 | Transaction leak, query/lock chậm | Một snapshot có idle-in-transaction | Age 0 s; context managers trả connection; không có long-lock/query evidence | **Chưa có bằng chứng** |
| 7 | Supabase outage diện rộng, DNS/TLS, EC2 quá tải | Đều có thể gây gián đoạn theo lý thuyết | Refusal cụ thể theo role; CPU/credits tốt; thiếu provider incident evidence | **Thấp với dữ liệu hiện có** |
| 8 | Cookie/CSRF projection sai, session revoked | Có các nhánh 401 và local INVALID_SESSION | Message/status của chúng khác; không giải thích role refusal | **Rủi ro phụ, chưa phải nguyên nhân chính** |

## 7. Bằng chứng còn thiếu và bước xác minh

1. Timestamp UTC+7 và `X-Request-ID` của lần màn hình lỗi, status/code/content-type của `/session`; không cần cookie hoặc HAR thô.
2. Log safe category + driver SQLSTATE trên **process chính**, route template `/api/v1/session`, duration và release SHA để liên kết các đầu mối.
3. `pool checked_out`, overflow, checkout wait và connect failures theo process; số client/server connection của Supavisor theo runtime role.
4. Gán tên ứng dụng cho các connection ở task tương lai và inventory mọi consumer của role. Không terminate session trong audit.
5. Query plan/p95 theo câu SQL với dữ liệu tổng hợp/staging; timeout mặc định **của runtime role** chưa thu được. Giá trị `5s` trong metadata probe là timeout do probe tự đặt, không phải cấu hình application.
6. Thời điểm workload/traffic khi lỗi; hiện không đủ dữ liệu để gọi đây là “burst 50 users” hay suy ra error-rate phần trăm.

Chẩn đoán bổ sung và test matrix ở [03-reproduction-and-test-plan.md](03-reproduction-and-test-plan.md). Các hướng sửa được so sánh ở [04-optimization-proposal.md](04-optimization-proposal.md), không được thực thi trong audit này.
