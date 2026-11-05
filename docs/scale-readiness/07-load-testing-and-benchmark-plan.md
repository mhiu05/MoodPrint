# Kế hoạch load test và benchmark

> **Implementation, 2026-11-05:** Yêu cầu hiện hành cho phép local engineering và read-only cloud. Target AI toàn ứng dụng **$50/ngày**, chưa kích hoạt production; campaign staging tối đa **$3 tổng cộng**, chỉ `gpt-6-luna` generation, không judge API. D03/D05/D10/D12 đã được chấp thuận. Mỗi production mutation cần approval riêng. Các đoạn audit-only/$20/$5 bên dưới là baseline lịch sử. [Tiến độ](12-implementation-progress.md), [cloud](13-cloud-inventory-redacted.md), [approval proposals](14-owner-decisions-required.md), [kết quả](15-test-results.md) là nguồn cập nhật; release vẫn **NO-GO**.

**Trạng thái: CHƯA CHẠY T1–T8.** Mục tiêu 50 active turns liên tục 15 phút là yêu cầu xác minh, không phải kết quả. [Capacity](02-capacity-and-bottleneck-analysis.md), [AI plan](05-ai-50-concurrent-chat-plan.md), [gates](10-release-readiness-gates.md).

## Kiểm kê công cụ đã có

| Công cụ, bằng chứng | Có thể tái sử dụng | Giới hạn phải giữ rõ |
|---|---|---|
| `scripts/load_chat_memory.py:43`, `:773` | 2–50 synthetic users, fake SDK/model, real local PG, SSE/privacy/cancel/revoke/crash; output JSON | Default workers 2, phải truyền 1; pool fixture 5+5 (`backend/tests/chat_load_server.py:160`), phải override 4+1 để mô phỏng Compose; all-features-off/budget mặc định 0, không chứng minh cap 20 hay workflow multi/proactive; một run hữu hạn, chưa soak 15 phút |
| `scripts/load_proactive.py:1`, `:69`, `:222` | Worker process riêng, lịch synthetic, fake model, pool/RSS/DB sampling | Drop/reset schema local; không dùng chung DB đang chạy; không duration CLI; không thay cho provider quota test |
| `scripts/load_session_startup.py:1`, `:39`, `:88` | Pool acquisition +SELECT 1 local, users/requests CLI | Hard code 5+2, không phải query session endpoint thật, không benchmark auth/signup |
| `scripts/provision_auth_test_accounts.py:1`, `:18`, `:30`, `:43` | Tham khảo input validation/không log credential | Hai account admin-confirmed của project cố định; ghi.env. **Không dùng để tạo 100/1000 hoặc chứng minh SMTP/confirmation**; không chạy trong audit |
| `backend/evals/concurrency_live.py:1`, `:40`, `:110` | Live latency probe có consent, synthetic actors, cost usage | Capped 12, không production network/Caddy, Settings không tái hiện cap 20. Không gỡ cap để giả benchmark 50 |
| `backend/tests/performance/benchmark.py:35`, `:48` | Synthetic 100/1000/10000, query ranking | Reset DB; chỉ ranking/matching. Module còn code dù target feature có thể bị ẩn, phải inventory router trước khi dùng |
| `scripts/load_social_mood.py:629` | Endpoint social/mood mixed synthetic users, percentile/pool/integrity | 2–50 users; không signup 100/1000 Auth |
| `scripts/load_guest_experience.py:216` | Guest 50, crash/recovery synthetic | Cần approval riêng nếu đổi sang hosted/paid; guests không chứng minh 50 registered |
| `.github/workflows/verify.yml:50` | Disposable PG/migrations, worker 1 users 10, fake fullstack | CI workflow tồn tại không chứng minh run HEAD đã xanh; không có 15 phút real 50 benchmark |

## Quy tắc an toàn và môi trường

