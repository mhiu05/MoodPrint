# Rollout, credentials, validation và coverage

Tài liệu vận hành **cho phiên triển khai sau**, không phải bằng chứng đã deploy. Ngày tra source/docs:03/11/2026. Không có runtime secret, AWS account ID hay kết quả API/live trong bộ plan.

## Credential người vận hành cần chuẩn bị

| Biến | Khi cần | Cách chuẩn bị |
| --- | --- | --- |
| `OPENAI_API_KEY` | Web Search và chat | Dùng key backend đang có. Người vận hành tự kiểm project/model/tool access và billing trong OpenAI dashboard; không gửi key vào chat. Không tự thay `OPENAI_MODEL` chỉ để có search; model phải có pricing bound đã review. |
| `APIFY_API_TOKEN` | Apify Maps | Tạo token riêng cho MoodPrint ở Apify Console → API & Integrations; đặt tên theo môi trường và expiry. Dùng scoped token chạy đúng actor, xem/abort run, đọc và cleanup default storages do run tạo; kiểm restricted actor runtime access. Không cấp quyền sửa actor hay mọi dữ liệu account chỉ để tránh cấu hình scope. |
| `APIFY_MAPS_ACTOR_BUILD` | Maps production | Không phải secret; pin build/input/pricing đã đánh giá. Chưa có build đã review thì Maps unavailable, không mặc định trôi theo `latest`. |
| `GOOGLE_MAPS_API_KEY` | Chỉ nếu chọn adapter Google sau này | Chưa cần cho Apify. Tạo Google Cloud project/billing, enable Places API (New), tạo key riêng backend, restrict API và server egress IP phù hợp, set quotas/budget alerts. Không dùng browser key/referrer restriction thay server credential. |

