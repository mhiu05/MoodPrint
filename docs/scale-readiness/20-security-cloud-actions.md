# Security containment and current cloud actions

Quan sát mới: 2026-11-05 17:54–17:59 Asia/Bangkok. Đây là điều tra read-only;
chưa rotate credential, sửa env/SSM/IAM/DNS, deploy, restart hoặc start/stop EC2.
Không xuất password, DSN, secret fingerprint, session ID hay dữ liệu người dùng.

## P0: migration-owner credential vẫn hoạt động

[Evidence đã lọc](evidence/round2-security.json) xác nhận `backend/runtime.txt` chứa
password PostgreSQL trong `DATABASE_MIGRATION_URL`, role **postgres**. Một kết nối
mới đã xác thực thành công qua TLS; transaction được đặt **READ ONLY** trước các
SELECT catalog. Role không phải superuser nhưng có **CREATE ROLE, CREATE DATABASE,
BYPASSRLS**, LOGIN và connection limit -1. Đây là credential quản trị/migration có
phạm vi tác động lớn; không được coi là credential test hoặc chỉ là publishable key.

| Consumer/configuration | Quan sát | Khi rotate postgres password |
|---|---|---|
| `backend/runtime.txt` | Bản plaintext rời, untracked, không bị ignore tại thời điểm kiểm tra | Loại bỏ bản plaintext sau containment đã được owner duyệt; không thêm giá trị mới vào file này |
| `backend/.env: DATABASE_MIGRATION_URL` | Cùng endpoint và cùng password bị lộ | Cập nhật riêng field này bằng secret input, không qua chat/argv/log |
| `backend/.env: DATABASE_URL` | Role moodprint_backend, password khác | Không đổi runtime credential trong đợt rotate owner này |
| SSM `/moodprint/staging/runtime`, version26 | DATABASE_URL=moodprint_backend, password khác; không có DATABASE_MIGRATION_URL | Không cần sửa SSM để thay owner password theo snapshot hiện tại |
| Alembic `backend/alembic/env.py` | Ưu tiên DATABASE_MIGRATION_URL, fallback DATABASE_URL; nhận env tường minh | Refresh env của process/terminal migration trước lần dùng tiếp theo; không chạy migration để test login |
| `apply_supabase_review.py`, `provision_supabase_runtime.py`, `test_supabase_fullstack.py` | Các tool quản trị đọc migration owner | Ngưng apply/provision trong cửa sổ rotate; sau đó dùng config mới, không replay DDL |
| `inspect_database.py` | Có thể chọn migration credential để đọc catalog | Là consumer read-only, vẫn cần config mới |
| CI secrets, máy khác, dump/BI, saved IDE/database clients, shell exports | Chưa có inventory đầy đủ | Owner xác nhận tên consumer và update qua secret store tương ứng |

Scan exact password trong **nội dung file tracked hiện tại** không tìm thấy match;
điều này không chứng minh lịch sử git, stash, artifact CI, shell history, snapshot,
backup hoặc máy khác sạch. Không có bằng chứng về việc credential đã bị sử dụng trái
phép; khả năng đó chưa được loại trừ. Không paste password hoặc hash vào ticket/evidence.

## Rotation order, verification và rollback — đề xuất chờ owner duyệt

1. **Chuẩn bị đường khôi phục quản trị độc lập.** Owner xác nhận đăng nhập Dashboard
   đúng project, quyền reset Database password, MFA và password manager dùng được.
   Xác nhận runtime moodprint_backend đang khỏe. Dừng riêng các migration/admin task
   đang hoặc sắp chạy; giữ runtime phục vụ bình thường. Hoàn tất inventory consumer
   postgres bên ngoài bảng trên. Không dùng credential cũ làm phương án rollback.