1. **L0:** local disposable PostgreSQL có ownership marker từ `scripts/disposable_postgres.py`; fake Auth/SMTP/model, egress deny. Không load `.env` người dùng. Script cũ có reset nên chạy tuần tự trên DB riêng, không trùng port.
2. **L1:** staging target-size t3.large +Supabase project riêng/được owner cho phép; synthetic non PII; traffic đi qua HTTPS/Caddy; SMTP sink/local model. Không load production.
3. **L2:** staging real Auth/SES/OpenAI phải có approval rõ project/region/dataset/cost/run window, không gửi tới mailbox ngẫu nhiên. Paid T5 cần run cap riêng≤$5 và app hard cap 20 nguyên vẹn; khi bound 15 phút vượt $5, **không chạy đủ profile**, owner phải quyết định budget test riêng mà không đổi production policy.
4. Record cả resolved non secret settings và image SHA/resource/pool config; không `docker compose config` xuất toàn bộ env vào artifact. Run manifest chỉ chứa allowlist numeric/flags/model.
5. Test multi IP cần các nguồn mạng thật do owner kiểm soát (hoặc network namespaces/egress có routing phù hợp). Không giả bằng `X-Forwarded-For` từ client. Synthetic proxy trust tests riêng chỉ chứng minh parsing.
6. Credential của local DB được giữ file temporary hạn chế quyền. Không ghi DSN/password/cookie/email/prompt/provider key trong result JSON; mailbox mapping trong vault test có TTL.

### Lệnh hiện có, runnable sau khi chuẩn bị local toolchain

PowerShell, chạy từ repository root. Yêu cầu Docker chạy, Python backend 3.12 và dependencies đã cài. Không chạy những lệnh load dưới đây trong audit này.

```powershell
$scaleMeta = backend/.venv/Scripts/python.exe scripts/disposable_postgres.py --port 55439 | ConvertFrom-Json
$scaleEnvLine = Get-Content -LiteralPath $scaleMeta.environment_file | Where-Object { $_.StartsWith('TEST_DATABASE_URL=') }
$env:TEST_DATABASE_URL = $scaleEnvLine.Substring('TEST_DATABASE_URL='.Length)
$env:APP_ENV = 'test'
$env:DATABASE_URL = ''
$env:DATABASE_MIGRATION_URL = ''
$env:OPENAI_API_KEY = ''
$env:SUPABASE_URL = ''
$env:VOYAGE_API_KEY = ''
$env:MOODPRINT_LOAD_POOL_SIZE = '4'
$env:MOODPRINT_LOAD_POOL_OVERFLOW = '1'
backend/.venv/Scripts/python.exe scripts/load_chat_memory.py --workers 1 --users 50 --model-delay 2 --output docs/scale-readiness/results-T4-smoke.json
backend/.venv/Scripts/python.exe scripts/load_session_startup.py --database-url $env:TEST_DATABASE_URL --users 50 --requests 1000
backend/.venv/Scripts/python.exe scripts/load_proactive.py --users 1000 --chat 50 --turns 3 --concurrency 2 --worker-pool 2 --model-delay 2
backend/.venv/Scripts/python.exe scripts/load_chat_memory.py --workers 1 --users 50 --crash-kill --crash-timeout 120 --output docs/scale-readiness/results-T8-local.json
backend/.venv/Scripts/python.exe scripts/disposable_postgres.py --remove $scaleMeta.run_id
Remove-Item Env:TEST_DATABASE_URL -ErrorAction SilentlyContinue
```

Mỗi lệnh load reset phải chạy sau khi process trước đã thoát; các fixture output default không được ghi đè evidence cũ. Session probe 5+2 được gắn nhãn control riêng, không gộp vào số liệu Compose 4+1. Cleanup script chỉ xóa container đúng UUID/label/tmpfs (`scripts/disposable_postgres.py:102`), không drop DB theo wildcard. Giữ cleanup trong `try/finally` khi thực thi; lỗi cleanup phải chặn lần chạy tiếp. Nếu đang ở Linux dùng `backend/.venv/bin/python` tương ứng.

### Harness mới: giao diện bắt buộc, chưa tồn tại

