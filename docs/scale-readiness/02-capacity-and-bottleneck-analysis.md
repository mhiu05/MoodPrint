# Capacity, SLO và bottleneck analysis

> **Implementation, 2026-11-05:** Yêu cầu hiện hành cho phép local engineering và read-only cloud. Target AI toàn ứng dụng **$50/ngày**, chưa kích hoạt production; campaign staging tối đa **$3 tổng cộng**, chỉ `gpt-6-luna` generation, không judge API. D03/D05/D10/D12 đã được chấp thuận. Mỗi production mutation cần approval riêng. Các đoạn audit-only/$20/$5 bên dưới là baseline lịch sử. [Tiến độ](12-implementation-progress.md), [cloud](13-cloud-inventory-redacted.md), [approval proposals](14-owner-decisions-required.md), [kết quả](15-test-results.md) là nguồn cập nhật; release vẫn **NO-GO**.

Các giá trị dưới đây là **mô hình nhu cầu**, chưa benchmark. Baseline và evidence ở [01](01-current-codebase-audit.md); số đo cần thu ở [07](07-load-testing-and-benchmark-plan.md). Giữ Supabase Pro/SES/t3.large/React/FastAPI/Agents SDK/Postgres/Compose; không thêm Redis/Kubernetes/ECS/SQS/máy thứ hai để đạt giả định.

## Ba workload độc lập

| Workload | Định nghĩa và SLO đề xuất | Không được nhầm |
|---|---|---|
| A registered 1000 | 1000 distinct Auth identity đã confirm, app provision đúng; dữ liệu và session tồn tại, ownership đúng; 10 RPS metadata, p95≤500 ms/p99≤1 s, 5xx<1% | Không phải 1000 online, không dùng admin auto-confirm để claim email flow |
| B signup 100/60 s | 100 valid unique emails trong 60 s; phân biệt distributed IPs/NAT. Accepted p95≤3 s/p99≤5 s; 100 created, 100 SES accepted, ≥99 delivered≤120 s, 100 delivered/confirmed≤10 phút trên controlled mailboxes | Accepted notice không chứng minh created/delivered; delivery đến mail server không bảo đảm inbox |
| C AI 50 | 50 registered parents đồng thời, 50 SSE, cohorts single/multi, 15 phút closed loop; provider TTFT p95≤5 s/p99≤10 s, single completion p95≤30 s/multi≤60 s, p99≤deadline; errors<1% | Tab≠turn≠ledger row≠provider HTTP call. Client hiện nhận validated final, không raw tokens |

Confirmation/resend/login có cohort burst riêng sau signup, không reset IP bucket. SLO là proposal cần owner chốt. Success denominator gồm legitimate requests gặp 429/503 budget/quota; negative abuse cases có denominator riêng. Provider TTFT đo bên provider, client progress≤2 s mục tiêu UI; client meaningful content hiện bằng final completion. Nếu yêu cầu raw token TTFT tới client phải có task product/privacy review riêng.

## Scenario best / expected / worst

Đây là scenario giả định có công thức để thay bằng trace thực, không phải dự đoán chính xác.

| Scenario | DB/Auth/email | AI/service pattern | Kết luận có điều kiện |
|---|---|---|---|
| Best | Same/near-region RTT≤10 ms, compute đủ headroom, custom SMTP production SES≥5 recipient/s, auth quotas đủ; bounded queries | Single call, 2 k input/600 output, 30 s mean, 50 parents; cold reserve đã fix và provider quota đủ | Single EC2 là ứng viên hợp lý; hiện $2 reserve vẫn là blocker |
| Expected | RTT 20–50 ms, api 4+1/pool role đủ, 100 signup kèm confirm/login; journal/media tăng | 8 k input/600 output/call, 2 calls/turn, 30 s mean; proactive/embeddings có shares | DB polling/lock và quota TPM có thể đứng trước CPU; phải T6/T7 |
| Worst | Far-region RTT 100 ms, role 10/pooler server 15, SMTP sandbox/shared IP buckets | Context 16 k/call, 3 calls 30 s; V3/group fanout, guest/journal jobs; CPU credit thấp | Không đạt 50/100 NAT bằng current config; scale EC2 không giải quyết policy/quota/reserve |

## AS-IS/TO-BE theo thành phần

