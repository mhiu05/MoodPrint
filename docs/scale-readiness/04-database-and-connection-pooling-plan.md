# Kế hoạch database và connection pooling

> **Implementation, 2026-11-05:** Yêu cầu hiện hành cho phép local engineering và read-only cloud. Target AI toàn ứng dụng **$50/ngày**, chưa kích hoạt production; campaign staging tối đa **$3 tổng cộng**, chỉ `gpt-6-luna` generation, không judge API. D03/D05/D10/D12 đã được chấp thuận. Mỗi production mutation cần approval riêng. Các đoạn audit-only/$20/$5 bên dưới là baseline lịch sử. [Tiến độ](12-implementation-progress.md), [cloud](13-cloud-inventory-redacted.md), [approval proposals](14-owner-decisions-required.md), [kết quả](15-test-results.md) là nguồn cập nhật; release vẫn **NO-GO**.

Ngày audit: **05/11/2026**. Phạm vi: đọc mã và tài liệu, lập kế hoạch; không thay runtime, cấu hình, migration, test hay tài nguyên cloud. Các mốc **1.000 tài khoản đăng ký**, **100 lượt signup trong 60 giây**, **50 người dùng AI hoạt động liên tục 15 phút** là mục tiêu kiểm chứng, **chưa đo trong audit này**. “50 active” phải được định nghĩa bằng workload, cadence gửi lượt, số stream và mức AI được admission; không đồng nghĩa 50 kết nối PostgreSQL hay 50 request trả 202.

Liên quan: [tóm tắt](00-executive-summary.md), [phân tích dung lượng](02-capacity-and-bottleneck-analysis.md), [benchmark](07-load-testing-and-benchmark-plan.md), [roadmap](08-implementation-roadmap.md), [việc HUMAN cần làm](09-human-action-checklist.md), [release gates](10-release-readiness-gates.md).

## 1. Kết luận và độ tin cậy

Mã hiện có pool hữu hạn, session lookup có index, phân trang chat, transaction ngắn quanh model và job claim có fencing. Chưa đủ bằng chứng để kết luận đạt tải mục tiêu. Các việc MUST trước gate tải là xác minh ngân sách cloud thực, sửa mô hình ngân sách để đếm mọi process/overlap, đo polling và lock contention, kiểm thử provisioning đồng thời, cùng kế hoạch recovery bao gồm Storage.

| Trạng thái | Bằng chứng | Hệ quả |
|---|---|---|
| VERIFIED trong repository | Compose API `4+1`, proactive `2+0`, Maps `1+0`: `deploy/compose.staging.yml:9`, `:10`, `:11`, `:43`, `:44`, `:75`, `:76` | Một bộ service có trần 8 connection ứng dụng; nếu cả ba overlap hai thế hệ thì 16 |
| VERIFIED trong repository | Code default là `5+2`, timeout 10 s: `backend/app/core/config.py:103`; runtime example cũng `5+2`: `deploy/runtime.env.example:5` | Chạy ngoài Compose có budget khác. Không được ghi default hiện tại là `8+4` |
| VERIFIED trong repository | `budget.py` vẫn tính 2 API ×7 + một proactive 2, không có Maps: `backend/app/infrastructure/database/budget.py:3`, `:14`, `:20`, `:43` | Warning trong `backend/app/main.py:38` chưa bảo vệ topology hiện nay; không đọc capacity cloud và chỉ warning |
| Giả định ngân sách, không phải xác minh cloud hiện tại | `APPROVED_ROLE_LIMIT=20`: `backend/app/infrastructure/database/budget.py:14`; tài liệu lịch sử báo đọc được 20 tại `docs/reliability/implementation/02-supabase-changes.md:16` | 20 chỉ là đầu vào dự kiến cần HUMAN đọc lại |
| VERIFIED SQL được lưu | SQL tạo login ghi **CONNECTION LIMIT 10** và grant `moodprint_app`: `deploy/supabase/reviewed-sql/supabase-runtime-login-review.sql:7`; provisioning dùng đúng artifact: `scripts/provision_supabase_runtime.py:23` | Fresh provisioning không tự trở thành 20. Không sửa SQL đã duyệt hoặc manifest để “khớp giả định” |
| UNKNOWN hiện tại | Compute/plan, region đang chạy, role limit thực, pooler limits, Postgres version, DB size/IOPS, backup/PITR, deployed env/replica count | Local env, tên host và báo cáo cũ không chứng minh cấu hình deployed hôm nay. Audit này không kết nối cloud |

`8+4` chỉ là lịch sử được nhắc trong `docs/backend/operations.md:26` và `budget.py:8`; comment proactive trong Compose tại `:42` vẫn kể budget cũ. Cần một nguồn cấu hình và bảng dung lượng thống nhất trước khi tăng worker/replica.

## 2. AS-IS: kết nối, process và transaction

Engine chuyển URL sang `postgresql+psycopg`, đặt `pool_size`, `max_overflow`, `pool_timeout`, `pool_pre_ping=True`, `hide_parameters=True`, `prepare_threshold=None`, connect timeout 5 s; `expire_on_commit=False`: `backend/app/infrastructure/database/connection.py:15`, `:21`, `:28`, `:30`. Dependencies khóa SQLAlchemy 2.0.55/psycopg 3.3.6 ở `backend/pyproject.toml:8`. Không dùng asyncpg trong runtime hiện tại. `DATABASE_POOL_MODE` có default `session` (`backend/app/core/config.py:18`) nhưng engine không dùng field này để chọn endpoint, pool class hay flags; đổi nhãn không chuyển topology.