P5-L01 sẽ tạo `scripts/scale_readiness.py` và fixture support. Các lệnh bên dưới là **specification để triển khai**, hiện chưa executable; không phải kết quả/lệnh đã chạy. Giao diện:

```text
python scripts/scale_readiness.py run --case T1..T8 --manifest <private-json> --output <new-json>
python scripts/scale_readiness.py cleanup --run-id <id> --manifest <private-json> --report <new-json>
```

Manifest chứa environment L0/L1/L2, expected host/project fingerprint, run ID, synthetic account list ref, users, duration, arrival profile, workflow mix, actual numeric settings, `max_cost_usd`, max email recipient, max calls/tokens, egress policy, allow paid/hosted approval ref. Secrets chỉ lấy từ runner environment/vault. Validate manifest, match target và require non-overwriting output trước mọi network/reset. Thiếu exact target hoặc cost bound →exit 2, không thực hiện. Cleanup chỉ tác động artifact/account/object/jobs trong run manifest có ownership marker, trả số còn lại; không xóa suppression list hay dữ liệu người dùng.

## T1 — 1000 registered records và tăng trưởng dữ liệu

- **Environment:** L0 đầu tiên, sau đó L1 với hosted approval; local synthetic Auth không chứng minh 1000 email confirmed thật.
- **Dataset:** 1000 unique users; mỗi user 2 sessions, 30 journal entries, 60 chat turns/tháng và 200 memory chunks giả lập, vector dimension bằng production config. Auth fixture local đủFK/claims; stage confirmed 1000 phải qua real Auth/mail ở test riêng được duyệt.
- **Isolation:** DB/run riêng, name space objects `scale/<runID>/`; không dùng provisioning script 2 accounts.
- **Exact future command:** `python scripts/scale_readiness.py run --case T1 --manifest <T1-private.json> --output <T1-new.json>`; manifest `users=1000`, snapshot data growth tại 0/30/90 ngày.
- **Expected:** count distinct user 1000, không trùng auth subject, session/consent/journal cáchly; record counts và bytes theo bảng/index/TOAST/vector/object.
- **Metrics/pass:** provisioning integrity 100%; sample 100 users read/session/journal 5xx 0; p95<500 ms/p99<1 s ở 10 RPS metadata; capacity headroom≥30% theo forecast 90 ngày; không thiếu RLS/retention.
- **Cost limit:** L0 $0 external; L1 $0 OpenAI, storage bytes≤1 GiB test fixture, không send mail nếu chưa duyệt. DB 1000 records không tính là 1000 verified Auth.
- **Cleanup:** future `cleanup --run-id <T1-ID> ...`; local destroy owned container; L1 xóa đúng 1000 test actors và objects theo manifest, kiểm FK/job/backlog hết; không bulk delete user thật. Rollback restore test dataset, không restore production.

## T2 — 100 signup/60 s, nhiều IP

- **Environment:** L0 fake Auth/SMTP cho contract; L2 real Supabase/SES staging sau owner approval.
- **Dataset:**100 valid distinct addresses trong domain/mailbox controlled, 100 passwords, age/captcha hợp lệ; 20 nguồn IP thật ×5 signup, arrivals uniform 60 s, thêm synchronized 1 sburst tách run.
- **Isolation/safety:** cap 100 initial +tối đa 20 resend theo cooldown; không bypass captcha/provider limits; abuse profile chạy riêng. Tài khoản already existing có testcase không nằm cohort 100 new.
- **Command (future):** `python scripts/scale_readiness.py run --case T2 --manifest <T2-multi-ip-private.json> --output <T2-new.json>`.
- **Expected:** timeline 100 accepted, 100 created, 100 email accepted, 100 delivered, 100 confirmed sau người/tự động test inbox xác nhận; trạng thái riêng biệt. Signup 200/202 đơn thuần không đủ PASS.
- **Metrics/pass:** request 100/60 s; p95 signup accepted≤3 s/p99≤5 s; unexpected 5xx 0; provider 429 phải count fail capacity; delivered≥99/100 trong 120 s, 100/100 trong 10 phút đối với mailbox controlled không suppressed; confirmed 100/100 trong 10 phút sau link issued, confirmation p95≤3 s. Đo login 100 trong 60 s và login 20 cùng 1 s sau confirm, p95≤2 s. Inbox classification ngoài hệ thống được báo cáo riêng.
- **Cost:** $0 AI; ≤120 recipient, SES run cap $1 (ước giá trước chạy); không retry vô hạn.
- **Cleanup/rollback:** cleanup manifest 100 test users+sessions/mail artifact; không xóa bounce monitoring; giữ redacted event counts. Nếu SMTP/rate limit lỗi, dừng run, khôi phục reviewed config trước đó, không tắt antiabuse.

