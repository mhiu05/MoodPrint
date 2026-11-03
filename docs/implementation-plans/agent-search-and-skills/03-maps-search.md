# Maps Search Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans hoặc superpowers:subagent-driven-development để triển khai task-by-task. Chưa gọi actor/API thật trong phiên lập plan.

**Goal:** Tìm địa điểm vui chơi theo khu vực người dùng nhập, hiển thị thông tin thiết yếu và Google Maps link; Hoạt động dùng được kết quả để gợi ý.

**Architecture:** Function tool backend `search_maps` khởi chạy Apify actor bất đồng bộ, trả job card trong lượt chat hiện tại. Worker riêng theo dõi job có lease và deadline; UI đọc status/result từ backend. Lượt sau có `mapsSearchId` có thể dùng kết quả đã chuẩn hóa mà không chạy actor lại.

**Tech Stack:** httpx có sẵn, FastAPI, PostgreSQL/SQLAlchemy, worker cùng image API, React; không cần thêm Apify SDK cho phiên đầu.

**Spec:** [00](00-overview.md), [01](01-codebase-audit.md); dùng fee ledger và protocol 3 của [02](02-web-search-citations-accounting.md).

## Global Constraints

- Provider đầu tiên: `compass/crawler-google-places`, key server-only `APIFY_API_TOKEN` kiểu `SecretStr`.
- Một khu vực rõ ràng, một search term, tối đa 5 places, một actor/lượt; không tự suy vị trí hay hỏi browser geolocation.
- Không enrichment liên hệ/lead/review text/ảnh, không website crawling; chỉ dùng rating tổng và giờ mở cửa nếu có sẵn.
- Không tăng timeout chat hoặc biến job Maps thành proactive/check-in job; không phát sinh model call sau chat completed.
- Search chỉ direct V3 trong đợt đầu; registered/adult/AI consent, session/data-version/budget phải còn hợp lệ.

## Chọn provider và giá tham chiếu

| Phương án | Điểm phù hợp | Đánh đổi |
| --- | --- | --- |
| **Apify actor — chọn đầu tiên** | Đúng actor được yêu cầu ưu tiên; dữ liệu nhiều trường, không cần Google key | Cold start/scraping không có cam kết dưới 30 giây; build/input/output/pricing có thể đổi; cần token và cleanup vendor storage |
| Google Places API (New) Text Search | HTTP API chính thức, field mask rõ ràng; thường phù hợp lookup tương tác | Google Cloud project/API/billing/key riêng; trường rating/hours nâng SKU; attribution/cache rules riêng |

