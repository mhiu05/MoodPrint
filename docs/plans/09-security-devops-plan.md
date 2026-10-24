# 09 — Security, privacy, observability và vận hành

> **Kiến trúc đã chốt ngày 23/10/2026:** Python 3.12/FastAPI/Pydantic v2, SQLAlchemy 2 async + psycopg 3, Alembic/uv, Supabase PostgreSQL/Auth và OpenAI Agents SDK Python. Giữ React/Vite/TypeScript; Pydantic → OpenAPI → `frontend/src/api/generated/`. Chỉ scaffold cloud, không deploy. Evidence audit ban đầu là lịch sử, không phải trạng thái implementation mới.

**Security là điều kiện của từng slice, không phải phase cuối gắn thêm.** Các thiết kế ở đây chưa được triển khai hoặc kiểm trên cloud. Scope PoC mặc định là tài khoản và nội dung **tổng hợp**, trước khi đủ quyết định sản phẩm/eligibility/processor/staffing. Nguồn retention/quota đang được thuật lại trong [prompt nội bộ](../prompt.md), chưa có Privacy Spec/Charter gốc; Q01/Q02/Q05 phải chốt trước dữ liệu thật.

## Data boundaries và quyền truy cập

**Age assurance D15/Q04, người dùng chốt 24/10/2026:** năm sinh + xác nhận tự khai báo16 cho tính năng riêng,18 cho kết nối. Đây không phải xác minh giấy tờ. Backend dẫn xuất band theo clock Asia/Bangkok và kiểm ở ingress; chỉ lưu record owner-private/version/policy/timestamp. Năm tròn18 chưa có xác nhận18 vẫn teen. Không nhận client ageBand/userId, không dùng user_metadata, không auto consent; strict input/CSRF/idempotency/CAS chống sửa request/race. Sửa năm sinh đã lưu không có public update; lifecycle tài khoản/erasure vẫn được theo dõi riêng tại Q05.

| Dữ liệu/chủ thể      | Được truy cập                                                                                                             | Bị chặn                                                                                                    |
| -------------------- | ------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------- |
| User                 | Own private items/mood/memory/draft, own AI session còn TTL, published candidates có quyền, rooms live, reveal đúng grant | Private của người khác, peer identity trước grant, room đã mất quyền                                       |
| Model/bot            | Context được ContextBuilder chọn theo bot/purpose và tool allowlist; không có credential/DB role                          | Arbitrary SQL/URL/code, human chat, report evidence, private peer profile; model args không cấp actor/role |
| Matching service     | Published allowlist projection + live eligibility/consent/block/moderation restriction                                    | Mood/private/memory/AI/human transcripts, identity/gender và report content                                |
| Socket client        | Authenticated own notifications và IDs/version tối thiểu; text lấy qua API live                                           | Arbitrary room join/global broadcast/private text cached trong event                                       |
| Worker               | Job ID/type/resource refs/version theo service policy và lease/fence                                                      | Tự tạo consent/actor, raw prompt trong job payload, replay action sau revoke                               |
| Moderator            | Report/evidence được chọn trong case được phân công; role riêng/audit                                                     | Mọi private data chỉ vì có quyền moderator; dùng evidence cho AI/matching                                  |
| Operator/log/tracing | Metadata IDs/status/versions/usage/latency/error categories                                                               | Tokens/secrets/raw private content/SDK state/chain-of-thought                                              |

Private Profile, approved memory, mood, matching draft/published và reveal là các lớp dữ liệu riêng. Published source mapping chỉ chuyển tag user đã chọn, không chuyển nguyên private text. Một bảng hoặc một role dùng chung cho tất cả nội dung sẽ làm mất ranh giới mục đích; thiết kế repositories/DTOs/public service cụ thể theo [05](05-backend-data-realtime-plan.md).

## Consent/version enforcement và revocation