## T3 — 100 signup/60 s cùng NAT

- **Environment/dataset:** giống T2, chỉ một IP egress thật; IP bucket sạch, không reset limiter giữa signup/confirm/login.
- **Command (future):** `python scripts/scale_readiness.py run --case T3 --manifest <T3-nat-private.json> --output <T3-new.json>`.
- **Expected baseline:** tối đa 40 provider attempt và ít nhất 60 local 429 từ shared 40/900 bucket (`backend/app/modules/auth/routes.py:227`); không khẳng định 40 account/email thành công. Đây là **FAIL business target**, PASS riêng cho việc bảo vệ limit.
- **Target:** owner chốt policy NAT có trusted source/CAPTCHA/email controls và capacity budget, rồi 100 unique legitimate hoàn thành như T2. Không tăng limit chung cho mọi endpoint để đạt số.
- **Metrics/pass:** log phân biệt local 429/provider 429, key scope và Retry-After; không enumeration. Final business gate 100/100 confirmed tương đương T2; negative abuse/captcha/cooldown vẫn bị chặn. Nếu owner giữ 40/900 thì requirement 100 NAT chưa đạt, ghi NO-GO cho requirement đó.
- **Cost/safety/cleanup:** như T2, max 120 recipients, $1, $0 AI; dừng ngay nếu policy không được duyệt, khôi phục config được review, xóa chỉ manifest cohort.

## T4 — 50 concurrent AI turns, mocked model

- **Environment:** L0 vàL1 qua Caddy/TLS, **workers 1/pool 4+1/budget 20/accounting true**; model hook fake nhưng ledger/locks/limits thật. Existing command phía trên chỉ smoke; future harness mới soak hợp lệ.
- **Dataset:**50 distinct registered users, 1 active parent/user; một cohort single-agent, một cohort orchestration/collaboration/groups, rồi mix 50%/30%/20%. Context 2 k/8 k/16 k token profiles và output 600 max (test envelope phải đồng bộ code); không tự đổi pricing policy.
- **Command (future):** `python scripts/scale_readiness.py run --case T4 --manifest <T4-fake-900s-private.json> --output <T4-new.json>`; duration 900 s, closed loop 50 không think time, admission barrier cho đợt đầu; fake first delta 500 ms/completion 5 s.
- **Expected:** trace chứng minh 50 parent inflight khi model barrier giữ 5 s; **actual provider active** bằng graph thực tế, không ép 50 nếu graph sequential. Root parent count/child count/SSE 50 đo riêng; child admission phải đủ sức chứa cho workflow được chốt.
- **Pass:**50/50 cohort admitted, unexpected reject=0 trong designed envelope; 15 phút SLO mock đạt, memory/queue bounded, integrity/privacy 100%, không pool timeout; budget liability≤20 tại mọi sample. Baseline $2 reservation dự kiến fail, đó là kết quả cần fix chứ không set budget 0.
- **Cost:** fake $0 external; synthetic ledger mô phỏng token charges, max liability 20. Cleanup cancel+reconcile all test runs, destroy owned DB; không reset giữa 15 phút, không dùng 50 lần script độc lập làm soak.

## T5 — 50 concurrent AI turns, provider thật