API được thiết kế một process (`backend/app/__main__.py:9`, `:15`). Sweeper, embedding/journal index, guest cleanup và storage cleanup chạy task trong API, chia sẻ **cùng engine**, không cộng thêm một pool cho mỗi task (`backend/app/main.py:136`, `:201`, `:243`). Tuy nhiên chúng tranh cùng 5 slot Compose, có thể làm request chờ. Proactive và Maps có engine riêng (`backend/app/jobs/proactive.py:373`; `backend/app/jobs/maps_search.py:29`); Maps ép pool 1+0 tại `:72`. Một worker chạy sai entrypoint/default vẫn có thể dùng pool 5+2.

| Đường thực thi | Transaction/lock đang có | Đánh giá cần giữ hoặc đo |
|---|---|---|
| Session bootstrap | `/session` xác thực và dựng view trong một checkout, `backend/app/modules/auth/routes.py:181`; lookup hash join User tại `backend/app/core/security.py:70` | Điểm tốt; không nhân đôi checkout. Không cookie bị từ chối trước DB |
| Request thông thường | `require_actor` có session đọc riêng (`security.py:108`); domain `transaction` revalidate và mặc định khóa User (`security.py:131`, `:173`) | Hai pha tuần tự, không nhất thiết hai connection đồng thời; nhiều query/auth round trip và serial hóa theo một user cần đo |
| Session freshness | Kiểm tra helper sống trên `auth.sessions`, `security.py:52`; sliding expiry chỉ ghi tối đa mỗi 15 phút, `:84` | Không bỏ revocation/consent/deletion check để đạt tốc độ; expiry mặc định 12 h, cookie cap 7 ngày (`config.py:107`, `:108`; auth/routes.py:292) |
| AI admission và model | Transaction admission `backend/app/ai/chat_routes.py:385`; runtime revalidate trong transaction tại `runtime.py:777`, thoát trước `provider.run_reply` tại `:860` | Không thấy giữ một checkout suốt model I/O trong đường này. Cần regression test xác nhận dưới tải/cancellation |
| Policy khi AI chạy | `runtime.py:826` kiểm tra mỗi 0, 5 s; `check` mở transaction và khóa User tại `runtime.py:333` | 50 run đang sinh tương ứng khoảng 100 vòng check/s, chưa tính callbacks và tool; có khả năng tranh lock cùng user |
| SSE chat lưu lịch sử | `chat_routes.py:767`, `:806`: poll mỗi 0, 25 s; `durable_run` transaction `lock=False` cho polling tại `:654` | Không giữ DB qua sleep/yield; khoảng 200 poll transaction/s với 50 stream. Mỗi vòng có nhiều SELECT, receipt/steps tùy protocol; không gọi 200 là 200 SQL/s |
| Proactive | Claim `SKIP LOCKED`, lease/fence trong `backend/app/jobs/proactive.py:160`; timeout transaction 2 s lock/5 s statement/15 s idle tại `:69`; generation ngoài pha `_open`/publish tại `backend/app/ai/proactive/executor.py:172`, `:215`, `:391` | Giữ nguyên fencing và timeout. Không dùng comment “hosted has no idle timeout” làm số liệu cloud hiện tại |
| Journal vector/index | Claim ngắn tại `backend/app/modules/journal/indexing.py:124`, embed sau khi transaction đóng tại `:164`, recheck fence ở `:172` | Tốt về connection; batch/reconcile và policy reads vẫn dùng pool API |
| Maps | `backend/app/ai/search/maps_jobs.py:180` claim, ra DB rồi provider I/O tại `:212`, settle fence tại `:265` | Giữ lease/fence; off switch không tự dừng cleanup (`backend/app/jobs/maps_search.py:35`) |
| Journal media | `backend/app/modules/journal/media_routes.py:124`, `:147`, `:181` gọi Storage giữa hai transaction xác thực | Giữ revalidation sau I/O. Storage deletion cũng tách I/O tại `backend/app/modules/journal/storage.py:181` |
| Retention/deletion | `purge_expired` giữ **một transaction** qua nhiều nhóm bảng (`backend/app/jobs/retention.py:20`); nhiều batch 1000 `SKIP LOCKED`; xóa journal nạp tất cả entry/media của user (`backend/app/modules/journal/service.py:91`) | Mỗi batch hữu hạn chưa đảm bảo tổng transaction ngắn; delete user lớn và startup sweeps có thể tranh pool/lock |

Số vòng đọc sơ bộ `R_db ≈ N_saved_stream/0,25 + N_running_ai/0,5 + R_HTTP + R_jobs + R_callbacks`. Với 50 ở cả hai nhóm, riêng hai thành phần đầu là 300 vòng/s. Đây là **suy luận tĩnh**, có thể giảm khi run kết thúc sớm và tăng bởi nhiều tab/reconnect/tool. Thời gian giữ connection trung bình `h` giây cho throughput `R` cần gần `R×h` checkout trung bình; nếu `h=0,01` thì 300 vòng/s đã dùng trung bình 3 checkout, nếu `h=0,02` là 6, vượt 5 slot API. Hai giá trị `h` chỉ là sensitivity example, chưa đo và không thay thế p95/p99.

## 3. Ngân sách connection TO-BE và gate topology