| Snapshot/gate                              | Khi nào kiểm / invalidation                                                                                                       |
| ------------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------- |
| authVersion/session expiry                 | Mỗi HTTP/socket ingress, SSE subscribe/replay, job actor reconstruction; logout/revoke invalidate session và clear caches         |
| eligibilityVersion/account status          | Mọi private/social feature theo policy; age band/kênh không lấy từ body/query                                                     |
| AI version                                 | Trước start/model request/tool/output/replay của AI                                                                               |
| MEM version + memory/source versions       | Khi lấy approved memory và trước tool/output phụ thuộc; MEM revoke hủy run đã dùng memory, không ảnh hưởng human matching độc lập |
| VOICE version cùng AI version              | Bắt đầu recording/upload/STT/get transcript/send text intent; revoke purge buffers/tracks                                         |
| MATCH version + published versions hai bên | Candidate response/invite/accept/read/send/reveal, queued event fetch                                                             |
| Pair/block/connection version              | Read/write/grant/notify/fetch; end/block terminal ngay                                                                            |
| data deletion gate/tombstones              | Trước mọi use/commit/recovery liên quan nguồn đã xóa; chặn worker cũ ghi lại                                                      |

**Version độc lập theo mục đích.** Không dùng một global version tăng khi tắt AI để vô hiệu human connection không liên quan. Có account row chung làm điểm lock nhưng mỗi operation chỉ so những fields phù hợp; deletion/account suspension là barrier rộng có lý do riêng.

Thu hồi theo transaction: check expected version→lock gate→increment relevant version/deny state/tombstone→outbox invalidation→commit. Đường access đọc live version từ DB hoặc cache có coherence đã kiểm; PoC ưu tiên DB, không cache quyền dài hạn. Worker cleanup, abort model, socket room eviction và client clearing chạy sau nhưng **không là điều kiện để deny**. In-flight bytes đã gửi không thu hồi tuyệt đối; không hứa xóa trí nhớ/screenshot của người nhận.

Bật lại chỉ là một consent event/version mới, không mở room/request/grant/run cũ. SDK guardrails/tool schema hoặc câu “tôi đồng ý” trong chat không thay xác nhận đúng payload cho memory/publish/invite/accept/reveal.

## Threat model tối thiểu và kiểm chứng

| Threat cụ thể                                          | Cổng kiểm soát                                                                                                                                       | Bằng chứng bắt buộc                                                                          |
| ------------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------- |
| User sửa local state/age/userId hoặc gọi API trực tiếp | Server actor/session+eligibility+ownership, body allowlist                                                                                           | T-AUTH-01/02, T-PRIV-01                                                                      |
| IDOR/tenant leak qua record ID hoặc candidate ref      | Scoped repository queries, opaque candidate ref scoped actor, response DTO allowlist                                                                 | Hai actor truy chéo IDs; unknown/foreign đều404, no hidden private payload                   |
| Prompt injection từ user/memory/tool result            | Context data không đổi instructions; tool allowlist/schema/live gateway; không SQL/URL/code từ model                                                 | Fake model cố tình gọi forbidden tool; real-model adversarial eval                           |
| LLM báo “đã lưu/đã mời” khi chưa làm                   | Proposal receipts và typed action states, model không có social write tools, output policy                                                           | Forged action/resource receipt bị reject; no-success-before-commit UI test                   |
| Duplicate/race/retry làm vượt quyền/quota              | Sorted locks, constraints, CAS, idempotency, fence, server clock                                                                                     | SQL barrier matrix ở08, cross requests/lostACK/claimcrash                                    |
| XSS từ generated text/card/links                       | Plain text hoặc sanitized markdown, link protocol allowlist, card route allowlist, CSP phù hợp build                                                 | Payload HTML/script/JS URL không chạy; private data không exfil qua image/link               |
| CSRF/cookie/session theft                              | HttpOnly Secure SameSite, cookie scope, CSRF+Origin checks, Supabase official getUser/verified token, app session expiry và live provider session_id | Origin invalid denied, logout/revoke shuts down SSE/socket; no tokens in browser storage/log |
| Replay grant/job/approval cũ                           | Payload+source+consent version bound, one-use, expiry, live recheck                                                                                  | T-MEM-02/03, T-REVEAL-02, T-JOB-01                                                           |
| Abuse/cost DoS/quota chia room                         | Body/range limits, rate/concurrency/budget reserve, per-account atomic quota                                                                         | T-AI-03, T-MSG-03, T-PERF-01; manual functions survive provider breaker                      |
| Logs/traces/error reporter thu text                    | Metadata allowlist, exporter disabled by default, canary network/log inspection                                                                      | T-OPS-01 cả success/error/retry/tool/approval paths                                          |
| Backup/restore hồi sinh dữ liệu hoặc consent           | Tombstone register và replay trước traffic, restore isolated, post-restore gate                                                                      | T-OPS-02/T-JOB-02; không “restore thành công” chỉ từ DB boot                                 |