- **Environment:** L2 target EC2/Supabase, đúng model/project quotas đã xác nhận, owner approval trước. Không chạy `concurrency_live --levels 50`: CLI hiện tại từ chối trên 12.
- **Dataset:**50 registered test actors, synthetic prompts context percentiles như T4, max output/calls/envelope đã code enforce; single/multi cohorts riêng; provider requests không suy ra từ số tab.
- **Command (future):** `python scripts/scale_readiness.py run --case T5 --manifest <T5-live-approved-private.json> --output <T5-new.json>`; manifest approval ref, run spend cap≤$5, app cap 20, duration 900 s, max calls/tokens/requests và stop operator.
- **Expected/pass:**50 parent admitted đồng thời, giữ cohort closed loop 15 phút; actual provider active/requests/tokens/RPM/TPM có trace; p95 TTFT≤5 s/p99≤10 s; p95 completion≤30 s(single)/≤60 s(multi), p99≤deadline; unexpected errors<1%, provider 429<1%, zero OOM/pool timeout/duplicate bill; estimated vs actual reconciled within 5% hoặc nguyên nhân từng chênh lệch có explanation. Quota thực thấp hơn required→NO-GO, không retry làm che lỗi.
- **Cost stop:** bound launch liability+settled spend≤min(run remaining, app remaining); stop new admission ở 80%run cap, safety cancel ở 95%; residual charges đã có reservation. Không hứa chỉ theo dõi dashboard là hard cap. Nếu profile 15 phút không nằm $5, run không được admit; owner chốt test profile/cost theo [AI plan](05-ai-50-concurrent-chat-plan.md).
- **Cleanup/rollback:** stop generator, cancel authorized runs, wait bounded provider close, reconcile/unresolved reserve không release bừa; manifest cleanup users; rotate ephemeral test key; khôi phục same images/config, giữ unresolved liability cho đến resolution.

## T6 — AI + Auth hỗn hợp

- **Environment:** L0/L1 trước; L2 email/paid phải approval như T2/T5. Dataset 50 existing registered chatters +100 new signup/60 s +100 confirmation/login/recovery theo cooldown; tránh dùng 1 IP cho mọi load trừ sub case NAT.
- **Command (future):** `python scripts/scale_readiness.py run --case T6 --manifest <T6-mixed-private.json> --output <T6-new.json>`; duration 900 s, signup burst phút 3, confirmation phút 4, login phút 5.
- **Expected/pass:** giữ 50 active chat cohort, auth SLO như T2/T3, TTFT p95 regression≤20% so với T4/T5 equivalent, unexpected 5xx<1%, pool timeouts 0, critical path lock wait p95<100 ms. Đếm đúng created/delivered/confirmed, không coi auth bucket decline là success.
- **Metrics:** per route/status/error code percentiles, provider/delivery/DB pool wait, host resources. Cost local $0; option al L2≤$5 AI +$1 mail≤120 recipients; không cộng vào app budget ngoài quy trình.
- **Cleanup/rollback:** cleanup manifest gồm chat cohort và new users; stop auth generator trước đổi SMTP policy; restore config reviewed nếu fail, giữ mail audit counts.

## T7 — AI + proactive/embeddings/journal/guests/maps

- **Environment:** L0/L1, đầy đủ feature flags cần release; không tắt features để claim full scope. Dataset 50 registered chatters, 1000 due proactive schedules, 100 journal writes/min, 20 embedding jobs/min, 10 guest turns, 2 search jobs đồng thời là**profile đề xuất** phải được owner chốt theo usage.
- **Command hiện có:** load_proactive command ở trên là smoke giới hạn. **Future:** `python scripts/scale_readiness.py run --case T7 --manifest <T7-background-900s-private.json> --output <T7-new.json>`.
- **Expected:** guests/proactive không nuốt reserved interactive capacity/budget; background bounded, có skip/defer reason và lease; maps/Voyage được fake trừ quota approval riêng.
- **Pass:**50 registered parent admitted, TTFT p95 regression≤20%, proactive p95 due-lag≤5 phút lúc peak và drain backlog≤10 phút sau giảm tải; DB connections total trong budget, ledger≤20; không double claim/duplicate action hoặc journal read privacy violation. Nếu 50 parent+child không vừa global run policy thì fail capacity, không nâng cap mù.
- **Metrics:** per origin admitted/model calls/queue age/latency/spend, DB workers/api/maintenance connections. Cost mock $0, optional real≤$5 tổng tất cả providers và email 0; nếu provider pricing unknown fail closed.
- **Cleanup:** disable only test run schedules, cancel test jobs, wait lease/reconcile, xóa test objects theo manifest, không disable production cleanup. Rollback worker flags theo snapshot sau owner approve.