2. **Tạo secret mới trong password manager**, ghi nhận thời điểm bắt đầu và người thực
   hiện; không tạo plaintext file tạm, không đưa secret vào câu lệnh/SSM Run Command,
   SQL editor history, clipboard artifact hoặc CI output. Không cần đổi Supabase JWT,
   anon/publishable/service-role key, SMTP hay runtime-role password chỉ vì vụ lộ này.
3. **Owner reset project Database password trong Supabase Dashboard → Database
   Settings**, đúng project đã xác nhận. Đây là postgres password reset, không phải
   chạy lại script tạo role. Hướng dẫn hiện hành cho biết các managed service được
   cập nhật tự động; external consumer dùng password trực tiếp cần cập nhật riêng.
   [Nguồn chính thức](https://supabase.com/docs/guides/database/postgres/roles).
4. **Cập nhật riêng migration DSN của từng consumer đã inventory**. Giữ nguyên host,
   port, database, username và TLS; dùng URL parser để encode password đúng. Với
   `backend/.env`, chỉ thay DATABASE_MIGRATION_URL. **Không chạy nguyên helper
   configure_database.py hiện tại cho thao tác này**: helper ghi cả DATABASE_URL và
   có thể thay runtime role bằng owner. Refresh shell/process đang giữ biến cũ.
   Theo evidence hiện tại không update SSM runtime, không restart API/workers.
5. **Kiểm tra positive và negative bằng kết nối mới**, chỉ SELECT metadata trong
   READ ONLY transaction, timeout5s; chỉ ghi PASS/FAIL, role category, TLS boolean và
   error class. New postgres credential phải login đúng role/TLS; old credential phải
   bị từ chối trên pooler endpoint đã dùng và direct endpoint nếu đường mạng hỗ trợ.
   Nếu endpoint trực tiếp không truy cập được, ghi UNKNOWN và kiểm tra lại từ môi
   trường có đường mạng, không coi timeout là password bị revoke. Cho thời gian
   propagation/pooler cache rồi kiểm tra lại có giới hạn; không tạo retry storm.
6. **Xác minh runtime độc lập**: kết nối mới moodprint_backend và public ready phải
   tiếp tục PASS; health API/web/proactive/maps ổn, không tăng restart/5xx/error rate.
   Nếu có authentication failure, dừng admin task và sửa consumer mapping/encoding;
   không tự động đổi runtime secret hoặc redeploy. Password change không tự đóng mọi
   kết nối đã xác thực: owner review aggregate postgres connection counts, rồi chỉ
   kết thúc session đáng ngờ/không còn cần thiết trong bước containment được duyệt
   riêng. Không terminate hàng loạt managed-service connection.
7. **Dọn bản plaintext và đóng incident** sau khi new PASS / old REJECTED / runtime
   healthy. Owner duyệt xóa `backend/runtime.txt`; không sửa `.gitignore`. Kiểm tra
   phạm vi lịch sử/artifact/backup có liên quan bằng công cụ redaction, thu hồi bản
   sao theo retention và ghi kết quả không chứa secret. Không rewrite git history
   nếu chưa có bằng chứng secret từng được commit và kế hoạch owner duyệt.

**Rollback thực tế:** nếu new login thất bại, giữ migration/admin task dừng và dùng
Dashboard/password manager để sửa target, URL encoding hoặc reset sang **một secret
mới khác**, sau đó update consumer và verify lại. Không khôi phục exposed password.
Image rollback/staging.previous.env không khôi phục DB password và không thay thế
credential recovery. Không cần image rollback khi runtime-role credential không đổi;
nếu xuất hiện outage, trước hết xác minh role bị tác động và health, rồi owner quyết
định recovery cụ thể. Không đóng incident khi old password còn login được hoặc khi
không chứng minh được new credential có thể kết nối.

## Cloud/runtime: instance đã chạy, không cần Start

[Evidence cloud](evidence/round2-cloud.json) supersede snapshot t3.small trước đây
cho instance MoodPrint/staging tại Sydney. EC2 hiện **running m7i-flex.large**, x86_64,
2vCPU, host memory khoảng7.59GiB usable (SKU8GiB); IMDSv2 required. EBS30GiB gp3
encrypted,3000IOPS,125MiB/s, in-use. Không thực hiện Start/Stop/resize.
Không dùng phép tính T3 CPU-credit cho instance hiện tại; m7i-flex có CPU baseline
40% và cơ chế Flex riêng, nên sustained CPU và chi phí vẫn cần đo theo SKU thực tế.
[AWS M7i/M7i-flex specifications](https://aws.amazon.com/ec2/instance-types/m7i/).

SSM Run Command đã **Success**, response0, nên đã chứng minh khả năng thực thi
diagnostic (khác với chỉ SSM Online). Payload tĩnh được lưu tại
[tool đã review](evidence/tools/round2-runtime-diagnostic.py): chỉ đọc host totals,
container health/status/restarts/image IDs và numeric/boolean allowlist; không đọc
Docker log bodies, user payload hay dump environment. TCP22 từ máy kiểm tra timeout;
chưa có authenticated SSH session. Không mở security group hoặc sửa SSH để kiểm tra.

| Runtime observation | Value / implication |
|---|---|
| Services | web,api,proactive,maps: running, healthy; restart0 mỗi service |
| Host uptime | ~1319s; snapshot sau boot gần đây, chưa có baseline dài |
| Host available memory | ~6.62GiB; no swap; load averages0.15/0.12/0.05 |
| API snapshot |158.9MiB/768MiB; CPU1.99%; không phải peak hay load test |
| Proactive/maps/web |135.6/82.3/53.15MiB; limits384/256/256MiB |
| Effective pool env | API4+1; proactive2+0; maps1+0; steady maximum8 connections |
| Effective AI env | global10,user2,timeout60s,budgetUSD20,accounting true |
| CAPTCHA/proactive flags | true trong deployed allowlist |
| Image identity | Docker image IDs có trong JSON; registry manifest digest/release SHA/provenance **chưa verified** |
| Release poller | timer active; chưa thay đổi state hoặc chạy deploy |
| 5xx/error aggregate, cgroup throttle/OOM history | **UNKNOWN**; không thay bằng zero |

DNS `moodprint.duckdns.org` trỏ đúng EIP của target; TLS1.3 certificate valid đến
2027-01-23. GET `/` và `/api/v1/health/ready` trả200, không đọc response bodies.
Hai latency sample717/1389ms là connectivity checks đơn lẻ, không phải p95/capacity.
Kết hợp DNS/EIP/health chứng minh target đang phục vụ endpoint public đã cấu hình;
tag staging và các probe **không chứng minh có traffic production/người dùng thật**.
Traffic role, hourly request volume và 5xx distribution cần aggregate metrics được
instrument riêng; tránh đọc hoặc lưu log chứa IP, URI, token hoặc journal/chat content.

SES vẫn **sandbox**, production_access=false, sending_enabled=true, quota200/24h,
1/s,SentLast24Hours1. Chưa gửi email, request production access hoặc đổi identity/DNS.
Hạ tầng đang chạy khỏe tại thời điểm chụp không thay thế controlled load test,
backup/restore rehearsal, alarm validation hoặc release gates. Các bước cloud có
mutation phải dựa trên runbook cụ thể và owner authorization tương ứng.

## Kiểm tra chất lượng evidence

Script điều tra chạy thành công với secret suppression; SQL chỉ SELECT catalog sau
SET TRANSACTION READ ONLY. Ruff PASS cho hai script mới. JSON không chứa secret,
DSN, session identifier hay response payload; file plaintext ban đầu được giữ nguyên
để owner quyết định containment. CLI Supabase v3 vừa đổi hosted targeting/confirmation
theo [changelog2026-11-04](https://supabase.com/changelog); runbook này dùng Dashboard,
không giả định flags CLI cũ có thể dùng an toàn.