Input validation/SQL parameterization ở server, authorization tại domain service và constraints tại DB phối hợp; không có một guardrail LLM thay tất cả. Supabase PostgreSQL runtime role tối thiểu, migration URL/role riêng; SQLAlchemy async/Alembic, DB/network private khi hạ tầng cho phép; không service-role/superuser credential vào tools/frontend. Domain tables không direct browser writes. Exposed schema RLS enabled; grants/policies theo owner/purpose và runtime role thực được test. Không user_metadata authorization/BYPASSRLS; Supabase Auth đã chốt, không secret/service_role key trong client/tools.

## Retention, xóa và provider gate

| Lớp                                                       | Baseline được thuật lại / đề xuất triển khai                                                                              | Cách chứng minh                                                                                                  |
| --------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------- |
| AI context/history/summary/proposals/raw SDK state/replay | Không lịch sử durable mặc định; hết session hoặc ≤24h từ interaction cuối; RAM cap/per-read expiry; không SQL/WAL/backups | Fake clock expiry, logout/end/restart mất raw content, canary inspect storage/network; define “hết phiên” Q05    |
| Approved memory/private confirmed items                   | Lưu đúng purpose/owner/bot/consent và user action; không tự đặt TTL vô hạn cho proposal; approved record lifecycle Q05    | Edit/delete/revoke/source invalidation; retrieval only active current versions                                   |
| Mood/human messages                                       | Tối đa 90 ngày theo prompt; deny access ngay khi quyền mất, dù physical retention còn                                     | Query filter TTL/server time + sweeper; purge/room-read tests                                                    |
| Audio STT                                                 | ≤30s capture; purge xong/hủy/lỗi và tối đa 15 phút, bao gồm temporary files/processor policy                              | Recorder cleanup + backend fake/real processor evidence; no audio tracing                                        |
| Explicit delete                                           | Chặn dùng ngay; active stores/processors trong 7 ngày; backup hết trong 30 ngày theo nguồn nội bộ                         | Tombstones, job progress và deadline alerts; processor confirmation/retention proof; backup expiry/restore drill |
| Logs/audit/usage/report evidence/export                   | Không có raw AI text mặc định; metadata TTL và evidence exception chưa chốt Q05/Q07; export download tạm/one-use          | Inventory schema, content canaries, access logging, expiry/deletion checks                                       |

Natural session expiry không xóa approved memory user đã xác nhận lưu độc lập; explicit source deletion phải áp dependency policy. Raw transcript không được giữ vì muốn “chứng minh memory”. Nếu evidence moderation cần retention khác, cần policy được duyệt riêng, không âm thầm kéo dài tất cả chat.