## T8 — stress, soak, disconnect, restart, recovery

- **Environment:** local/target-size staging riêng, không production. Dataset 50 cohort; burst 75 rồi 100 đểđo graceful overload; slow reader 10, disconnect 10, reconnect replay 10, duplicate idempotency key, process SIGTERM/SIGKILL tại phases reserve/provider/persist.
- **Commands:** existing crash command ở trên; **future:** `python scripts/scale_readiness.py run --case T8 --manifest <T8-recovery-private.json> --output <T8-new.json>`; 900 s required 50 cohort, thêm 7200 s mock soak, chaoschỉ owned process.
- **Expected/pass:** designed overload 429/503 có retryhint, không 500/queue unbounded; no duplicate provider call/charge dưới retry/replay; stream slots return baseline≤30 s sau terminal, durable interrupted/reconcile đúng lease; RSS plateau<10%growth sau warmup trong 2 h, OOM 0; migration compatible image rollback đạt RTO≤180 s có maintenance. No claim zero-downtime khi SSE bị đóng.
- **Metrics:** TTFT/network first byte vs first meaningful token, per workflow completion/p99/max, stream close/replay events, reserve/settled/unresolved, readiness/recovery time, credit slope và estimated 24 h cost.
- **Cost:** fake $0; real fault injection bị cấm trừ approval riêng≤$2 và token bound. Cleanup stop only owned processes, release confirmed completed resources, retain unknown liabilities, destroy owned container; rollback previous digest/env trên staging, không downgrade DB vô điều kiện.

## Metrics contract và SLO

Tất cả là ngưỡng đề xuất, chưa SLA/cam kết. Nhóm errors gồm HTTP status +domain code, capacity 429/503 vẫn đếm là capacity failure của cohort legitimate; overload negative profile có denominator riêng.

| Đo | Phương pháp | Gate đề xuất |
|---|---|---|
| RPS/throughput | arrivals, accepted, completed mỗi 60 s, cùng run ID/window | T2/T3 đạt 100 valid signups/60 s và 100 confirmed cuối window |
| p50/p95/p99 | histogram/raw duration, sample count và cohort; không average percentiles | Metadata p95<500 ms/p99<1 s; signup p95≤3 s/p99≤5 s |
| Provider TTFT | thời điểm provider dispatch đến token đầu trong SDK; không dùng heartbeat/progress làm token | Mock p95≤2 s; real p95≤5 s, p99≤10 s |
| Client first content | đo riêng POST→progress và POST→final đã validate; code hiện không gửi raw token delta cho client | Progress mục tiêu≤2 s; first meaningful content theo completion SLO. Token streaming tới client cần quyết định product/privacy riêng, không thuộc tối ưu capacity mặc định |
| Completion | client terminal event; single/multi/failed/timeout riêng | Real p95≤30 s/60 s, p99≤configured deadline; timeout không loại khỏi denominator |
| Inflight | parent turn gauge, all running ledger rows, actual provider start/end, total calls/turn | T4: 50 parent+50 SSE simultaneous; multi đo graph actual, không dùng tabs làm proxy |
| CPU/RAM | host CloudWatch +cgroup 1 s/RSS/loop lag; credits 5 min | 0 OOM/unplanned restart, host RAM<80%, steady working RSS<70%limit; [EC2 gates](06-ec2-t3-large-deployment-plan.md) |
| DB | pg_stat_activity(role/process), pool checkout waits, locks/idle-in-tx, query plans | steady 8/overlap 16 theo Compose; tổng+reserve≤actual role/DB/pooler; timeout 0; waits p95<100 ms/p99<500 ms |
| SSE | open/closed reason/reconnect/replay dedupe/slow reader queue | 50 simultaneous, leak 0, reconnect không bill lại |
| Provider | rate-limit headers, 429/RPM/TPM per model/project, retries | required headroom 30%, không retry vô hạn |
| Email | app/Auth/SES accepted/delivery/confirm timeline | T2/T3 exact counts 100; controlled inbox 99%≤120 s, 100%≤10 phút |
| Cost | reservation liability, estimated settled, actual provider invoice usage | app cap≤20, run cap như case; unresolved giữ reserve, không tự đánh PASS actual khi usage chưa có |