Phân biệt **client → pooler** và **pooler → Postgres**. Transaction pooling không cho phép nâng pool vô hạn: còn trần client, trần backend mỗi role/mode/database, role connection limit, `max_connections` và các dịch vụ Supabase khác. Supabase nêu pool size theo role, vì thế tách role tránh dùng chung quota app nhưng có thể làm tổng backend pool tăng; phải tính toàn project. Xem [connection management](https://supabase.com/docs/guides/database/connection-management), [pooling and limits](https://supabase.com/docs/guides/database/connecting-to-postgres/pooling-and-limits).

Đặt `p_i = pool_size_i + max_overflow_i`, `n_i` là số process sống đồng thời **kể cả deploy overlap**, `C_other` là mọi client dùng runtime role ngoài ba service. Khi session mode giữ một backend cho client, bound ứng dụng là:

```text
C_app = n_api*p_api + n_proactive*p_proactive + n_maps*p_maps + C_other
C_runtime_total = C_app + C_runtime_ops
C_project = C_runtime_backends + C_migration_admin + C_auth + C_storage
            + C_postgrest + C_realtime + C_monitoring_reserved + C_other_roles

C_runtime_total <= L_runtime - H_runtime
C_runtime_pooler_backends <= P_role_mode_database
C_pooler_clients <= K_pooler_clients
C_project <= max_connections - H_project
```

`L_runtime`, `P`, `K`, `max_connections` và service peaks đều UNKNOWN tại audit. Không cộng “4 slots cho Supavisor” như một pool tiêu thụ độc lập không có số liệu; Supavisor server connections đã nằm trong backend demand. Chỉ cộng overhead/control connection nếu inventory thực chứng minh.

| Kịch bản | API | Proactive | Maps | App bound | Budget role 20 giả định |
|---|---:|---:|---:|---:|---|
| Compose bình thường |1×5=5|1×2=2|1×1=1|8|12 chưa phân bổ |
| Chỉ API overlap |2×5=10|2|1|13|7 chưa phân bổ |
| Cả ba overlap |10|2×2=4|2×1=2|16|4 chưa phân bổ |
| Dùng default 5+2, cả ba overlap |2×7=14|4|2|20|Không còn headroom |
| Default lịch sử 8+4, cả ba overlap |24|4|2|30|Vượt giả định 20 |
| Compose hai API steady, cả stack rolling overlap |4×5=20|4|2|26|Vượt giả định 20; chưa được phép scale như vậy |
| Fresh provisioning cap 10, Compose all-overlap |10|4|2|16|Vượt SQL cap 10 |

**Preset ứng viên cho test, không phải thay đổi đã áp dụng:** tiếp tục API 4+1/proactive 2+0/Maps 1+0, tối đa một bộ steady, tối đa hai thế hệ khi deploy. Nếu HUMAN xác nhận `L_runtime≥20`, phân bổ all-overlap 16, runtime diagnostic tối đa 1, **runtime emergency reserve 3**. Không cho dev/CI dùng role production, `C_other=0` là điều kiện phải chứng minh. Migration dùng role riêng, tối đa 1 connection; admin dùng role riêng, tối đa 1; cả hai vẫn tính vào `C_project`, nên không được coi 20 là ngân sách toàn DB. Trước migration, dừng workload benchmark và tránh deploy overlap; không chạy migration như một task startup của mọi replica (`backend/app/main.py:72`).

Nếu `P_role=15`, bound 16 đã vượt pooler dù role 20; phải chọn no-overlap worker đã được deploy script chứng minh, giảm pool sau benchmark, hoặc HUMAN duyệt capacity mới. Không tăng role limit tự động. Ví dụ với `max_connections=60` **chỉ để tính**, runtime 16 + diagnostic 1 + migration 1 + admin 1 =19; phần còn 41 phải đủ Auth/Storage/Postg REST/Realtime/reserved và `H_project`, không được tuyên bố 41 đều rảnh. Công thức chốt `C_runtime_allowed = min(L_runtime-H_runtime, P_role, max_connections-C_services_peak-C_migration_admin-H_project)`; transaction mode dùng đo backend peak thay bound client nhưng vẫn giới hạn `K`.

### Chọn session, transaction hay direct

AS-IS giữ psycopg và pool hữu hạn. Shared session pooler là lựa chọn phù hợp khi VM/container cần IPv4; direct phù hợp long-lived backend khi network hỗ trợ. Shared transaction pooler thường dùng cổng 6543, session dùng 5432; host cùng port không đủ suy ra toàn cấu hình. Sao chép endpoint đã xác nhận từ Connect của project, không tự ghép host name. Shared transaction không hỗ trợ prepared statements, còn session hỗ trợ. Xem [hướng dẫn kết nối Supabase](https://supabase.com/docs/guides/database/connecting-to-postgres).

TO-BE ưu tiên benchmark AS-IS trước. Chỉ thử transaction pooling như một nhánh có rollback nếu pool backend bị giữ idle và gây thiếu capacity. Giữ `prepare_threshold=None` cho psycopg, đúng [hướng dẫn prepared statements](https://supabase.com/kb/troubleshooting/disabling-prepared-statements-qL8lEL). Audit session-level `SET`, temp table, LISTEN và advisory lock; các `pg_advisory_xact_lock` hiện thấy tại `backend/app/ai/accounting.py:103`, `backend/app/ai/search/accounting.py:37` là transaction scoped, không đổi sang session locks. `SET LOCAL` qua `set_config(..., true)` trong proactive phù hợp phạm vi transaction. Không đổi sang Null Pool chỉ để giảm một số liệu connection; long-lived API có thể mất lợi ích tái dùng socket và tăng connect/TLS load.

**Nếu tương lai đổi asyncpg:** không sao chép `prepare_threshold` của psycopg sang asyncpg. Raw asyncpg cần `statement_cache_size=0` và tránh prepare tường minh. SQLAlchemy asyncpg còn có `prepared_statement_cache_size=0`; dialect vẫn gọi `Connection.prepare()`, nên hai flags không tự chứng minh shared transaction compatibility. Cần canary trên đúng driver/SQLAlchemy/pooler, không chỉ unit test URL. DDL từ process khác có thể làm cache type/statement stale, nên migration/deploy phải có drain/restart phù hợp. Xem [SQLAlchemy asyncpg dialect](https://docs.sqlalchemy.org/en/20/dialects/postgresql.html#prepared-statement-cache). Audit này không đề xuất đổi driver.

## 4. Query, index, RLS và tăng trưởng

| Dữ liệu/đường đọc | Index/bound đã thấy | Khoảng trống hoặc phép đo cần làm |
|---|---|---|
| User provisioning và session | `users.auth_subject` unique; `auth_sessions.token_hash` unique, `user_id` và `expires_at` indexed: `backend/app/infrastructure/database/models.py:44`, `:84` | Confirm actual catalog trên đúng schema/revision; đo join/helper, không thêm index trùng unique |
| Chat list/page | Owner/activity và expiry index `backend/app/ai/models.py:55`; message unique `(conversation_id,sequence)` và run index tại `:78`, `:86`; page query `backend/app/ai/persistence.py:113` | Đo rows read, join child runs, receipt/steps trên SSE; index không thay thế giảm tần suất polling |
| AI quota/retention | `(user_id,origin,created_at)` và active conversation partial unique ở `backend/app/infrastructure/database/models.py:219`, `:224`; admission có advisory transaction lock ở `backend/app/ai/persistence.py:423` | Lock toàn cục bảo vệ budget đúng nhưng có thể serial hóa admission. Chỉ tối ưu sau đo wait; không bỏ lock làm tăng spend |
| Journal list | Owner/date/created/id và owner/status/updated tại `backend/app/modules/journal/models.py:58`; list có COUNT + page + media batch (`backend/app/modules/journal/routes.py:89`; `service.py:47`) | Count/keyword/filter JSON có thể tốn thêm scan. Kiểm EXPLAIN synthetic 1.000 users, 90 ngày và user có nhiều entries/ngày |
| Journal hybrid | Owner/model/dimensions index `backend/app/modules/journal/ai_models.py:47`; retrieval count + cosine sort + `icontains` + recent ở `backend/app/modules/journal/retrieval.py:62`, `:72`, `:76` | Không thấy HNSW/IVFF lat hoặc trigram trong migration 0029. Exact search trong owner/date scope có thể đủ; cần đo trước khi thêm vector/GIN index |
| Memory retrieval/jobs | Scope B-tree `backend/app/ai/embedding_models.py:102`, due index `:73`; memory scope `database/models.py:166` | Đo per-user corpus và scheduler queue; không tự tạo global ANN có nguy cơ ảnh hưởng privacy/filter recall |
| Retention | Chat expiry batch 250 tại `backend/app/ai/persistence.py:366`; journal/mood 90 ngày, usage/run 90 ngày, proactive 30 ngày: `backend/app/jobs/retention.py:35`, `:49`, `:81`, `:100`, `:116` | Multi-table transaction dài; `idempotency_keys.created_at` không có index thời gian trong `database/models.py:176`, mặc dù purge dùng expiry predicate (`retention.py:152`). Là ứng viên EXPLAIN, chưa kết luận cần index |
| Session và storage tombstone | Session expiry index có sẵn; storage deletion có unique object path và attempts (`backend/app/modules/journal/models.py:88`) | Không tìm thấy purge định kỳ cho registered expired/revoked `AuthSession` trong sweeper đã đọc; logout chỉ revoke (`auth/routes.py:382`). Không nhầm TTL authorization với xóa row. Cần retention policy và batch; storage tombstone queue cần retry lag/attempt cap quan sát được |

RLS trong private schema cho runtime role là `USING(true) WITH CHECK(true)`, các role public bị revoke (`backend/alembic/versions/0019_journal.py:16`, `:28`; `0029_journal_intelligence.py:16`, `:27`). Đây là **backend trust boundary**, không phải RLS tự lọc tenant theo JWT. Runtime BFF phải kiểm owner ở mọi query; `get_owned_entry` có user/date scope (`backend/app/modules/journal/service.py:28`), `owned_conversation` có owner/expiry (`backend/app/ai/persistence.py:52`). Không thêm `auth.uid()` hàng loạt vào role BFF không mang JWT rồi cho rằng tăng bảo mật. Không expose schema/private tables để tăng tốc frontend.

Helper `SECURITY DEFINER`, `search_path=''` và revoke PUBLIC ở `backend/app/infrastructure/database/provider_session.sql:8`, `:26` là bridge Auth cần review riêng; migration 0017 thay helper guest-aware (`backend/alembic/env.py:80`; `backend/alembic/versions/0017_guest_security.py:179`). Phải kiểm current function definition/grants và role membership actual, không dùng file bootstrap cũ để overwrite definition mới. Bản initial role chain: `moodprint_backend → moodprint_app → moodprint_runtime`, tham chiếu `deploy/supabase/reviewed-sql/supabase-runtime-login-review.sql:9` và `supabase-initialization-review.sql:435`.

### Mô hình dung lượng cần đo

`U=1.000` registered; `a` tỷ lệ active/ngày; `t` turn/user/ngày; `b` assistant bubbles/turn; `j` journal/user/ngày; `m` media/entry; `s` bytes/media trung bình; `d_chat≤90`, `d_journal=90`. Các tỷ lệ đều là biến đầu vào, không phải số liệu sản phẩm.

```text
chat_rows ≈ U*a*t*(1+b)*d_chat
journal_rows ≈ U*a*j*90
media_objects ≈ journal_rows*m; storage_bytes ≈ media_objects*s
embedding_bytes_raw ≈ indexed_documents*dimensions*4  (chưa gồm row/index/WAL)
session_rows ≈ U*logins_per_user_per_day*days_without_purge
db_bytes ≈ SUM(pg_total_relation_size(table)) + WAL/operational headroom
```

Ví dụ giả định `a=0,2,t=10,b=2,d_chat=30,j=1,m=1,s=2MiB`:180.000 message rows, 18.000 journal entries, khoảng 35, 2 GiB media. Với 18.000 vector 1024 chiều, payload vector thô khoảng 70, 3 MiB; không phải tổng DB. Media vì vậy có thể vượt chi phí text/vector sớm. Per-file/per-entry cap (`media_routes.py:32`, `:101`) chưa phải storage quota theo user/project. Cần đo avg/p95 serialized row, TOAST/index size, WAL/day, dead tuples, cleanup lag và storage egress; không chọn compute chỉ theo số user.

## 5. Signup/provisioning và độ trễ vùng

`/auth/signup` chỉ gọi Supabase Auth rồi trả 202 (`backend/app/modules/auth/routes.py:299`); user app được tạo khi login sau xác minh provider, với `ON CONFLICT(auth_subject) DO NOTHING`, khóa User, upsert 4 consent, tạo một session (`:241`, `:251`, `:265`, `:271`). Provider HTTP nằm trước transaction app. Vì vậy test 100 signup/60 s không đo cùng đường với 100 concurrent first-login/session bootstrap. Phải test cả hai, retry cùng identity và đồng thời nhiều identity; kiểm một User/auth_subject, không trùng consent, không mất session cookie, không bỏ eligibility/CSRF.

`IP_LIMIT=40/900s`, `EMAIL_LIMIT=3/3600s` tại `auth/routes.py:228` là giới hạn có chủ ý:100 signup cùng một IP bị từ chối một phần. Benchmark phải ghi phân bố IP và phân biệt legitimate admission với 429 do limit; không đổi production limiter để làm đẹp kết quả. Auth quota, CAPTCHA/email provider/rate limits là external dependency cần HUMAN xác minh trong [09](09-human-action-checklist.md).

Region deployed của API và Supabase **UNKNOWN**; tên trong local env/báo cáo cũ không phải proof. Nhiều SQL round trip trên session/AI làm RTT liên vùng có thể chi phối latency. Cần ghi API region, DB region, private/public path và đo connect/TLS/`SELECT 1`/session transaction từ chính runtime staging. Chỉ đề xuất co-location sau đo và xét data residency/egress/downtime; không tự move region.

## 6. Compute, backup và recovery

Tài liệu Supabase kiểm tra ngày 05/11/2026 nêu Nano/Micro mặc định 60 database connections, 200 pooler clients, pool 15; Small 90/400/15; Medium 120/600/15. Đây là bảng tham chiếu, **không xác định compute của MoodPrint** và không thay role limit. Đo CPU/RAM/IOPS/disk/active queries trước lựa chọn nâng compute; không khuyến nghị nâng `max_connections` đơn lẻ. Xem [compute và giới hạn](https://supabase.com/docs/guides/platform/compute-and-disk).

Backup/PITR đang bật hay không **UNKNOWN**. Supabase daily backup theo plan có retention khác nhau; database backup không chứa blob Storage, và custom-role passwords không được lưu trong daily backup. Phải có recovery cho DB, object, secret/role và deletion tombstone cùng nhau; restore không được làm dữ liệu đã xóa/guest đã hết hạn phục hồi vào serving path. Xem [Supabase backups](https://supabase.com/docs/guides/platform/backups). RPO/RTO phải do HUMAN chốt; ứng viên thảo luận RPO≤24 h với daily backup hoặc≤15 phút khi PITR đủ điều kiện, RTO≤4 h sau rehearsal; đây chưa phải SLA và PITR/cloud backup có thể phát sinh tiền.

Changelog hiện có breaking change CLI v 3 ngày 04/11/2026; nếu sau này dùng CLI, phải khám phá `--version`/`--help` và pin version, không copy lệnh hosted từ runbook cũ. Audit này không chạy CLI cloud hoặc upgrade. Xem [changelog CLI v 3](https://supabase.com/changelog/supabase-cli-v3).

## 7. Backlog thực thi

Tất cả mục dưới đây là **kế hoạch chưa thực hiện**. Độ phức tạp S≈0, 5–1 ngày, M≈1–3 ngày, L≈3–5 ngày làm việc, chưa gồm thời gian chờ HUMAN/benchmark. Owner CODEX chuẩn bị code/test/review; owner HUMAN quyết định hoặc thao tác tài nguyên/account/cloud. Không dùng plan này như quyền tự chạy cloud SQL, load test hosted, đổi plan, xoay secret hay apply migration.

### P2-D01 — MUST — Xác minh nguồn sự thật cloud và role

- **Vấn đề/bằng chứng:** cloud UNKNOWN; constant 20 tại `budget.py:14` khác provisioning SQL10 tại `supabase-runtime-login-review.sql:8`; historical observation không còn chứng minh hiện tại.
- **Giả thuyết gốc:** cấu hình cloud đã thay ngoài artifact, nhiều tài liệu còn phản ánh các thời điểm khác nhau.
- **Tệp:** `backend/app/infrastructure/database/budget.py`, `deploy/supabase/reviewed-sql/`, runbook và [09](09-human-action-checklist.md).
- **Giải pháp/bước:** HUMAN inventory deployed endpoint mode, role membership/`rolconnlimit`, pooler client/backend caps, compute, `max_connections`, service peaks, region, migration head, backup/PITR; lưu timestamp và số liệu đã redacted. CODEX đối chiếu grants/hash/revision và tạo plan sửa drift; không sửa artifact đã duyệt tại chỗ.
- **Phụ thuộc/owner:** không phụ thuộc; **HUMAN** cloud inventory, CODEX đối chiếu.
- **Test/nghiệm thu:** review metadata chỉ đọc có timestamp, không URL/password/raw query/user data; role không superuser/BYPASSRLS; tất cả UNKNOWN ảnh hưởng gate có owner; budget dùng đúng verified limits.
- **Phức tạp/rủi ro/rollback/chi phí:** S; nguy cơ chọn nhầm project; dừng nếu fingerprint/role không khớp; read-only không cần rollback; không thêm hạ tầng, công sức HUMAN.

### P2-D02 — MUST — Một ngân sách cho mọi process và overlap

- **Vấn đề/bằng chứng:** `budget.py:20`, `:43` thiếu Maps và worker overlap; Compose comment `:42`, runtime example và operations docs lệch preset.
- **Giả thuyết gốc:** calculator còn mô hình hai service, deployment assumption không encode đầy đủ.
- **Tệp:** `database/budget.py`, `main.py:38`, `core/config.py`, `deploy/compose.staging.yml`, `deploy/runtime.env.example`, deploy scripts, `docs/backend/operations.md`, tests config/deploy.
- **Giải pháp/bước:** CODEX inventory engine/process; encode riêng API/proactive/Maps/other/admin/overlap; gắn preset 4+1/2+0/1+0 hoặc preset đã đo; deployment config gate validate mọi override trước launch; phân biệt warning app và release rejection. Chứng minh stop-before-start nếu dựa vào no-overlap; giữ emergency reserve.
- **Phụ thuộc/owner:** D01, kế hoạch rollout [08](08-implementation-roadmap.md); **CODEX**, HUMAN duyệt capacity/rollout.
- **Test/nghiệm thu:** matrix có steady 8, all-overlap 16, fallback 20, fresh cap 10 reject, thêm replica reject; parse effective config đã redacted; không thêm pool cho task dùng chung engine; migration/admin tính project budget; không dùng production role ở dev/CI.
- **Phức tạp/rủi ro/rollback/chi phí:** M; fail gate có thể chặn rollout hợp lệ; rollback deployment/config revision và giữ topology đã chứng minh, không tăng role ngầm; không tăng recurring cost.

### P2-D03 — MUST — Đo và giảm vòng đọc AI/SSE theo bằng chứng

- **Vấn đề/bằng chứng:** `chat_routes.py:806` poll 4 Hz, `runtime.py:828` check 2 Hz, `durable_run:657` nhiều query; pool API tối đa 5.
- **Giả thuyết gốc:** round trip/auth/receipt lặp lại và RTT có thể chiếm pool trước khi model đạt concurrency 50.
- **Tệp:** `backend/app/ai/chat_routes.py`, `runtime.py`, `persistence.py`, security, SSE tests và load harness.
- **Giải pháp/bước:** CODEX instrument số tick/query/checkout wait/transaction duration theo route+process; benchmark baseline; thử cadence thích ứng hoặc notification dùng chung phù hợp kiến trúc; chỉ lấy projection cần thiết và giảm query lặp trong cùng transaction. Giữ revalidate trước output, revoke/consent/expiry/cursor/gap/reconnect semantics; không cache authorization vô hạn.
- **Phụ thuộc/owner:** D01–D02, workload [07](07-load-testing-and-benchmark-plan.md); **CODEX**.
- **Test/nghiệm thu:** synthetic 50 active 15 phút với 50 saved streams và reconnect/multi-tab; so sánh query/s, pool wait, p95/p99; đề xuất p95 checkout≤100 ms, p99≤500 ms, 0 pool timeout/SQLSTATE 53300, 0 unexpected 5xx; mục tiêu phải được gate owner phê duyệt. Revoke/delete/expiry không lộ thêm payload sau authorization fence; provider stall không giữ checkout qua await.
- **Phức tạp/rủi ro/rollback/chi phí:** L; giảm polling có thể tăng time-to-final hoặc chậm revoke; rollback cadence/flag về baseline và giảm admission nếu cần; synthetic không cần paid API, shared notification có thể thêm phí nếu chọn sau này.

### P2-D04 — MUST — Chốt timeout và lock discipline cho registered path

- **Vấn đề/bằng chứng:** default account lock `security.py:136`; guest có deadline-derived statement/lock timeout `:177`, proactive có 2 s/5 s/15 s (`jobs/proactive.py:74`), chưa thấy equivalent registered app-wide guard. Advisory global ở `accounting.py:103` có chủ đích bảo vệ spend.
- **Giả thuyết gốc:** lock queue hoặc query chậm có thể giữ checkout dài dù provider ngoài transaction.
- **Tệp:** security, database connection/config, AI accounting/admission, job transaction helpers, tests lock/recovery.
- **Giải pháp/bước:** đo blocked chain, transaction age, lock wait trước; chuẩn hóa lock order User→job→run và short transaction; thiết kế `SET LOCAL` timeout theo class request/worker, chỉ đổi role defaults qua HUMAN review; bounded retry cho deadlock/serialization ở idempotent transaction, không retry paid call mù.
- **Phụ thuộc/owner:** D01–D03; **CODEX**, HUMAN cho role settings.
- **Test/nghiệm thu:** local held-row lock/slow SQL/provider timeout/cancel/crash; request kết thúc trong bound, release pool, rollback receipt đúng; không deadlock kéo dài, không duplicate message/spend, không bỏ advisory budget guard.
- **Phức tạp/rủi ro/rollback/chi phí:** M; timeout quá ngắn có thể gây false failure; rollback threshold/flag sau drain, giữ idempotency; không recurring cost.

### P2-D05 — MUST — Benchmark signup và first-login riêng

- **Vấn đề/bằng chứng:** signup 202 chỉ provider ở `auth/routes.py:313`; provisioning thực ở `:251`; shared IP limiter 40/900 s tại `:228`.
- **Giả thuyết gốc:** burst thành công ở Auth vẫn có thể nghẽn pool khi 100 client vào app lần đầu; retry cùng subject có thể tranh unique/user lock.
- **Tệp:** auth routes/provider, session builder, `backend/tests/test_auth_flows.py`, auth test harness.
- **Giải pháp/bước:** synthetic provider và auth/session fixture local; test 100 identities/60 s, 100 first-log ins/60 s, duplicate identity/retry and session startup; phân bố IP hợp lệ và lane same-I P429 riêng; HUMAN xác nhận email/CAPTCHA/Auth quota trước hosted canary.
- **Phụ thuộc/owner:** D02,D04, auth owner và [07](07-load-testing-and-benchmark-plan.md); **CODEX**, HUMAN external quotas.
- **Test/nghiệm thu:**100 expected admissions trong lane distributed-IP, không unexpected 5xx/connection timeout; mỗi subject đúng 1 User/4 consent; session revocation còn hiệu lực, latency/chỉ tiêu ở 07; không chỉnh production limiter chỉ để pass.
- **Phức tạp/rủi ro/rollback/chi phí:** M; harness không đại diện provider email latency; rollback code, không xóa account cloud trong audit; fake provider $0, hosted email/SMS cần budget HUMAN.

### P2-D06 — SHOULD — Lập query plan và index theo workload

- **Vấn đề/bằng chứng:** journal keyword/cosine/count `retrieval.py:63`; no ANN trong 0029, retention Idempotency không có time index ở `database/models.py:176`.
- **Giả thuyết gốc:** số rows trong scope hoặc retention backlog tăng scan/sort; chưa có EXPLAIN để xác nhận.
- **Tệp:** journal retrieval/routes/models, AI persistence/embedding models, retention; migration mới chỉ sau review.
- **Giải pháp/bước:** local synthetic 1.000 users/90 ngày và skew user lớn; `EXPLAIN (ANALYZE, BUFFERS)` SELECT trên synthetic; ghi estimates/actual rows, buffers, sort spill; thử partial/composite/trigram/ANN nếu plan chứng minh cần, cân write cost và filter recall; không thêm index trùng PK/unique/scope.
- **Phụ thuộc/owner:** D03,D08; **CODEX**; HUMAN duyệt migration cloud.
- **Test/nghiệm thu:** plan trước/sau reproducible, số index và footprint báo cáo; owner isolation/recall/date-bound vẫn đúng; migration lock/rollback rehearsal local; query p95/p99 đạt 07 trong dataset skew. `ANALYZE`/DDL không chạy cloud từ task audit.
- **Phức tạp/rủi ro/rollback/chi phí:** M; index tăng WAL/disk và migration locks; rollback index mới theo reviewed migration, không rewrite lịch sử; phí disk/IOPS tùy kết quả đo.

### P2-D07 — SHOULD — Batch retention và xóa dữ liệu lớn

- **Vấn đề/bằng chứng:** `retention.py:21` một transaction nhiều nhóm; `journal/service.py:91` nạp toàn bộ journal của owner; không tìm thấy sweeper expired registered session, logout chỉ revoke.
- **Giả thuyết gốc:** backlog sau downtime và user media lớn gây transaction dài, heap bloat, RAM/pool pressure; authorization TTL không tự purge rows.
- **Tệp:** retention, user lifecycle, journal service/storage, auth session model; data lifecycle/session/storage tests.
- **Giải pháp/bước:** HUMAN chốt TTL cho expired/revoked sessions; CODEX purge theo batch+time budget+`SKIP LOCKED`, commit mỗi lớp công việc, stable key set; giữ storage tombstone trước delete, idempotent resume. Thêm metrics oldest eligible row/queue lag/rows/sec/dead tuples; không xóa active sessions bằng created_at khi còn sliding expiry.
- **Phụ thuộc/owner:** D04,D06,D08; **CODEX**, HUMAN retention/privacy policy.
- **Test/nghiệm thu:** synthetic 90 ngày+backlog, delete lớn, crash giữa batches; active sessions/financial liability không bị purge; lag đề xuất healthy≤60 s, escalation>5 phút; transaction p99 và pool wait không làm canary 07 fail; storage eventual delete verified local fake.
- **Phức tạp/rủi ro/rollback/chi phí:** L; retention sai gây mất dữ liệu, commit split đổi atomicity; rollback worker code/disable destructive purge mới, dữ liệu đã xóa chỉ phục hồi theo policy D10; không cam kết rollback SQL có thể khôi phục row đã purge; giảm disk dài hạn, thêm vận hành.

### P2-D08 — MUST — Kiểm tra RLS/grants và privacy khi tối ưu

- **Vấn đề/bằng chứng:** backend-wide policy true trong `0019_journal.py:29`, `0029_journal_intelligence.py:28`; helper definer `provider_session.sql:8`; role chain không cùng tên login.
- **Giả thuyết gốc:** tối ưu query/role/pooler có thể bỏ owner predicate hoặc cấp quyền rộng, dù unit test single-user vẫn pass.
- **Tệp:** security/provider helper, migrations/reviewed SQL, journal/chat/user ownership query, role tests.
- **Giải pháp/bước:** inventory schema exposure, ownership, function search_path/EXECUTE and latest helper; verify runtime login không owner/superuser/BYPASSRLS, browser roles không private grants; review mọi query mới hai user, revoked consent, guest expiry. Không thêm tenant RLS theo JWT khi BFF không mang JWT mà chưa thiết kế authorization context.
- **Phụ thuộc/owner:** D01 trước thay topology/index/retention; **CODEX**, HUMAN catalog validation.
- **Test/nghiệm thu:** negative cross-user reads/writes/retrieval/SSE/exports; browser/anon/authenticated không gọi private helper/data; role runtime chỉ DML cần thiết; latest migration 0017 guest-aware helper không bị bootstrap ghi đè.
- **Phức tạp/rủi ro/rollback/chi phí:** M; grants sai có thể outage hoặc leak; rollback chỉ grant/migration đã review, không tắt RLS; không recurring cost.

### P2-D09 — SHOULD — Đánh giá transaction pooler bằng canary

- **Vấn đề/bằng chứng:** pool mode chỉ label (`config.py:18`, `connection.py:21`), session giữ backend idle; actual endpoint/mode UNKNOWN.
- **Giả thuyết gốc:** transaction pooler có thể giảm idle backend footprint nếu connection là nút thắt; không đảm bảo giảm query latency/CPU.
- **Tệp:** engine/config validation, deployment env validation, pooler runbook, driver compatibility tests.
- **Giải pháp/bước:** sau baseline, HUMAN chọn endpoint; CODEX local compatibility/canary plan: psycopg flags hiện tại, transaction-scoped config/locks, connect/TLS/recycle, DDL rollout, cancellation, prepared-statement errors; so sánh small Queue Pool với lựa chọn khác có dữ liệu. Chỉ deploy canary khi HUMAN cho phép.
- **Phụ thuộc/owner:** D01–D04,D08; **CODEX** canary/code, HUMAN endpoint/capacity.
- **Test/nghiệm thu:** workload 07 với exact pinned driver/pooler; không `prepared statement does not exist/already exists`, không session state bleed, revocation đúng, server peak/wait cải thiện và không regression p95; không tuyên bố asyncpg tương thích từ cache flag đơn lẻ.
- **Phức tạp/rủi ro/rollback/chi phí:** M; session semantics và connect storm; quay endpoint session đã lưu an toàn, drain/restart engine, không downgrade schema; có thể không tăng phí shared pooler, compute/network tùy plan.

### P2-D10 — MUST — Recovery DB + Storage, compute và region decision

- **Vấn đề/bằng chứng:** region/compute/backup/PITR UNKNOWN; Storage objects không nằm trong DB backup; media growth có thể lớn hơn text.
- **Giả thuyết gốc:** capacity/recovery chưa có inventory cùng một mốc thời gian, restore đơn DB có thể mất media hoặc phục hồi dữ liệu cần xóa.
- **Tệp:** runbook backup/restore/deploy, lifecycle cleanup, storage plan, docs 07/09/10; không thay cấu hình cloud trong audit.
- **Giải pháp/bước:** HUMAN chốt region/plan/RPO/RTO/storage quota/budget và xác minh backup gần nhất; CODEX chuẩn bị rehearsal trên isolated disposable target, disable outbound providers/listeners, restore DB+object metadata/blob fixture, reapply role secrets qua secure channel và run guest/deletion reconciliation trước mở phục vụ; đo thời gian/chi phí. Compute nâng chỉ sau CPU/IOPS/pool/query evidence.
- **Phụ thuộc/owner:** D01,D07,D08 và acceptance [10](10-release-readiness-gates.md); **HUMAN** decision/cloud, CODEX rehearsal/runbook.
- **Test/nghiệm thu:** restore drill có timestamp/RPO/RTO, valid registered session/data đúng policy, expired guest/deleted object không trở lại serving; objects có inventory/check sum redacted, role secrets không log; fail back tested. Gates chưa đạt khi backup chỉ “enabled” nhưng chưa restore.
- **Phức tạp/rủi ro/rollback/chi phí:** L; restore có thể replay paid work/leak deleted data; quarantine giữ outbound off, hủy target rehearsal sau review, không overwrite production; PITR/storage backup/compute/egress cần HUMAN duyệt bill thực.

## 8. Verification đã làm và lệnh cho lần triển khai

Audit này chỉ đọc source, tra tài liệu primary và kiểm tra tài liệu được tạo. **Không chạy pytest, migration, benchmark, provider trả phí hay SQL cloud; không có kết quả capacity mới.** Bằng chứng load cũ ở tài liệu khác không thay cho sustained 15 phút của revision hiện tại.

Lệnh dưới đây là đề xuất cho người thực thi, chạy từ `backend` trong shell riêng. Unit lane đặt `TEST_DATABASE_URL=''`; conftest tắt dotenv và external provider config (`backend/tests/conftest.py:29`). Integration lane bắt buộc URL loopback disposable có hậu tố `_test`, qua guard `backend/tests/database_target.py`; fixture có `drop_all`, vì vậy tuyệt đối không thay bằng runtime URL (`backend/tests/conftest.py:69`, `:106`). Không chạy nguyên toàn suite khi đang cần baseline hẹp.

```powershell
# Lane unit/config, không database và không paid provider.
$env:TEST_DATABASE_URL=''
uv run --locked pytest -q tests/test_session_reliability.py tests/test_ops_config.py tests/test_disposable_database_safety.py

# Lane PostgreSQL, chỉ sau khi harness cấp owned loopback *_test database.
# Không lấy giá trị DATABASE_URL/DATABASE_MIGRATION_URL từ .env hoặc cloud.
if (-not $env:TEST_DATABASE_URL) { throw 'Harness must supply an owned disposable loopback *_test target' }
uv run --locked pytest -q tests/test_auth_flows.py tests/test_chat_persistence.py tests/test_data_lifecycle.py tests/test_journal_indexing.py tests/test_proactive_executor.py tests/test_maps_jobs.py
```

Migration workflow hiện chặn hosted target và dùng `NullPool` (`backend/alembic/env.py:68`); local fixture bootstrap không tự chứng minh migration/RLS/grants hosted đã đúng. Khi triển khai D06/D08, phải có migration test lane riêng với explicit disposable migration URL và review SQL/hash theo runbook hiện có, không chạy migration remote để “kiểm tra”. Load/signup/AI/restore commands và safety/budget gates được chốt tại [07](07-load-testing-and-benchmark-plan.md) và [10](10-release-readiness-gates.md).

Release chỉ nhận khi có inventory cloud D01, budget đầy đủ D02, số đo D03–D05, privacy D08 và recovery D10. Nếu một số SHOULD chưa làm, ghi lý do, owner và risk accepted trong roadmap; không đánh dấu “scale-ready” chỉ từ pool math hoặc `ai_global_concurrency=50` (`backend/app/core/config.py:99`). Capacity AI còn chịu durable admission/reservation và financial budget; tách lane đo DB với fake provider khỏi lane kiểm 50 lượt thật được admission, đối chiếu [02](02-capacity-and-bottleneck-analysis.md) trước khi chọn ngân sách. Nới pool không mở được admission đang đóng vì budget.