OpenAI phân biệt abuse monitoring và application state; nội dung API mặc định không dùng huấn luyện trừ opt-in, nhưng abuse monitoring mặc định có thể giữ tới 30 ngày, và controls như ZDR cần đủ điều kiện/phê duyệt. **`store:false` không đồng nghĩa zero retention.** Vì vậy tài khoản mặc định chưa chứng minh đáp ứng delete7ngày/TTL nội bộ; kiểm endpoint/model/cache/tracing/account/region/processor trước dùng nội dung thật. [Data controls](https://developers.openai.com/api/docs/guides/your-data).

Provider checklist ở gate Q02 là yêu cầu nghiên cứu của task này: endpoint/model/version, store/defaults, prompt cache, abuse/application state, trace/exporter, region/subprocessors, deletion API/confirmation, backup/ZDR eligibility và dữ liệu audio. Không coi tắt SDK traces là đã tắt mọi provider storage. Nếu chưa đáp ứng, giữ synthetic-only hoặc Hold feature; không tự nới privacy requirement.

## Observability không thu thập private content

SDK tracing bật mặc định trong đường server theo [official guide](https://developers.openai.com/api/docs/guides/agents/integrations-observability); implementation phải tắt exporter trước request đầu và test pinned SDK options. Default app observability là metadata: request/run/event IDs, bot/prompt/tool/model/schema versions, status, errorCode, latency, source/consent version numbers, token usage, cost estimate, queue/DB metrics. Opaque IDs vẫn là dữ liệu liên kết cần access/TTL, không gọi là anonymous chỉ vì không có tên.

Không log bodies/login passwords/Authorization/Cookie/Supabase tokens, prompts, replies, mood notes, memory text, tool args/results, identity, raw SDK state, selected evidence hoặc stack/message provider có text. Error adapter chỉ giữ error category/retryability/request ID; redaction theo allowlist tốt hơn regex “xóa các từ nhạy cảm”. Sentry/APM/HTTP access logger nếu thêm phải kiểm request/response capture, span events, network metadata và source-map access trước bật.

Metrics cần có: AI accept/complete/fail/cancel, queue delay, model-call/tool counts, latency/usage/cost, unknown usage reservations; matching query latency/eligible count/empty-rate; human commit→fetch latency/duplicates/reconnect/denied; pool saturation/lockwaits/deadlocks; job oldest age/lease expiry/retries/deletion deadline. Không dùng metric labels chứa user text/userId/candidateId high-cardinality hoặc private taxonomy choices.

Tracing debug nếu cần mở chỉ synthetic staging trước; inspect success/failure/tool/guardrail/approval/nested spans và exporter flush. Retention/access/sampling explicit; sampling không thay việc loại text. Không yêu cầu hoặc lưu chain-of-thought.

## Development, staging, production và secrets

| Môi trường           | Cấu hình/dữ liệu                                                                                    | Quyền                                                                          |
| -------------------- | --------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------ |
| Local/test           | Local PostgreSQL, test-only dependency override identity, fake SDK model/processor, synthetic seeds | Không production credentials; fixtures explicit                                |
| Staging PoC          | Chưa tạo/deploy; chỉ env templates và local synthetic rehearsal, hard caps/health/metrics           | Adult test identities; không tuyển người thật khi gates còn mở                 |
| Production/beta thật | Chỉ sau Go cụ thể, Q01–Q08 và operational proof                                                     | Secret manager/least privilege, reviewable release, report staffing và on-call |

Server env dự kiến: DATABASE_URL, DATABASE_MIGRATION_URL, SUPABASE_URL, SUPABASE_PUBLISHABLE_KEY, session/CSRF/allowed origins, OPENAI_API_KEY, explicit OPENAI_MODEL, SANDBOX_ENABLED=false, AI limits, feature flags, deletion/TTL config. Chỉ tên là ví dụ thiết kế; env schema và exact names được P00/P01 pin. Browser chỉ public API origin/mode, không secret trong VITE_* hoặc source map. `.env.example` baseline từng rỗng, implementation bổ sung tên biến/hướng dẫn, không secrets hoặc `.gitignore`. Không cần service-role key cho login/read verification; không persist password/provider tokens. App session TTL≤JWT expiry, login lại khi hết hạn.

Keys tách project/env, rotate khi lộ, ngừng key cũ theo runbook; không paste key vào CI logs/terminal artifacts. Database credentials trong secret manager, role phân quyền; pool shared, statement/lock timeout và connection budget; TLS ngoài localhost. CORS allowlist cụ thể; cookie same-site thiết kế cùng reverse proxy; socket Origin/auth checks không suy từ CORS HTTP đơn thuần.

## CI/CD, migrations, backup và rollback

Pipeline đề xuất: uv sync --locked + npm ci frontend→Ruff/mypy/Pydantic/OpenAPI drift/pytest + frontend typecheck/Vitest→ephemeral PostgreSQL+migrations+SQL permission/race tests→fullstack provider-stub E2E→build/container→secret/config checks→local container rehearsal→readiness/smoke→reviewable cloud skeleton chưa deploy. Real-model evals thành job opt-in theo budget, không chặn mọi edit bằng API trả tiền. Không dùng secrets/prod DB trong PR tests không tin cậy.

Alembic migrations chạy riêng, revision/version lock, migration role riêng; app readiness chỉ true khi compatible revision, DB và worker policy đã sẵn. Expand→migrate→contract; dry-run upgrade từ previous staging backup đã sanitize. App rollback không tự chạy destructive down migration. Các schema có source/version grants phải tương thích cả image trước trong rollout window.

Container dài hạn để PoC có stream/socket/worker; nếu chọn serverless phải thử timeout, flush/proxy buffering, connection duration, job lifecycle và DB pooling của nền tảng cụ thể, không khẳng định mọi serverless không hỗ trợ. Health live không gọi model; ready kiểm dependencies tối thiểu, có timeout và không lộ config.

Shutdown: ngừng nhận run/send mới, mark readiness false, drain HTTP/socket/SSE trong deadline, cancel AI còn dang dở hoặc mark interrupted, release/expire worker leases, flush metadata logs, await engine.dispose() và exit hữu hạn. Tests phải bao phủ cả **teardown**; audit hiện gặp suite assertions xong nhưng runner timeout. Không coi process luôn mở là health.

Backup schedule/retention phải phù hợp 30 ngày max cho deleted copies theo Q05; encrypt/access control và separate environment. Restore vào mạng cô lập→apply migration compatibility→replay deletion tombstones/consent invalidations từ registry không bị rollback theo snapshot→purge expired→verify no revoked grants→readiness. Nếu tombstones chưa có đủ hoặc processor delete không chứng minh, Hold phục vụ dữ liệu liên quan.

Rollback rehearsal: deploy image/prompt/config version trước, giữ schema tương thích, gates/tombstones hiện tại và committed domain data; cancel old AI runs để không mix prompt/tool policy versions; feature flags disable new social/AI work nhưng cho phép user quản lý/xóa dữ liệu. Không bật demo seed hoặc restore consent để “khôi phục trải nghiệm”.

## PoC/MVP và phần chỉ cần khi scale

| Cần ngay ở PoC/MVP                                                                                                                                                     | Chỉ nâng khi có evidence                                                                                                                              |
| ---------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------- |
| Một backend+DB quản lý+auth+model API; metadata jobs/outbox; bounded RAM TTL; TLS/session/policy; tests/concurrency; cost cap; backup/delete/restore; report readiness | Multi-instance shared TTL store/socket adapter/permission invalidation bus; dedicated worker; Redis/shared quota khi số đo cần; HA/advanced autoscale |
| Simple schema/index theo query, metrics/alerts tối thiểu và runbooks                                                                                                   | Data warehouse/feature store/vector DB/Kafka/Kubernetes; không cần chỉ vì có5 bot                                                                     |
| Manual fallback khi LLM/downstream lỗi, versioned prompts/models                                                                                                       | Multi-provider routing/specialist/planner/sandbox/computer use sau benchmark và policy riêng                                                          |

Release hold conditions cụ thể: ownership/consent race chưa đóng, context leakage, provider retention không đáp ứng, restore resurrect, voice cleanup không đạt khi voice mở, không có người xử lý report cho beta, kênh teen chưa được duyệt, quota/cost cap không hiệu lực. Phase 0/local synthetic vẫn tiếp tục khi những gate dữ liệu thật này đang mở. Quyết định và owner ở [10](10-decisions-and-open-questions.md).

## Docker sandbox có điều kiện và cloud skeleton

Chưa code/file execution use case trong 5 bot baseline: chỉ port/interface và `SANDBOX_ENABLED=false`, không container mọi run. Nếu dùng sau: backend authorize, Docker nonprivileged/non-root, read-only root, bounded temp disk/CPU/RAM/PIDs/wall-time, egress denied mặc định. Không host mounts tùy ý/secrets/DB credentials/Docker socket cho model; fixed image/commands allowlist; cleanup finally/watchdog. Model không tự launch Docker. Config presence không chứng minh isolation đã được test.

Chỉ Dockerfile/worker/local Compose/deploy examples/env templates/health/CI/runbooks; không cloud resources/account setup/public deploy/mua dịch vụ/remote migrations. Khi có Supabase config: xác minh project/URL/privileges/schema/Alembic history/diff read-only, trình bày changes rồi chỉ DDL/writes sau permission riêng; không drop/truncate tự động. Direct/session pooler ưu tiên; transaction mode `prepare_threshold=None`, no session state/LISTEN. `DATABASE_MIGRATION_URL` tách app URL, role runtime không DDL/BYPASSRLS. Local fake tests không chứng minh hosted backup/processor deletion PASS.