## P5 tasks

### P5-L01 — MUST FIX / P1: harness đủ T1–T8

**Problem/evidence:** scripts có scope khác nhau, fixtures overrides và thiếu duration/multi IP/SES lifecycle, đã nêu trong inventory. **Root:** công cụ smoke/eval không phải capacity harness. **Owner:** CODEX. **Files mới:** `scripts/scale_readiness.py`, `backend/tests/test_scale_readiness_safety.py`, `backend/tests/scale_readiness_server.py`; sửa `scripts/load_chat_memory.py`, `scripts/load_proactive.py` nếu tái sử dụng primitives. **Dependencies:** P0 facts, Auth/DB/AI task acceptance; metric contract P4-E03.

- [ ] Test manifest wrong target/hosted without approval/paid without cap/refused overwrite/cleanup ownership →exit 2, zero external calls.
- [ ] Implement CLI/interfaces ở trên, 1000 seed markers, trusted real IP drivers, fake Auth/SMTP/provider barriers.
- [ ] Add case 50 single/multi with budget 20 +production equivalent pool/resource; measured 50 must hold barrier trước phát response.
- [ ] Capture all metrics contract và raw redacted trace; expected rejection không ẩn errors.
- [ ] Test cost stop trước dispatch, unresolved reservation retained, cleanup đúng manifest, lỗi giữa chừng vẫn cleanup safe.
- **Acceptance:** mọi test case có dry run L0, reject unsafe manifests; 15000+samples hoặc báo cáo sample count thật; no secret detection hits. Command `cd backend` rồi `uv run pytest tests/test_scale_readiness_safety.py -q` sau khi file được tạo.
- **Complexity:** L, 3–5 ngày. **Risk:** harness khác topology/gây false PASS. **Rollback:** giữ script cũ, xóa chỉ harness artifacts/run owned resources. **Cost:** local $0 external; staging/provider do HUMAN approve.

### P5-L02 — MUST FIX / P1: rehearsal và bộ evidence release

**Problem:** chưa benchmark đúng HEAD/target cloud. **Owner:** HUMAN (approve/run L2), CODEX (L0/L1 analysis). **Files:** outputs mới dưới `docs/scale-readiness/evidence/<runID>/` sau khi scrub, `10-release-readiness-gates.md`. **Dependencies:** P5-L01, P0-H tasks, P1/P2/P3/P4 must fix.

- [ ] Chạy L0 đủ T1–T8; chốt ngưỡng trước nhìn kết quả.
- [ ] Chạy L1 đúng limits, so baseline after từng phase; thiếu metric giữ UNKNOWN.
- [ ] Owner approve L2 T2/T3/T5, record cost/target/stop; chạy distributed và NAT riêng.
- [ ] Reconcile actual cost/mail counts, verify cleanup, operator review NO-GO items.
- **Acceptance:** gate checklist có timestamp/SHA/dataset/config/scenario/raw counts, all must fix closed; một PASS synthetic không được nâng thành production PASS. **Complexity:** M, 1–3 ngày +quota wait. **Risk:** real provider jitter; rerun với cùng profile, không cherry-pick run. **Rollback:** dừng test, giữ hold, previous reviewed config; không deploy trong audit. **Cost:** cap theo case, owner review tổng các run.