Cost impact chỉ ước lượng xu hướng nếu chưa có region/usage; mọi thay đổi cần task/owner ở [08](08-implementation-roadmap.md).

| Thành phần | Current configuration | Required configuration / recommendation | Evidence | Bottleneck/severity | Cost impact | Owner action |
|---|---|---|---|---|---|---|
| Supabase Pro/compute | Pro đã mua theo người dùng; SKU/region UNKNOWN | Ghi SKU, CPU/RAM/disk/IOPS/limits; chỉ resize khi CPU/IO/query trace chứng minh | H-S01, [Supabase compute](https://supabase.com/docs/guides/platform/compute-and-disk) | Compute/RTT UNKNOWN; P0 gate | Resize/PITR/storage có thể tăng bill | HUMAN lấy facts |
| Auth | Shared IP 40/900, login email 10/900, email action 3/h | NAT legitimate 100/60 s bằng reviewed risk policy, vẫn antiabuse | `backend/app/modules/auth/routes.py:227` | NAT hard policy P0 | Abuse cost nếu nới limit; không fixed infra | CODEX P1-A02, HUMAN policy |
| SES/custom SMTP | No cloud proof | Production access, verified sender, quota Auth+SES đủ 100/60 s+resend; proposed≥5/s, ≥3000/24 h | `provider.py:144`; [SES quotas](https://docs.aws.amazon.com/ses/latest/dg/manage-sending-quotas.html) | Sandbox/rate/delivery UNKNOWN P0 | Per recipient/eventing | HUMAN H-M01…06 |
| DB connections | Compose 4+1/2/1; core 5+2; role 20 assumption | Budget all processes+overlap+reserve, actual role/pooler≥requirement | `deploy/compose.staging.yml:10`; `budget.py:43` | Budget drift P1 | Pool enlargement không miễn phí server RAM; có thể compute | CODEX P2-D02/HUMAN H-S06 |
| Query/polling | Persistent SSE 4 Hz +policy 2 Hz | Đo queries/checkout time/locks, giảm repeated work giữ revoke | `chat_routes.py:806`; `runtime.py:828` |≈300 vòng DB/s INFERRED P1 | CPU/IOPS/network | CODEX P2-D03 |
| AI admission | DB global count +local runtime; local global 10 | Parent/provider separate semantics, reserve bounded, cap 20 giữ | `persistence.py:423`; `runtime.py:142`; `backend/.env:67` | Policy/reservation P0/P1 | Không tự tăng daily budget | CODEX P3-I01/I02/I03 |
| Provider | RPM/TPM UNKNOWN, V3≤7/group≤10 total calls | Actual model quotas≥demand+30%, bounded dispatch/backoff | `orchestration/workflow.py:72`; `groups/turn.py:372` | Provider throttle P0 gate | Paid tokens/provider plan | HUMAN P3-I09 |
| API process | One Uvicorn; 768 MiB/1.5 CPU | Giữ one process; thử 1536 MiB +resources balanced theo RSS | `backend/app/__main__.py:15`; Compose`:19` | RSS/loop lag chưa đo P1 | Same host, staging usage | CODEX P4-E01 |
| EC2 t3.large | Target 2 vCPU 8 GiB; actual credit/usage UNKNOWN | CPU/RSS/headroom+credit projection trước resize | Compose CPU total 3; [AWS credits](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/burstable-credits-baseline-concepts.html) | Credits/sustained CPU P1 | Unlimited surplus/EBS/IPv4 | HUMAN H-E01…03 |
| SSE/deploy | Caddy flush-1; server grace 45 s/container 150 s | Measured network TTFT, drain/replay/cancel/recovery | `deploy/Caddyfile:20`; `backend/app/__main__.py:18` | Disconnect đơn thuần không cancel model P1 | Reconnect traffic/possible paid residual | CODEX P3-I05/P4-E02 |
| Backups/monitoring | Templates; installed/restore UNKNOWN | Metrics gates+alarm test+DB&Storage restore | `cloudwatch-alarms.json:3`; H-S08 | Release/recovery P0 gate | Logs/custom metrics/PITR/backups | CODEX P4-E03/HUMAN |

Các path rút gọn ở bảng theo prefix đầy mục khác: AI dưới`backend/app/ai/`, auth provider dưới`backend/app/modules/auth/`, budget dưới`backend/app/infrastructure/database/`, cloudwatch dưới`deploy/aws/`.

## Connection budget

```text
local_app_connections = sum(process_instances * (pool_size + max_overflow))
required_role_budget = local_app_connections + admin_or_migration_same_role + emergency_reserve
```

| Process/topology | Steady | API overlap only | All process overlap |
|---|---:|---:|---:|
| API 4+1 |5|10|10|
| Proactive 2+0 |2|2|4|
| Maps 1+0 |1|1|2|
| In-API embedding/retention/guest/journal |0 additional pool|0|0|
| Total app |8|13|16|
| Admin/maintenance reserve, proposal |4|4|4|
| Required |12|17|20|

4 reserve là phần dư không tiêu hết cho app, không kết luận admin luôn dùng runtime role. Migration owner connection cần count riêng vào DB server budget. Nếu additional worker có engine riêng thì phải cộng; internal async jobs dùng chung API pool nên không cộng trùng. All overlap là biên bảo thủ, Compose hiện recreate không cam kết blue/green. Role 20 và Supavisor capacity là hai điều kiện riêng. Session pool giữ server connection theo client; transaction pool tách client/server budget nhưng vẫn phải giới hạn server theo actual role/Pg Bouncer/Supavisor settings. Không áp dụng công thức client=server máy móc cho transaction mode. [DB plan](04-database-and-connection-pooling-plan.md).

Áp dụng Little's Law cho API pool 5: nếu 300 vòng transaction/s, checkout trung bình 10 ms→3 active connections; 30 ms→9; 50 ms→15. Đây là lý thuyết không tính burst/locks/query nhiều vòng. Không suy ra 5 connections đủ hoặc phải tăng 15; đo actual duration rồi giảm RTT/query frequency/lock hold trước. Admission lock chung có thể serialize signup/AI budget? Signup khóa theo user khác, không đồng nhất với budget lock; không kết luận cả app chung global lock.

## AI demand và quota

Gọi`C=50`parents inflight,`L`thời gian mean/turn giây,`k`calls/turn mean,`I/O`tokens/call. Closedloop không think time:

```text
turns_per_minute = C*60/L
model_RPM = turns_per_minute*k + background_model_RPM
token_demand_per_minute ~= turns_per_minute*k*(I+O) + background_tokens
```

TPM thực tế có thể account theo reserved max output/provider estimator và model-specific token classes; công thức là planning lower-bound, theo console/headers mới chốt quota.

| L, k, I, O giả định | Turns/min | Model RPM | Token/min planning |15 phút model calls |
|---|---:|---:|---:|---:|
|30 s, 1, 2000, 600 |100|100|260000|1500|
|30 s, 2, 8000, 600 |100|200|1720000|3000|
|30 s, 3, 16000, 600 |100|300|4980000|4500|
|10 s, 1, 2000, 600 |300|300|780000|4500|

Nhanh hơn tạo RPM cao hơn, không phải ít quota hơn.50 provider request song song không thể suy ra từ RPM đơn lẻ; cần provider latency/call phases. V3 hai children có thể song song trong một parent, groups speakers phần lớn tuần tự. Nếu tổng capacity được policy đếm ledger rows 50 thì 50 parents +children/background không còn headroom; task P3-I03 tách semantics rõ và không đơn thuần nâng 50→100.

## AI cost và cap 20

Standard short context gpt-6-luna công bố input $0.10/output $0.50/1 M, cached input $0.01. [Official pricing](https://developers.openai.com/api/docs/pricing), [model](https://developers.openai.com/api/docs/models/gpt-6-luna), chi tiết multipliers/capped rate sở [05](05-ai-50-concurrent-chat-plan.md). Không cache hit, không tool fees giả định:

```text
cost_turn = sum((input_uncached*0.10 + cached_input*0.01 + output*0.50)/1e6 for each call)
cost_total = turns*cost_turn + embeddings + voice + search + background + pricing_multipliers
```

| Usage case | Cost/turn lý thuyết |1000 users×1 turn |×10 turn |×60 turn |50 concurrent, 30 s mean, 15 phút |
|---|---:|---:|---:|---:|---:|
|2 k/600, 1 call |$0.0005|$0.50|$5|$30|1500 turns=$0.75|
|8 k/600, 2 calls |$0.0022|$2.20|$22|$132|$3.30|
|16 k/600, 3 calls |$0.0057|$5.70|$57|$342|$8.55|

Số turn lý thuyết dưới $20 lần lượt 40000/9090/3508; không phải số admission hiện tại. Giá settle thận trọng trong code 550/550/1650 nano/token làm ví dụ 8 k/600×2 call thành $0.01078/turn, 1500 turns≈$16.17; giữ multipliers để bảo vệ cap. Báo cáo billing standard khác conservative liability, không coi liability là actual invoice.

**Nghẽn trước cả tokens:** hiện`RUN_RESERVATION_NANO=2e9`và ceiling≤20 e 9; lúc empty budget chỉ 10 registered rows chưa settle.50 parent requires $100 pending reserve, chưa child. Muốn 50 dưới remaining $20 thì mean maximum reservation≤$0.40/parent bao child liability; nếu đã spent 10 thì≤$0.20. Cần bound**từng turn**được cưỡng chế và tổng sum reservation≤remaining; average cost không phải hard bound. Không hạ reserve theo average hoặc đổi app cap 20. Context truncate/max output/call limits có thể ảnh hưởng product, HUMAN phải chốt bound; không chứng minh được thì requirement 50 dưới 20 chưa khả thi.

App reserve/settle atomic đã có. Capped budget liability lấy to day/yesterday UTC và open/uncertain carryover (`backend/app/ai/accounting.py:27`); không reset assumption 00:00 Bangkok. Quota user theo app day khác; model spend không bao đảm bao gồm Voyage/STT/maps ngoài ledger. Cần scope explicit, không đổi pricing policy.

## Data growth của 1000 users

| Dữ liệu | Assumption minh họa | Growth | Cần đo |
|---|---|---|---|
| Auth/app users |1000 identities, 2 sessions/user |1000 users +2000 sessions ban đầu | auth/provider storage+indexes và session retention |
| Journal text |1 entry/user/day, 2 KiB payload |30000 entries/tháng≈58.6 MiB raw | row/index/TOAST/RLS/query cost, retention |
| Chat |10 turn/user/day, 2 messages/turn, 2 KiB/message |600000 messages/tháng≈1.14 GiBraw | actual retention text/events, DB overhead |
| Memory vectors |200 chunks/user, 256..1024 float 32 dimension |200000 vectors≈195..781 MiB raw | vector index+text overhead/HNSW/IVFFlat config |
| Media |1×2 MiB image/user/day |≈58.6 GiB/tháng | object storage/egress, uploads/day/cleanup/private ACL |

Số raw không cộng tự động thành disk bill: retention/compression/schema index và actual profile quyết định.10 turn/day ở case daily cost expected đã vượt 20; usage profile phải phù hợp business budget. Repo image 10 MiB/audio 20 MiB/video 50 MiB là perfile cap (`backend/app/modules/journal/storage.py:20`), không phải quota tháng. [Supabase billing](https://supabase.com/docs/guides/platform/billing-on-supabase) cóMAU/disk/Storage included riêng; 1000 registered không đồng nghĩa 1000 MAU hoặc compute đủ. [DB growth plan](04-database-and-connection-pooling-plan.md).

## Quyết định sizing

- **A single EC2 trước:** hợp lý khi TTFT/completion đạt, CPU<70%, RAM<80%, no OOM, loop lag p95<100 ms, pool wait p95<100 ms và credit slope 24 h được budget chấp nhận.
- **B nâng EC2:** chỉ khi profile đúng là CPU/RSS saturation sau query/polling đã tối ưu. Nâng Supabase compute khi có DB CPU/IO/connection wait trace; không tăng pool mù.
- **C thêm component:** chỉ khi HA/RTO hoặc process bottleneck không giải quyết bằng A/B; phải chia sẻ/fence ephemeral state, limiter, provider dispatch và cost ledger trước nhiều replica.
- Quota 429, SES sandbox, NAT limit, $2 reserve không được giải quyết bằng máy mạnh hơn. [EC2 decision table](06-ec2-t3-large-deployment-plan.md), [open decisions](11-risks-and-open-decisions.md).