Apify khuyến nghị authentication bằng `Authorization` header; không để token trong query URL/log. Scoped token cần quyền truy cập storage của run để lấy kết quả và dọn dữ liệu, không chỉ quyền run actor. [Apify API integration và scoped tokens](https://docs.apify.com/integrations/api). Google key cần project/billing/API đã bật và restrictions tương ứng. [Google Places setup](https://developers.google.com/maps/documentation/places/web-service/get-api-key).

Khi triển khai local, sau khi code Settings/adapter đã hỗ trợ biến mới, người vận hành mở `backend/.env` **trực tiếp trong editor của họ**, thêm `APIFY_API_TOKEN` với token thật tại đó, giữ OpenAI key hiện có và thêm các cờ non-secret đã chọn. Không điền credential vào `.env.example` hoặc `deploy/runtime.env.example`; examples chỉ có tên/giá trị trống. Không dùng lệnh shell chứa literal token, screenshot env, copy provider error body hay dán secret vào chat. Không tạo `VITE_*` chứa key. Restart backend/worker để Settings đọc lại; chỉ thêm env khi code chưa hỗ trợ sẽ không tự tạo chức năng.

Dùng password manager/secret manager của môi trường; token theo từng môi trường, rotate/revoke ở provider khi nghi lộ, sau đó cập nhật runtime/recreate process. Không báo “provider sẵn sàng” chỉ vì biến có giá trị; availability còn phụ thuộc pricing, flags, eligibility và worker.

## AWS staging — giữ cùng SecureString, không mở IAM theo suy đoán

Đã đọc [README AWS](../../../deploy/aws/README.md), [instance policy](../../../deploy/aws/instance-policy.json), [deploy.sh](../../../deploy/aws/deploy.sh), [runtime example](../../../deploy/runtime.env.example), [Compose staging](../../../deploy/compose.staging.yml).

Repo mô tả runtime là SecureString **`/moodprint/staging/runtime`**, nội dung là env backend. Policy mẫu instance chỉ `ssm:GetParameter` trên đúng ARN parameter này. `deploy.sh` dùng `--with-decryption` ghi file `/run/moodprint/runtime.env.*` mode0600, không print secret; API/proactive nhận file qua `API_ENV_FILE`. Không có thao tác AWS nào đã chạy để kiểm policy attached, key hoặc value thực.

### Các bước operator thực hiện khi đến lúc rollout

1. Kiểm đúng AWS account/region/instance/parameter, parameter type/key/size tier và role attached bằng console hoặc quy trình vận hành được duyệt. **Không xuất value vào terminal/log/chat.** Instance role chỉ cần đọc parameter hiện có; identity operator cần quyền cập nhật parameter (`ssm:PutParameter`) đúng resource. Không cấp PutParameter cho instance hoặc CI chỉ để operator cập nhật secret.
2. Nếu parameter dùng customer-managed KMS key, kiểm instance `kms:Decrypt` và key policy hiện có, operator có encrypt quyền tương ứng tier. Dùng **cùng parameter/cùng key** thì thêm dòng env không tự đòi thêm resource ARN/quyền. Chỉ xử lý thiếu quyền thực đã chứng minh, scope đúng key và context; không thêm `ssm:*`, `kms:*` hay wildcard path. [AWS KMS/Parameter Store permissions](https://docs.aws.amazon.com/systems-manager/latest/userguide/secure-string-parameter-kms-encryption.html).
3. Trong phiên console được bảo vệ, cập nhật **toàn bộ giá trị hiện có một cách bảo toàn**, thêm `APIFY_API_TOKEN`, pinned build và non-secret flags cần thiết. Không thay SecureString bằng một dòng token làm mất DB/Auth/OpenAI config. Kiểm duplicate key, syntax và biến bị thiếu bằng công cụ không in values. Ghi lại parameter **version**, release SHA, config-name diff, không copy value vào plan/ticket/Git.
4. Apply additive DB migration qua quy trình riêng đã review target/schema/role/disposable proof; release poller **không chạy migrations**. Giữ gate CI/exact-main/attestation/readiness/approval của repo. Đối chiếu release hold thực của commit sắp ship; audit01 đã ghi docs/marker có thể lệch, không xóa hoặc bypass gate để deploy bộ này.
5. Ship compatibility code+frontend trước khi bật tính năng. Với Maps, cài Compose/service worker mới và healthcheck; operator cập nhật installed files theo runbook release, không giả định đổi image tự cập nhật `/opt/moodprint/compose.staging.yml`. `deploy.sh` hiện chỉ health-check api/web và proactive khi có; phiên implement phải thêm Maps worker vào health gate.
6. **Redeploy/recreate API và worker để đọc runtime mới.** Chỉ sửa SecureString không thay environment process đang chạy; timer có thể bỏ qua release cùngSHA đang active, nên không trông chờ sửa parameter là tự restart. Dùng quy trình redeploy/recovery được duyệt với immutable digest/reviewedSHA, bảo toàn rollback image pair. Không reboot hoặc dump container env để kiểm secret.
7. Từ môi trường synthetic/cohort đã cho phép, kiểm feature readiness không lộ secret, chat/citations/job status, receipt/usage và worker heartbeat; live provider chỉ theo gate riêng bên dưới. Mở rộng cohort sau khi theo dõi cost/timeout/deny/uncertain. Cuối rollout defaults phải phục vụ toàn eligible accounts, không để oldfalse cần user bật lại.
8. Nếu lỗi: tắt admission flags phù hợp, redeploy config, giữ cleanup/reconciliation. Hoàn tác runtime parameter version và image pair theo cặp tương thích khi cần; đừng restore image cũ nhưng giữ env bật feature/schema mà image không hiểu. Không hạ migration phá dữ liệu như bước rollback đầu tiên.

**Kết luận cụ thể:** Apify staging cần thêm `APIFY_API_TOKEN` vào SecureString đang có **và deploy/recreate lại** các process dùng nó. Cùng parameter không cần thêm SSM ARN vào `instance-policy.json`. Đây là kết luận từ config source; xác minh IAM attached/KMS thực là bước operator trước rollout, không phải kết quả khảo sát live.

## Các setting mới đề xuất — chưa tồn tại cho đến khi implement

| Biến | Default đề xuất | Authority/phase |
| --- | --- | --- |
| `AI_WEB_SEARCH_ENABLED` | false | 02; dispatch mới, không tắt settlement |
| `AI_MAPS_SEARCH_ENABLED` | false | 03; cần token/build/worker/pricing |
| `MAPS_SEARCH_WORKER_ENABLED` | false | 03; không dùng tắt flag này để trốn cleanup/liability |
| `AI_AGENT_SKILLS_ENABLED` | false | 04; registry + menu skill |
| `AI_SEARCH_ROLLOUT_USER_IDS` | [] | Search cohort, empty nghĩa mọi eligible user khi master flags bật |
| `AI_SEARCH_DAILY_CAP_PER_USER` | 5 | Web+Maps operations, ngày `Asia/Bangkok`, atomic DB admission |
| `AI_SEARCH_USER_CONCURRENCY` / `AI_SEARCH_GLOBAL_CONCURRENCY` | 1 / 2 | Giữ slot tới terminal; Maps async không mất slot khi chat completed |
| `AI_SEARCH_DAILY_BUDGET_USD` | 5 | Tokens child+external fees, là subset global, không ngân sách cộng thêm |
| `AI_COLLABORATION_DEFAULTS_ENABLED` | false | 05; đặt true ở rollout mục tiêu cả old/new accounts |
| `AI_COLLABORATION_POLICY_EPOCH` | 2 | 05; tăng khi chuyển policy/rollback rồi bật lại |
| ~~`AI_AGENT_CHECK_IN_SETTINGS_ENABLED`~~ | — | Bỏ trong phiên triển khai (ruling 06.K4): panel theo `features.proactive`, rollback bằng image pair |

Giới hạn12giây web,3giâyHTTP Maps,60giâyactor,90giâywall,5results,10phútresultTTL,0,05USD Maps cap là constants/settings có validate trong02/03, không tự nới từ input client. Search unavailable nếu global budget/accounting không hợp lệ, sub-budget lớn hơn global, pricing unknown hoặc máy không có worker cần thiết. Feature view public đề xuất `webSearch/mapsSearch/agentSkills/agentCheckInSettings` chỉ là availability; endpoint prompt-capabilities cho reason chi tiết không chứa secret.

Không bật `PROACTIVE_ENABLED/PROACTIVE_WORKER_ENABLED` chỉ vì chuyển vị trí cài đặt. Nếu muốn mở check-in lần đầu, theo [proactive QA runbook hiện có](../../../deploy/aws/proactive-qa.md) với quota, positive budget và lịch người dùng tự chọn. Existing collaboration/V3 flags cần đổi để thực chạy đã liệt kê trong05; ví dụ runtime còn thiếu chúng nên phải bổ sung trong **phiên triển khai**, không sửa trong phiên plan.

## Hợp đồng tài chính và vận hành chung cần review

- Global money gate vẫn là authority qua DB advisory lock; search fee0,01USD/call và Maps cap0,05 là phần **ngoài token ledger**, phải cộng đúng một lần. Search subset5USD phải gồm cả token ledger của child. Reservation2USD/child hiện có nghĩa budget quá nhỏ có thể không nhận một search dù actual bill thấp; không “sửa” bằng bỏ reservation.
- Ledger content-free; owner/parent/child FK cần nullable/`SET NULL` hoặc detached liability authority trước khi purge user/run. Operation UUID và amount/pricing/state không mất khi xóa chat/account, nhưng không giữ owner identity/query/location chỉ để reconciliation. Retry/retention flag off vẫn phải bảo toàn khoản uncertain; ngày chuyển quota không làm mất liability cũ.
- Cap quota/concurrency khác cap tài chính. Một prompt chọn2 providers tiêu hao2 paid operations; async slot chỉ release khi job settled/terminal theo policy. Cache/read status không tính là actor mới. Không decrement quota vì HTTP timeout chưa biết kết quả.
- Worker Maps pool1/overflow0. Worst-case API `(5+2)*2=14`, proactive`2*2=4`, Maps`1*2=2` =20 connection nếu cả ba overlap hai phiên; đây là **bound dự kiến chạm trần**, không còn headroom. Trước rollout worker phải giảm API pool cho deployment này (đề xuất4+1 khi có Maps:10+4+2=16) hoặc chứng minh strategy không overlap workers; không tự tăng DB role limit. Kiểm memory/CPU/stop grace và migration/admin connections riêng. Không có PG connection bị giữ quanh provider/model I/O.
- Metrics chỉ enum/count/latency/USD/status/pricing-version: manual/auto, success/empty/failure/cancel, timeout-stage, deny reason, open/uncertain liability, pending/expired jobs, policy token mismatch. Không query, area, GPS, prompt, source article text hoặc token. Worker health không gọi provider để “test key”.

## Validation tương lai — không thực hiện trong phiên plan

Từng task của02–06 phải viết fake regression → chạy thấy failing → implement → chạy pass và lưu evidence không nội dung/secret; sau đó review/commit theo phạm vi task. DB dùng disposable Postgres/pgvector thuộc harness repo, `APP_ENV=test`; không dùng hosted DB, SQLite thay lock semantics, hoặc local env đang mở của người dùng. Tham chiếu [README](../../../README.md) và [development](../../development.md) để provision/guard DB riêng. Không chạy pytest/fullstack song song cùng disposable DB.

Lệnh mục tiêu cụ thể nằm tại từng task; sau khi pass và chỉ khi scope có liên quan, chạy gate hợp đồng/UI:

```text
# Từ backend; chỉ khi fixture/env test riêng đã chuẩn bị
uv run --locked ruff check app tests
uv run --locked mypy app
uv run --locked python ../scripts/export_openapi.py

# Từ frontend
npm.cmd run contracts:generate
npm.cmd run typecheck
npm.cmd run build
npx.cmd vitest run src/api/streamReply.test.ts src/api/streamCollaboration.test.ts src/api/streamOrchestration.test.ts
npx.cmd playwright test tests/e2e/activities.spec.ts tests/e2e/proactive.spec.ts tests/e2e/collaboration.spec.ts tests/e2e/chat-history.spec.ts
```

Các suite mới phải fake HTTP/SDK/provider và chặn real egress; tests thường không cần key thật. E2E fixtures kiểm hợp đồng/interaction, không chứng minh provider quality hoặc hosted IAM. Có thể thêm bounded fullstack fake với harness repo khi ghép contracts; không thay cả test framework hoặc test suite refactor ngoài scope. Không cần chạy lại mọi suite sau mỗi sửa docs.

**Live tests chỉ opt-in riêng**, bằng credential operator tự cấu hình, cờ test riêng và budget được duyệt. Tên cờ test đề xuất `RUN_LIVE_SEARCH_TESTS=1`; default suite bỏ qua `live` marker. Web:1query/1hostedcall với ceiling reserve đã verify; Maps:1actor/1term/5places/cap0,05USD. Tránh prompt/journal/địa chỉ nhà thật. Nếu min charge/build khiến cap không hợp lệ, dừng và review thay vì tự nâng budget. Record số call, cost, latency, fields có/thiếu và redacted errors; cleanup vendor storage; không coi live optional là điều kiện bắt buộc để viết/chạy fake tests.

## Acceptance/coverage matrix

| Yêu cầu | Task/contract bao phủ |
| --- | --- |
| Web auto + manual, key hiện có | W2, S2/S3, capability endpoint |
| CitationURL backend→SSE→history/export→clickable chat | W1/W3, protocol3, source registry/code-point offsets |
| Hosted tool limits, timeout, usage/fee/unknown money | W2, ledger/reconciliation ở tài liệu này |
| Apify actor ưu tiên, so sánh Google + credential khác | M1, bảng provider03, credential table07 |
| Place name/type/address/rating/hours/Maps link | M1/M3, PlaceResult và one-card-with5places |
| 30giâychat vs actor chậm; cancel/restart/async | M2, 60/90giây deadlines, pending card, next-turn result use |
| Khu vực/GPS/không enrichment | M1/M3, Maps privacy03; GPS backlog riêng |
| Hai SKILL.md, auto/manual, trust registry/tool allowlist | S1/S2, backend registry contracts |
| Dấu+ Web/Maps/Skills, chip bỏ/một lần/retry | S3/S4, frozen options+idempotency W1 |
| Skill current agent hay transfer; activities tránh trùng | Routing04; S2/S4; backlog mood-reset/creative-break/journal-prompt/focus-sprint |
| Mặc định bật oldfalse/missing/new, không enable UI | C1/C4, logical backfill defaults+epoch, retiredPUT |
| Bỏ settings nhưng giữ orchestration/consult/handoff/tools | C2/C3; cả legacyR1–R4 và4V3edges |
| Inventory dữ liệu mỗi capability, không scope rộng hơn | Bảng boundary05; C2 snapshots/taint/group/matching assertions |
| Production flags/eligibility/quota/budget/kill switches | Config05/07, C1/C4; không suy example thành runtime |
| Lịch vào info từng agent, sáng/tối/bật/tắt | K1/K2, owner identity không speaker |
| Bỏ Account/route manager, giữ inbox/history/legacy | K3, oldURL redirects, proactive messages/read marker |
| Giữ timezone/quiet/cap/pause/consent/schedules | K1/K4, single global source + versions, không migration dữ liệu |
| Desktop/mobile/focus/keyboard/accessibility | S4/K2, viewport/resize/select tab loop/axe/manual QA |
| Local credential và SecureString/redeploy/IAM scope | Credential/AWS checklist07, source audit01 |
| Fake tests mặc định/live bounded optional | Từng task02–06 và validation07 |

## Rủi ro còn phải kiểm khi triển khai

Chưa biết runtime flags/SSM/IAM thực, account billing hay actor latency/quality/build/minimum. Chưa kiểm chứng search child trả usage đủ để bound search-content tokens với SDK đang pin. Vì vậy search flags phải fail closed cho đến gate pricing/serialization; không dùng thiếu dữ kiện làm lý do chặn kế hoạch UI/registry/compatibility tests. Defaults-v1 là thay đổi hành vi sản phẩm với tần suất/cost lớn hơn; release phải đo thêm calls/liability mà không tăng quyền đọc private data. UI lịch là di chuyển vị trí, không phải permission để sửa scheduler hoặc tự bật lịch.

Bộ plan được tự rà theo ma trận trên và signatures/contracts chung00. Evidence phiên lập plan chỉ là khảo sát source/docs công khai và kiểm tra tĩnh tài liệu; không có test pass hoặc production-ready claim.

## Kết quả kiểm tra tĩnh tài liệu ngày03/11/2026

Đã kiểm 8 Markdown files, 89 relative links đều resolve, 64 task/acceptance checkboxes chưa đánh dấu thực thi; 5 subplans có Goal/Architecture/Tech Stack/Spec/Global Constraints/Review Focus. Không có trailing whitespace, placeholder chưa chốt hoặc ký tự thay thế UTF-8 trong các tài liệu mới. Danh sách tracked files đang modified vẫn là 6 frontend files đã có trước phiên; chỉ 8 plan files được tạo mới trong thư mục được cho phép. Không chạy tests, import app Settings, đọc secret, gọi provider/runtime API, AWS CLI, migration hoặc deploy để thực hiện việc kiểm tra tài liệu này.