Apify quảng bá **từ 1,50 USD/1.000 places**, nhưng trang pricing cũng liệt kê Starter **3 USD/1.000** và phí plan. Vì vậy 5 places ≈0,0075–0,015 USD chỉ là phép tính phí place theo tier, chưa là tổng chi phí/minimum/add-on. [Actor pricing](https://apify.com/compass/crawler-google-places/pricing).

Google bảng global hiện liệt kê Text Search Pro **32 USD/1.000 requests**, Enterprise **35 USD/1.000**, trước free caps/discounts. Request có `rating/currentOpeningHours` thuộc Enterprise; FieldMask phải tường minh. Không kết luận provider nào rẻ hơn chỉ từ hai đơn vị “place” và “request”. [Google pricing](https://developers.google.com/maps/billing-and-pricing/pricing), [Text Search fields](https://developers.google.com/maps/documentation/places/web-service/text-search).

Chọn Apify để đánh giá và triển khai adapter đầu tiên; nếu độ trễ/quality hoặc bound chi phí không đạt gate thì giữ Maps off và lập thay provider, không tự fallback sang Google cùng một yêu cầu. Chưa có bằng chứng latency/quality/live ở khu vực Việt Nam. Khi triển khai Google, phải có policy attribution/storage riêng thay vì dùng nguyên retention của Apify. [Places policies](https://developers.google.com/maps/documentation/places/web-service/policies).

## Interfaces và luồng async

```text
MapsSearchRequest(category: approved category, area: str[2..120], limit: int[1..5])
ProviderRunRef(run_id: str, dataset_id?: str, storage_refs: dict[str,str]) // backend only
ProviderRunStatus(state: pending|succeeded|failed|timed_out|aborted, charged_usd?: Decimal)
MapsProvider.start(request, timeout_seconds=3) -> ProviderRunRef
MapsProvider.status(ref) -> ProviderRunStatus
MapsProvider.results(ref, limit=5) -> list[PlaceResult]
MapsProvider.abort(ref) -> None

PlaceResult(placeId?, name, category?, address, rating?, ratingCount?,
            openingHours?, mapsUrl, fetchedAt, provider='apify')
MapsSearchView(searchId, status, version, expiresAt, retryAfterSeconds,
               places: list[PlaceResult], errorCode?)
```

Một `places` card chứa tối đa 5 places, không phải 5 cards (giới hạn existing reply là 3 cards). Pending card `{kind:'maps_search', searchId}` không chứa provider run/dataset/token. Card kết quả có name, category/address, rating/hours nếu có và “Mở Google Maps”; không hiển thị field thiếu như dữ kiện đã biết. Giờ/rating có `fetchedAt`, không khẳng định “đang mở” nếu không có timezone/giờ hiện tại đáng tin.

Backend chỉ lấy/maps URL từ dữ liệu provider đã validate hoặc tự dựng `https://www.google.com/maps/search/?api=1&query=...&query_place_id=...` với escaping. Host Google Maps chính xác, HTTPS, không redirect/fetch URL tùy ý. Output discard phone/email/social/owner/reviewer/contact fields kể cả khi provider vẫn gửi. Nội dung place là dữ liệu không tin cậy, không phải instruction hoặc grant.

1. Manual Maps hoặc auto địa điểm → lấy `area` từ prompt/options hiện tại. Thiếu/không rõ (ví dụ “gần mình”) → hỏi khu vực, chưa reserve/dispatch actor. Không lấy địa chỉ từ journal/profile/IP. `hangout` không có khu vực vẫn có thể gợi ý hoạt động chung.
2. Tool admission: lock owner → quyền/quota → search fee reservation → tạo `AiMapsSearch` trạng thái `starting`; commit. Gọi start endpoint với timeout≤3 giây; không giữ DB. Lưu ref trong transaction ngắn có fence; tool trả card pending, parent trả lời ngắn và completed trong deadline chat.
3. Worker poll trạng thái với lease; chỉ lấy tối đa 5 dataset items sau thành công; normalize. API UI `GET /ai/maps-searches/{searchId}` đọc view có owner authorization, `Cache-Control:no-store`. GET không tự start actor hoặc model.
4. UI poll pending khi card visible (2 giây trong 30 giây đầu, sau đó 5 giây, tối đa job deadline), dừng khi hidden/unmount/terminal/logout. Worker vẫn xử lý deadline/cleanup khi browser đóng; không dựa vào client timeout để ngừng trả phí.
5. Kết quả ready hiển thị trong card. Nút “Nhờ trợ lý gợi ý từ kết quả” chỉ chèn lựa chọn `mapsSearchId` + draft, người dùng bấm gửi; lượt sau backend đọc đúng job/result sau revalidation. Tự nhận ý định ở lượt sau có thể tái dùng job hiện tại nếu cùng scope và còn hạn. Không auto gửi tin hay âm thầm chuyển sang Hoạt động.

**API mới:** GET view trên; POST `/ai/maps-searches/{searchId}/cancel` với `expectedVersion`, CSRF/idempotency. Job start chỉ qua tool đã admission, không có public arbitrary-actor endpoint. `mapsSearchId` khác owner/session/conversation, expired hoặc data-version cũ trả lỗi chung; backend không chấp nhận dataset/run ID do client đưa.

## Actor config và thời gian/chi phí

Body allowlist: `searchStringsArray` đúng một term từ category công khai, `locationQuery` là khu vực, `maxCrawledPlacesPerSearch=5`, `language='vi'`, `scrapePlaceDetailPage=false`, `scrapeContacts=false`, `maxReviews=0`, `maxImages=0`, `maximumLeadsEnrichmentRecords=0`; social/other enrichment không bật. Không nhận raw actor JSON, startUrls, polygon, proxy hoặc actor ID từ model/browser. Các field này cần snapshot test theo schema/build đã review; không bỏ trống limit vì có thể lấy hết. [Actor input schema](https://apify.com/compass/crawler-google-places/input-schema).

Provider API dùng `POST /v2/acts/compass~crawler-google-places/runs`, `waitForFinish=0`, `timeout=60`, `maxTotalChargeUsd=0.05`, `restartOnError=false`, build được pin sau gate đánh giá. API start có run ref, không đợi toàn bộ dataset. Cap là đề xuất cần xác minh với pricing/minimum hiện tại trước rollout; nếu bị từ chối vì minimum hoặc price thay đổi, unavailable và không tự nâng cap. `maxItems` không thay thế giới hạn crawl/dataset-read. [Apify Run Actor](https://docs.apify.com/api/v2/actors-runs-post).

Sync endpoint có thể đợi tới **300 giây**; timeout HTTP không đồng nghĩa actor được abort. Vì vậy không chọn sync rồi chỉ cắt chờ ở giây 30. [Synchronous endpoint](https://docs.apify.com/api/v2/actor-run-sync-get-dataset-items-post).

Actor execution≤60 giây, job wall deadline≤90 giây gồm queue/start/poll/fetch, mỗi status/result HTTP≤3 giây, response body≤64 KiB. Worker poll có exponential backoff giới hạn và jitter, không retry start sau response-unknown. Overdue/cancel phải attempt abort và reconcile tiền cuối; abort lỗi không release reservation. Search flag tắt vẫn cho cleanup/reconcile/abort chạy. Timeout trước dispatch có bằng chứng chưa gửi mới được release.

`AI_SEARCH_DAILY_BUDGET_USD=5` subset global, maps reserve0,05/lần theo bound được xác minh; shared cap 5 operations/user/day, 1 pending/user, 2 global. Không cache chéo người dùng. Result RAM cache tối đa 10 phút cùng owner/session và job TTL; API không public vendor dataset ID. Persist normalized place card chỉ khi người dùng dùng kết quả trong saved reply; không lưu prose/result vào DB temporary chat. Vendor input/dataset/queue/KV phải để restricted và cleanup sau tối đa 10 phút; metadata job giữ tới khi settlement/cleanup xong. Không gọi việc xóa local là cam kết xóa backup/vendor logs.

## Persistence và worker

Tạo `AiMapsSearch` content-free: UUID PK, owner, parent run, conversation UUID nullable (temporary không có durable row), session ID cho temporary, data version, status/version, provider run/dataset/storage refs chỉ backend, fee operation FK, deadline/expiresAt/nextPollAt, worker lease/fence. Không persist query/area/raw result; query chỉ cần ở start. Nếu crash trước khi nhận ref thì job `uncertain`, không retry actor; operator reconcile bằng metadata, không đoán chưa tính phí.

Worker dùng `FOR UPDATE SKIP LOCKED`, transaction ngắn; trạng thái `starting → pending → ready|empty|failed|timed_out|cancelled|expired` với transitions có fence; financial uncertain là trạng thái ledger độc lập. Worker restart tiếp tục poll ref đã biết, không replay start. Saved job result có thể đọc lại vendor trong TTL khi RAM cache mất; sau TTL cần người dùng chủ động tìm lại. Purge account/session/AI consent: invalidate job access và request abort/cleanup, tách liability trước xóa identity; không FK cascade làm biến mất khoản chưa chốt.

Files tạo: `backend/app/ai/search/{maps,apify,maps_jobs,maps_routes}.py`, thêm schema/model vào `search/{schemas,models}.py`, `backend/app/jobs/maps_search.py`, `backend/alembic/versions/<next>_maps_search_jobs.py`, `frontend/src/features/real/search/{MapsSearchCard,useMapsSearch}.tsx`. Files sửa: runtime/tools, main router registration, config, schema/card/protocol 3 và render, `users/lifecycle.py`, `jobs/retention.py`; `deploy/compose.staging.yml`, `deploy/aws/deploy.sh` và runtime example chỉ trong phiên triển khai (worker healthcheck/pool budget, xem 07).

## Tasks và tests tương lai

### M1 — Adapter an toàn và kết quả tối thiểu

**Interfaces:** `MapsProvider`/`PlaceResult` như trên. **Tests mới:** `backend/tests/test_maps_provider.py`.

- [x] Viết HTTP-fake tests cho start/poll/result/abort, auth header không query token, một khu vực/term/5 places, enrichment off, field dư bị bỏ, malformed hours/rating/URL, huge body và no-results.
- [x] Implement `ApifyMapsProvider` bằng httpx reuse client, chỉ HTTPS host cố định `api.apify.com`; pin actor/build/pricing và map input allowlist. Không tự follow dataset URL tùy ý, chỉ ID hợp lệ ở fixed endpoint.
- [x] Chạy `uv run --locked pytest tests/test_maps_provider.py -q`; pass bằng mock transport, khẳng định không có real requests. Contract drift fail closed thay vì fallback không giới hạn.

### M2 — Async job, deadline, accounting và lifecycle

**Interfaces:** `AiMapsSearch`, `MapsSearchView`, cancel API; dùng `AiSearchUsage` của W2. **Tests mới:** `test_maps_jobs.py`, `test_maps_api.py`.

- [x] Fake clock/provider + disposable PG cases: concurrent admission, duplicate client ID/options, start response lost, worker chết sau dispatch, lease takeover, cancel racing ready, session revoke/account delete, deadline/abort thất bại, no-result still charged, switch off while pending.
- [x] Implement fenced job start/poll/cleanup, private status/cancel routes, retention/financial detachment; không giữ DB connection qua HTTP. Khẳng định parent chat completed không bị worker viết thêm bubble hoặc gọi LLM.
- [x] Chạy `uv run --locked pytest tests/test_maps_jobs.py tests/test_maps_api.py tests/test_search_accounting.py -q`; pass và không vượt 5/user/day,1/user,2/global,0,05 bound hoặc 90 giây wall trong fake tests.

### M3 — Card và agent sử dụng kết quả

**Files/tests:** `MapsSearchCard`, `useMapsSearch`, runtime renderer, `frontend/tests/e2e/maps-search.spec.ts`, mới `frontend/src/features/real/search/mapsSearch.test.ts`.

- [x] Fixture “quán cà phê ở quận 3” tạo pending card; “gần mình” chỉ hỏi vùng; ready tối đa5 đúng name/type/address/rating/hours/link. Test provider thiếu rating/hours không bịa dữ kiện.
- [x] Implement poll/visible states/cancel, source labels và draft action; `mapsSearchId` dùng cached normalized data sau authorization, không tạo actor thứ hai. Trong hội thoại Hoạt động đã tạo job, agent phải gợi ý được từ kết quả ở lượt tiếp theo; không mang job từ hội thoại Điều phối sang chat riêng khác hoặc lách conversation boundary.
- [x] Offline UI/API fixtures kiểm keyboard/mobile, lỗi mạng và retry cùng job, navigation back/reload/gone card, options chip một lượt, không lộ vendor ref/token và không auto-send. Terminal/cancel stop polling. Evidence ở [implementation-evidence](implementation-evidence.md); browser forward riêng chưa có assertion chuyên biệt.

### M4 — Rollout provider/worker

- [x] Thêm settings đề xuất `AI_MAPS_SEARCH_ENABLED=false`, `APIFY_API_TOKEN`, `APIFY_MAPS_ACTOR_BUILD`, `MAPS_SEARCH_WORKER_ENABLED=false`, các cap/deadline; healthcheck không gọi Apify.
- [x] Thêm worker service pool1/overflow0; cập nhật deploy health validation và kiểm tổng connection budget khi API/proactive/maps cùng overlap. Worker poll không phụ thuộc cờ admission đang bật.
- [ ] Khi tới gate staging, làm theo credential/SSM checklist [07](07-rollout-credentials-and-coverage.md); live test tùy chọn đúng1 actor≤5 places/cap0,05 và không vượt budget đã xác minh. Không tự gọi live để hoàn tất M1–M3.

## Review Focus và acceptance

Thiếu vùng → M3 không dispatch; start-timeout vẫn tính tiền → M2 uncertain/no replay; worker restart → M2 fence/known-ref resume; provider gửi contact fields → M1 discard; temporary chat/account deletion → M2 không persist query/result và liability sống tới settlement.

Chấp nhận khi actor async không làm chat vượt30 giây, card tối đa5 kết quả có link Maps, agent dùng được kết quả ở lượt sau, mọi failure có đường phục hồi rõ, và chỉ bắt đầu trả phí khi credential/pricing/worker sẵn sàng. AWS cần **thêm `APIFY_API_TOKEN` vào SecureString hiện có rồi redeploy/recreate backend và worker**; không thêm parameter ARN hoặc mở IAM chỉ vì thêm biến. Chi tiết quyền operator/KMS và cách không in secret ở 07.

GPS là backlog: nếu thêm sau, cần nút hành động riêng, browser consent đúng lúc, giải thích chỉ dùng cho lượt này, lượng hóa precision/radius và TTL, không lưu tọa độ raw vào history/log; từ chối GPS luôn có nhập khu vực thay thế. Không triển khai GPS trong phase đầu.

### Review bổ sung 2026-11-03 — cancellation và giới hạn worker

- Trạng thái kết thúc trên UI không chứng minh actor đã dừng. Ref còn chạy hoặc abort chưa xác nhận phải giữ `AiSearchUsage.active` để admission không vượt concurrency; chỉ giải phóng khi có bằng chứng vendor terminal (hoặc trường hợp no-ref unknown đã được quy định riêng).
- Qua TTL vẫn phải poll và thử abort actor pending trước khi xóa storage; không bỏ abort chỉ vì UI đã timed out/cancelled.
- Claim lease trong transaction chỉ khóa job, commit trước khi chờ account gate. Authorization theo thứ tự owner → job và settlement kiểm fence, tránh khóa ngược với cancel/delete.
- Mỗi HTTP request/body có deadline tổng 3 giây; một tick I/O tối đa 20 giây dưới lease 25 giây. Heartbeat xác nhận worker/DB hoạt động, không phải bằng chứng provider đang khỏe hoặc cleanup đã thành công.
