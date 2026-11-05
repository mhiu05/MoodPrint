# Kế hoạch AI: 50 lượt chat đồng thời

> **Implementation, 2026-11-05:** Yêu cầu hiện hành cho phép local engineering và read-only cloud. Target AI toàn ứng dụng **$50/ngày**, chưa kích hoạt production; campaign staging tối đa **$3 tổng cộng**, chỉ `gpt-6-luna` generation, không judge API. D03/D05/D10/D12 đã được chấp thuận. Mỗi production mutation cần approval riêng. Các đoạn audit-only/$20/$5 bên dưới là baseline lịch sử. [Tiến độ](12-implementation-progress.md), [cloud](13-cloud-inventory-redacted.md), [approval proposals](14-owner-decisions-required.md), [kết quả](15-test-results.md) là nguồn cập nhật; release vẫn **NO-GO**.

> **Dành cho người triển khai:** thực hiện từng task bằng `executing-plans` hoặc phương thức đã được chủ dự án chọn; đọc toàn bộ ràng buộc trước khi sửa code. Tài liệu này là audit và kế hoạch, không phải báo cáo chạy tải hay ủy quyền gọi provider.

**Mục tiêu:** chứng minh 50 lượt chat được tiếp nhận đồng thời trong một API process, duy trì 15 phút theo workload đã định nghĩa, trong ngân sách và quota hiện có; đo riêng số HTTP client, lượt được admission và lời gọi provider.

**Kiến trúc đề xuất:** giữ topology một API process được hỗ trợ; bảo toàn admission/financial lock ở PostgreSQL. Bổ sung giới hạn lời gọi provider theo fanout, reservation dựa trên bound được cưỡng chế trước mỗi dispatch, và phép đo đầy đủ trước khi cân nhắc tăng cấu hình.

**Stack:** FastAPI/asyncio, OpenAI Agents SDK/Responses API, PostgreSQL/SQLAlchemy, SSE/fetch, Voyage embeddings.

**Phạm vi:** snapshot mã nguồn và cấu hình local ngày 2026-11-05. Không sửa runtime, config, migration, test hoặc `.gitignore`; không chạy paid calls, load test cloud hay test database hosted trong audit này. Đã đọc `Settings()` local và chỉ in allowlist model/số/boolean; chưa chạy suite hoặc load script. Deployment đang chạy, quota provider và hiệu năng thực tế đều **UNKNOWN**.

## Ràng buộc và kết luận hiện tại

- Mục tiêu 15 phút là **tiêu chí cần kiểm chứng**, chưa có kết quả đạt mục tiêu trong tài liệu này.
- Giữ trần $20 và các policy quota/consent/guest hiện có. Không đạt 50 bằng cách tắt accounting, bỏ reservation, bật budget=0, tăng tiền hoặc tự nhân replica.
- Cấu hình class mặc định là `ai_global_concurrency=50`, `ai_user_concurrency=2`, timeout 30 s, budget 0; nhưng file local có key lặp và `Settings()` thực tế đọc được **global 10, user 2, timeout 60 s, budget $20, accounting=true, pool 5+2, proactive worker=false**. Bằng chứng: `backend/app/core/config.py:99`, `backend/app/core/config.py:102`, `backend/app/core/config.py:126`; `backend/.env:35`, `backend/.env:67`, `backend/.env:69`, `backend/.env:66`, `backend/.env:76`, `backend/.env:77`. Các giá trị local này không chứng minh giá trị Compose/container/production.
- Reservation hiện tại là **$2 mỗi `AiUsage` row**. Từ ngân sách rỗng $20, tối đa 10 row chưa quyết toán được giữ cùng lúc; child row cũng giữ $2. Vì thế ngay cả sửa global 10 thành 50 cũng chưa tiếp nhận được 50 lượt dài chưa settle. Test đã có ghi rõ 12 attempt chỉ 10 thành công: `backend/tests/test_budget_reservations.py:92`, `backend/tests/test_budget_reservations.py:108`. Đây là assertion trong mã test, **không phải kết quả test chạy trong audit**.
- Admission global đã có ở DB: advisory lock chung và count mọi `AiRun.status=running`; semaphore/SSE/RAM mới là theo process. Không được mô tả toàn bộ admission là một semaphore local rồi kết luận cứ thêm worker sẽ nhân 50.
- Tăng lên 50 chỉ hợp lệ khi chứng minh bound của tất cả model/tool calls, tổng liability còn lại, quota RPM/TPM và DB đáp ứng. Nếu không chứng minh được bound đủ nhỏ thì ghi rõ **50 admitted đồng thời dưới $20 hiện không khả thi**, giữ admission từ chối có kiểm soát.

## Bằng chứng kiến trúc và điểm nghẽn

| Nội dung | Bằng chứng chính xác | Hệ quả khi nhắm 50 |
| --- | --- | --- |
| Admission dùng chung DB | `backend/app/ai/persistence.py:419`, `:423`, `:425`, `:443`; `backend/app/ai/chat_routes.py:446` | Lock `664201,1` bảo vệ check+insert trong transaction; count gồm user/proactive/agent/collaboration/journal đang chạy. User cap 2 chỉ đếm origin=user. Không có đảm bảo một parent tương ứng một provider call. |
| Semaphore local | `backend/app/ai/runtime.py:142`, `:763`; `backend/app/ai/groups/turn.py:367` | Mỗi runtime có semaphore riêng. Deadline của direct bao cả chờ semaphore, memory và model; không có queue người dùng bền vững. Group giữ một slot nhưng deadline ngoài là `2*ai_timeout_seconds`. |
| Child/fanout | `backend/app/ai/orchestration/workflow.py:437`, `:449`, `:756`; `backend/app/ai/collaboration/coordinator.py:367`; `backend/app/ai/groups/turn.py:136` | Children thêm row/reservation. DB count tăng trong lúc workflow chạy; không đồng nghĩa count là semaphore chặt quanh từng HTTP request provider. V3 có hai specialist chạy song song trong một parent slot. |
| State/RAM và topology | `backend/app/ai/runtime.py:138`, `:139`, `:149`; `deploy/README.md:5` | Temporary context/runs/events, stream counters nằm RAM; deploy hỗ trợ một worker/replica. Saved transcript có durable replay không làm ephemeral state chia sẻ được. |
| Budget thực sự atomic | `backend/app/ai/accounting.py:94`, `:103`, `:108`, `:129`; `backend/app/modules/guests/accounting.py:103` | Check liability+reserve cùng lock/transaction, không phải cache local. Ceiling registered là `min(config,20)`. Budget 0 tắt guard này. Không được thay bằng estimated average để vượt reservation. |
| Bound rất rộng | `backend/app/ai/accounting.py:18`, `:23`, `:24` | Giá thận trọng 550/550/1650 nano USD/token, envelope cả 922 k input, tối đa 3 call và 1200 output/call, làm tròn $2. Đây là bound bảo vệ tài chính, không phải giá hóa đơn trung bình. |
| Quyết toán/unknown | `backend/app/ai/accounting.py:80`, `:149`, `:162`, `:172` | Usage thiếu input dương không được xem là response đã biết giá; open giữ envelope tới terminal; mismatch/unknown giữ uncertain, crash không replay provider. |
| Ngày ngân sách | `backend/app/ai/accounting.py:27`, `:33`; `backend/app/ai/persistence.py:451` | Liability lấy cả hôm qua+hôm nay UTC, cộng mọi open/uncertain bất kể ngày; quota lượt user dùng helper ngày riêng. $20 không có nghĩa cứ 00:00 Bangkok là thêm $20 mới. |
| SSE không stream token thô | `backend/app/ai/provider.py:309`; `backend/app/ai/chat_routes.py:671`; `frontend/src/api/stream.ts:282` | Provider deltas bị giữ trong SDK; client nhận progress và final đã validate, rồi completed. First progress không phải TTFT. |
| SSE replay | `backend/app/ai/chat_routes.py:570`, `:617`, `:737`, `:746`, `:777`; `backend/app/ai/groups/events.py:18`, `:28` | Saved events được dựng lại từ DB, cursor `afterSeq`/`Last-Event-ID`; direct tối đa 3/5/6 event tùy mode. Group có protocol riêng tối đa 11 event. Ephemeral replay phụ thuộc RAM hiện tại. |
| Disconnect/cancel | `backend/app/ai/chat_routes.py:769`, `:759`, `:821`; `backend/app/ai/runtime.py:189`, `:265`; `backend/app/ai/provider.py:146` | Đóng SSE giải phóng stream slot và dừng đọc, không tự gọi cancel model. Cancel endpoint dừng/drain SDK; saved cancel có durable row và policy monitor nhận biết. Không hứa rằng disconnect lập tức ngừng tính phí. |
| Stream slot | `backend/app/core/streams.py:1`, `:13`, `:22`; `backend/app/ai/runtime.py:149` |6 stream/user/process, reserve đồng bộ trước await và release idempotent/finally/background.50 client gồm nhiều tab không bằng 50 user hoặc 50 model calls; thiếu global SSE cap. |
| Polling tạo tải DB | `backend/app/ai/chat_routes.py:654`, `:777`, `:806`; `backend/app/ai/runtime.py:826` | Saved poll mỗi 0.25 s ≈200 poll transaction/s cho 50 stream; ephemeral 0.1 s ≈500/s. Policy check 0.5 s thêm≈100 transaction/s cho 50 direct run. Mỗi transaction gồm nhiều query/auth check. Đây là phép tính cấu hình, chưa phải RPS đo được. |
| DB connection | `backend/app/core/config.py:104`; `backend/app/infrastructure/database/connection.py:23`; `backend/app/infrastructure/database/budget.py:3`, `:14`, `:20` | Một API pool 5+2=7; hai process overlap 14 cộng proactive 2=16, so với approved role 20 nhưng observed cũ 10. Cần xác minh role hiện tại; không tăng pool tới 50 chỉ vì 50 chat. SSE sleep/provider I/O không giữ nguyên một DB session suốt lượt. |
| HTTP client | `backend/app/ai/provider.py:160`, `:164`; `backend/app/core/outbound.py:25`, `:34`, `:37` | OpenAI tái sử dụng client, 100 max connections/20 keepalive, connect≤5 s. Đây là pool transport, không phải quota provider và không phải giới hạn toàn hệ thống cho mọi client/process. |
| Timeout/retry | `backend/app/ai/provider.py:55`, `:219`, `:290`, `:291`; `backend/app/core/outbound.py:10`, `:31` | Direct provider wrapper 30 s dù local outer 60 s; SDK/model retries 0, transport thử lại kết nối 2 lần. Không có retry tự động HTT P429/503. Hook logical requests không chắc đếm mọi connect attempt. |
| RAM bound | `backend/app/ai/runtime.py:276`, `:298`, `:323`, `:1022` |2 MiB/conversation, 64 MiB tổng content/event/reserved output; không phải total RSS bound. Capacity scan duyệt conversations+runs/events, cần đo event loop khi lịch sử nhiều. Saved idle copy bị bỏ khi xong. |

Admission DB bảo vệ các lượt bắt đầu qua `admission()`, nhưng các child path và journal không dùng chính xác cùng cơ chế global/provider slot. Ví dụ journal chỉ lấy budget lock rồi insert row/call (`backend/app/ai/journal_memory.py:218`, `:266`, `:298`); nó không acquire `runtime.slots`. Vì vậy không suy diễn “mọi provider call chắc chắn≤50” từ setting 50. Giữ global DB lock hiện có và đo/chỉnh semantics trong P3-I03.

## Đếm đúng workload

Đặt `C_http` là số kết nối SSE/client đang mở, `C_turn` là parent turn đã admission chưa terminal, `C_run` là mọi row đang running, `C_provider` là HTTP model request thực sự inflight, và `N_call` là tổng lời gọi trong khoảng đo. Mỗi đồ thị và báo cáo phải dùng tên riêng này.

| Route/workflow | Lời gọi model/turn theo mã hiện tại | Đồng thời trong một turn | Chi phí/latency phụ |
| --- | --- | --- | --- |
| Direct cơ bản |1..3; `_BudgetHooks` chặn>3, tool≤2, `max_turns=3` (`backend/app/ai/provider.py:98`, `:116`, `:139`, `:304`) | Thường 1, `parallel_tool_calls=False` ở`:288` | Memory query embedding có thể thêm call Voyage trước model; tool đọc journal có thể thêm query embedding. |
| Phase 2 collaboration | Tối đa 1 specialist call ngoài direct 1..3; specialist no tools và model_limit 1 (`backend/app/ai/provider.py:512`, `:544`, `:549`; `backend/app/ai/runtime.py:840`) | Specialist rồi main, không suy ra 4 inflight | Child row/reservation riêng; specialist timeout mặc định 8 s (`backend/app/core/config.py:80`). |
| Điều phối V3 | Hard cap 7 cho toàn planner/main/specialists (`backend/app/ai/orchestration/workflow.py:72`, `:113`, `:263`, `:295`, `:303`) | Có thể 2 specialist song song, parent vẫn giữ 1 local slot (`:756`) | Planner 1 call tối đa 500 output, timeout 8 s (`:423`); mỗi child có ledger riêng.7 là giới hạn, không phải mọi turn đều dùng 7. |
| Group | Selector 0 ở fast path hoặc 1; tối đa 3 speaker, mỗi speaker≤3; tổng≤`1+3*speakers`=10 (`backend/app/ai/groups/turn.py:98`, `:166`, `:186`, `:372`) | Speaker tuần tự (`:372`), không phải 10 inflight/turn | Selector 300 output, speaker 900 (`:190`, `:272`); group deadline ngoài 2× setting. |
| Proactive | Main không tool, `_BudgetHooks` mặc định≤3 và `max_turns=2`, không khẳng định luôn 1; consultation có thể thêm 1 (`backend/app/ai/provider.py:358`, `:399`; `backend/app/ai/proactive/executor.py:211`) | Worker riêng claim≤concurrency rồi gather (`backend/app/jobs/proactive.py:331`) | Outer 45 s (`backend/app/ai/proactive/executor.py:396`), share mặc định 50%; DB admission kiểm tra global (`backend/app/ai/proactive/policy.py:183`). |
| Journal auto memory | Bounded background extraction; gọi provider cùng runtime nhưng ngoài chat semaphore (`backend/app/ai/journal_memory.py:298`; `backend/app/ai/provider.py:484`) | Hiện worker pass tuần tự, mỗi process có một pass | Share mặc định 20%; row journal cũng giữ $2; 10 jobs/pass mặc định, có debounce/retry/lease. |

50 browser mở SSE chỉ chứng minh `C_http=50`.50 response 202 cũng chưa chứng minh 50 provider inflight; thậm chí mức 50 trong `C_run` có thể gồm nhiều child của ít parent. Với mixed workload phải ghi parent completed/admitted, row count, provider active/peak, calls/turn phân phối và từng loại từ chối. Không nhân 50×7 thành 350 inflight mặc định; 7 chủ yếu là tổng call, fanout đồng thời tối đa phụ thuộc từng đoạn workflow.

## Giá, công thức và ý nghĩa $20

Đã tìm và fetch nguồn chính thức OpenAI Docs ngày 2026-11-05. Model local là `gpt-6-luna` (`backend/.env:10`, xác minh `Settings()`), không tự thay bằng model khác. Standard short context: input $0.10, cached input $0.01, output $0.50/1 M token. Long input>272 k: input/cache×2, output×1.5; cache write 30 phút×1.25, 12 h×2.5; Fast×2, regional khi áp dụng×1.1. Nguồn: [OpenAI pricing](https://developers.openai.com/api/docs/pricing), [GPT-6 Luna](https://developers.openai.com/api/docs/models/gpt-6-luna). Giá áp dụng tài khoản, tier thực dùng và cache-hit ratio chưa quan sát; không giả định cache hit.

Cho call `j`, dùng `I_j` là tổng input, `H_j` input cache-hit, `O_j` output bao cả reasoning được tính phí; `W_j` cache-write nếu có, không đếm trùng vào uncached. Với Standard short và không cache write:

```text
cost_call_j = ((I_j - H_j)*0.10 + H_j*0.01 + O_j*0.50) / 1,000,000 USD
cost_turn = sum(cost_call_j for j in all model calls) + tool_fees + embedding_cost
cost_day = sum(cost_turn của mọi user) + proactive + journal_background + voice + external_tools
reserve_capacity <= floor((20 - resolved_cost - unresolved_liability - other_reservations) / bound_per_active_unit)
RPM_model ≈ 60 * completed_turns_per_second * mean_calls_per_turn
TPM_model ≈ RPM_model * mean(input_tokens_per_call + output_tokens_per_call)
```

Từng call phải dùng đúng pricing tier/context/cache category; không nhân giá nhỏ của final output cho toàn workflow. Formula trên là mô hình planning, không thay thế invoice/headers.

| Kịch bản minh họa, không cache/tool/embed | Standard/turn | Ledger thận trọng 550/1650 nano/turn khi đã settle |1000 user×1 turn |1000 user×10 turn | Turn tối đa/$20 theo Standard thuần |
| --- | ---: | ---: | ---: | ---: | ---: |
|1 call, 2 k input/400 output |$0.0004 |$0.00176 |$0.40 |$4 |50, 000 |
|1 call, 8 k/800 |$0.0012 |$0.00572 |$1.20 |$12 |16, 666 |
|1 call, 20 k/1200 |$0.0026 |$0.01298 |$2.60 |$26 |7, 692 |
|3 call, mỗi call 8 k/800 |$0.0036 |$0.01716 |$3.60 |$36 |5, 555 |
|7 call, mỗi call 8 k/800 |$0.0084 |$0.04004 |$8.40 |$84 |2, 380 |
|10 call, mỗi call 8 k/800 |$0.0120 |$0.05720 |$12 |$120 |1, 666 |

Các dòng 7/10 call là sensitivity scenario, không transcript token thực tế của planner/specialist. “Turn/$20” đã làm tròn xuống, chỉ tính token Standard, **không phải capacity hệ thống hiện tại**. Vì ledger dùng conservative rate và carryover, guard sẽ chặn sớm hơn các số Standard này.1000 user×60 turn/day theo quota default tạo 60, 000 turn: ngay kịch bản nhỏ nhất là $24 Standard trước mọi phí phụ, medium là $72; quota user không đảm bảo ngân sách global đủ cho tất cả user.

Nếu 50 active liên tục và mean wall time mỗi turn 10 s, trong 900 s có khoảng 4, 500 turn, 300 turn/min. Medium 1 call là 4, 500 call, ≈$5.40 Standard và≈2.64 M token/min; medium 7 call là 31, 500 call, ≈$37.80 Standard và≈18.48 M token/min. Cùng 50 concurrency nhưng turn 30 s chỉ≈1, 500 turn/15 min. Đây là công thức giả định để chọn workload, **chưa đo latency/throughput**. Per-user 20 RPM có thể làm một closed-loop user gửi 6 RPM hợp lệ; không dùng một tài khoản để giả 50 user vì cap 2.

Bound hiện tại dùng full 922 k input/call. Giá thận trọng cho 3 call×(922 k×550 +1200×1650) nano≈$1.52724; làm tròn $2 (`backend/app/ai/accounting.py:18`).50 parent row cần reserve $100 khi tất cả còn open, nên không thể giữ $20. Previous liability/children giảm slot khả dụng thêm.10 parent không để dư reservation cho planner/specialist có thể làm delegation fail/fallback trước khi có đủ budget cho child. Không giải quyết bằng reserve theo mean hoặc “gọi trước, ghi tiền sau”.

Hướng khả thi cần kiểm chứng: cưỡng chế input/output bound từng call và reserve cả workflow atomically. Ví dụ **đề xuất phân tích, chưa triển khai** nếu mọi call đã bị chặn ở 16 k input và 1200 output, conservative bound/call=16000×550+1200×1650 nano=$0.01078; 7 call≤$0.07546, 50 workflow≤$3.773, chưa cộng công cụ/background. Nếu không thể enforce 16 k trên system prompt+history+retrieval+tool returns thì ví dụ này vô hiệu. Không thay current bound trước khi test chứng minh pre-dispatch enforcement ở mọi call và không double count parent/child. Threshold 50 luôn phụ thuộc remaining budget, nên sau khi chi gần $20 thì từ chối thêm là hành vi đúng.

### Quota provider còn thiếu

Rate limits dựa trên RPM/RPD/TPM/TPD tùy model/tier, ở organization/project chứ không theo user; header có remaining/reset và có thể `Retry-After`. Cần dùng quota thật trong console/headers; public table không chứng minh account hiện tại đủ cho 50. Failed requests có thể tiêu rate limit; không replay tự động sau khi đã có output streaming. Nguồn: [OpenAI rate limits](https://developers.openai.com/api/docs/guides/rate-limits). **Quota project/org thực tế: UNKNOWN**, chưa truy cập tài khoản hoặc gọi provider. P3-I09 giao HUMAN xác minh.

## Background, guest và giới hạn phạm vi tài chính

`embedding_pass()` lần lượt xử lý memory embeddings rồi journal embeddings/automatic memories; một coroutine/process chạy mỗi pass rồi sleep 1 s (`backend/app/main.py:136`, `:225`). Mỗi loại batch được xử lý tuần tự (`backend/app/ai/embeddings.py:412`, `backend/app/modules/journal/indexing.py:123`, `backend/app/ai/journal_memory.py:178`). Backlog memory chậm có thể kéo dài thời gian chờ journal. Lease/SKIP LOCKED/fenced publish đã có, nhưng tăng số API process đồng thời tăng worker pass local và outbound traffic; không coi setting batch 10 là 10 call song song.

Voyage dùng `voyage-4-lite` local (`backend/.env:45`), tạo `httpx.AsyncClient` mới mỗi `embed()` nếu không inject (`backend/app/ai/voyage.py:36`, `:43`); query memory và journal gọi trực tiếp (`backend/app/ai/embeddings.py:641`, `backend/app/modules/journal/retrieval.py:34`). Registered embeddings không đi qua `reserve_accounting()`; còn journal extraction OpenAI có row/budget share (`backend/app/ai/journal_memory.py:230`, `:233`). Vì vậy $20 guard hiện tại không tự chứng minh bound cho mọi chi phí AI của cả app, đặc biệt registered Voyage/STT. Giá Voyage, usage và quota **UNKNOWN trong audit này**; không gán giá OpenAI embedding cho Voyage. Công thức embeddings bổ sung là `query_tokens*rate_query + document_tokens*rate_doc`, hoặc theo đơn vị invoice provider nếu khác.

Guest có detached reservation/totals sống qua purge; global liability cộng vào cùng financial lock (`backend/app/ai/accounting.py:61`, `:67`; `backend/app/modules/guests/accounting.py:90`, `:116`), không double count diagnostic `AiUsage`. Guest limiter riêng mặc định global 10/user 1 (`backend/app/core/config.py:148`) và user quota/counters DB (`backend/app/modules/guests/limits.py:265`). Khi positive global budget, `kind_available()` hiện chỉ cho paid guest **AI** với price bound phù hợp, guest cap≤$5; voice/embed bị đóng trong branch đó (`backend/app/modules/guests/pricing.py:115`, `:120`). Vì thế không tuyên bố guest semantic/voice đã hoạt động chỉ vì feature flag=true. Trạng thái guest paid khả dụng local chưa xác minh vì audit không in pricing/secret và không dispatch.

External search đã có fee/reservation riêng được cộng vào liability (`backend/app/ai/search/accounting.py:22`, `:37`, `:50`): web fee $0.01 cộng token reservation; Maps upper $0.50. Mọi phép tính “chat 50” phải ghi search/voice/Voyage/background có bật trong workload hay không, và nếu cùng ngân sách phải hạch toán đủ.

## Các phương án và quyết định đề xuất

1. **Giữ bound $2 và $20:** an toàn tài chính, tối đa 10 ledger open từ ngân sách trống; có thể phục vụ 50 client với refusal/queue rõ ràng nhưng không được quảng bá 50 admitted provider turns. Đây là baseline/rollback.
2. **Enforce token envelope + reservation workflow + giới hạn dispatch chung:** phương án đề xuất. Giữ 20 và atomic guard; admission 50 chỉ khi còn budget đủ, quota/DB đạt. Đổi accounting cần kiểm chứng kỹ lease, children, uncertain, purge và midnight.
3. **Tăng replica/pool hoặc bỏ guard:** không đáp ứng scope/policy/topology hiện tại. Chưa chọn; không triển khai như cách chữa 50.

## Review focus bắt buộc

- Hai request đồng thời ở ranh $20, child reservation và guest purge không được mở lại budget đã chi (P3-I02/I08).
- Cancel/disconnect/restart sau request_started nhưng trước usage không được phát final muộn hoặc refund unknown (P3-I05/I08).
- Một parent với 2 specialist song song không được bypass provider limit hoặc chiếm hết interactive slots (P3-I03/I06).
- 50 SSE có session/auth revalidation mỗi tick; pool timeout không được gây retry storm hoặc ngừng cancel (P3-I04/I11).
- Context/tool output vượt bound trước call thứ 2/3 phải bị chặn trước dispatch; quota có thể không đủ dù chỉ 50 user (P3-I02/I09).

## Task triển khai

Mọi task dưới đây là công việc **tương lai**. MUST là release gate cho claim 50; SHOULD làm sau khi có metrics; OPTIONAL không chặn single-process target. Test ghi tên mới là test **cần bổ sung**, không phải file/test hiện đã có. CODEX không được tự chạy paid/hosted test trong phạm vi audit này.

### P3-I01 — MUST — Chốt cấu hình thực chạy và phát hiện key trùng

**Vấn đề/gốc:** defaults 50 nhưng local effective 10/60 và budget 20; cấu hình ở nhiều lớp dễ gây load report sai.

**Files:** dự kiến sửa `backend/app/core/config.py`, `scripts/verify_local_providers.py`, `deploy/runtime.env.example`, tài liệu vận hành; test mới `backend/tests/test_ai_capacity_config.py`. Không tự sửa `.env` hoặc `.gitignore`.

**Giải pháp/interface:** `ai_capacity_fingerprint(settings) -> dict[str, int | float | bool | str]` chỉ allowlist model/limits/budget/pricing version/flags/topology marker, không URL/key/user IDs; phân biệt defaults, file local, process environment và deployment artifact. Validator đọc key trùng và báo tên key+line, không log value nhạy cảm.

**Phụ thuộc/người làm:** không; CODEX viết validator/report, HUMAN xác nhận deployment fingerprint.

- [ ] Thêm test `test_capacity_fingerprint_never_contains_secrets` và `test_duplicate_capacity_key_is_reported`; chạy thấy fail đúng nguyên nhân.
- [ ] Thêm fingerprint/validator không khởi tạo provider và xuất cấu hình non secret vào load artifacts.
- [ ] Đọc config từ container thực ở môi trường được phép, so với manifest, ghi rõ process count; chưa tự đổi value 50.
- [ ] Chạy test trên và `backend/tests/test_load_settings_baseline.py`; artifact phải nêu global/user/deadline/pool/budget/flags/model/pricing.

**Nghiệm thu:** không còn báo 50 từ class default khi effective 10; secret canary không xuất hiện; duplicate được định vị và runtime overrides được ghi nguồn. **Độ phức tạp:** S, 0.5–1 ngày. **Rủi ro:** log secret/false confidence. **Rollback:** bỏ diagnostics/validator mới, giữ config guard cũ. **Chi phí:**$0 provider; thời gian kỹ thuật.

### P3-I02 — MUST — Reservation dựa trên bound được cưỡng chế, giữ trần $20

**Vấn đề/gốc:** reserve $2/row làm 50 admitted không khả thi; dùng mean cost sẽ phá hard financial bound.

**Files:** `backend/app/ai/accounting.py`, `provider.py`, `usage.py`, `orchestration/workflow.py`, `collaboration/coordinator.py`, `groups/turn.py`, `journal_memory.py`, `modules/guests/accounting.py`, `modules/guests/pricing.py`, `ai/search/accounting.py`; schema/migration mới chỉ nếu cần lưu envelope/version; `backend/tests/test_budget_reservations.py`, `test_guest_global_budget.py`.

**Giải pháp/interface:** `CallEnvelope(model, pricing_version, max_input_tokens, max_output_tokens, remaining_calls, tool_fee_upper_nano)` immutable; `bound_nano(envelope) -> int`; kiểm tra serialized full input ngay trước **mỗi** dispatch. `reserve_workflow(db, workflow_id, envelope) -> Reservation` dùng lock 664201, 1 và integer nano; `allocate_child(db, reservation_id, child_id, bound_nano)` chuyển allocation trong cùng hold, không đếm parent/child hai lần. Lưu call-level dispatch marker/lease; unknown giữ phần bound có thể đã dispatch; chỉ release phần chắc chưa gửi. Giá trị input/output bound phải được chốt sau token audit, không lấy 16 k ví dụ làm sự thật.

**Phụ thuộc/người làm:** P3-I01; CODEX chứng minh thuật toán, HUMAN chốt tác động user-visible của context bound và tài liệu giá; không tự nâng $20.

- [ ] Bổ sung test `test_fifty_bounded_workflows_hold_under_twenty` cho 50 registered parent với children; sum settled+open+uncertain≤20 e 9 trong mọi interleaving. Giữ test legacy reserve 2 để migration/version không refund lịch sử.
- [ ] Bổ sung test `test_tool_expansion_denied_before_next_dispatch`, `test_child_allocation_never_double_counts`, `test_unknown_dispatch_retains_bound`; cap crossing, planner fail, 0 usage, max output và đổi pricing phải fail closed.
- [ ] Cưỡng chế token bound gồm system/history/retrieval/tool returns/schema; nếu không tính chính xác được, dùng upper bound được chứng minh hoặc từ chối trước gửi. Không chỉ đếm ký tự user input.
- [ ] Cài reservation version mới và revalue/import legacy an toàn; kiểm chứng guest purge, search, midnight carryover, expired lease, late settlement cùng lock order.
- [ ] Chạy các suite budget/accounting/recovery/guest trong DB local dùng một lần; xuất ledger invariant report. Nếu 50×full_workflow_bound>remaining thì report `INFEASIBLE_AT_CURRENT_BUDGET`, không nới guard.

**Nghiệm thu:** đủ 50 admission chỉ khi bound thật đủ tiền; call vượt bound=0; total liability không vượt 20 e 9; cả children và phí phụ được tính một lần; crash không refund unknown; không thay quota ngày. **Độ phức tạp:** L, 4–7 ngày. **Rủi ro:** cao, under-reserve/tokenizer mismatch/deadlock/migration. **Rollback:** versioned feature flag trở lại bound $2, ngừng admission mới khi ledger không tương thích; giữ mọi reservation/uncertain đã phát sinh, không xóa ledger. **Chi phí:**$0 với fake providers; paid validation chỉ P3-I09.

### P3-I03 — MUST — Tách parent admission khỏi giới hạn dispatch/fanout

**Vấn đề/gốc:** count running row, local semaphore và actual inflight provider là ba đại lượng khác nhau; child/journal có thể bypass cùng slot.

**Files:** `backend/app/ai/runtime.py`, `provider.py`, `persistence.py`, `orchestration/workflow.py`, `groups/turn.py`, `collaboration/coordinator.py`, `proactive/executor.py`, `journal_memory.py`; test mới `backend/tests/test_ai_dispatch_capacity.py`.

**Giải pháp/interface:** giữ `admission()` DB cho parent/user policy; thêm `ProviderDispatchGate.acquire(workflow_id, lane, deadline)` async context manager quanh từng paid model call và embedding gate riêng. Gate có finite queue, bounded wait, cancellation-aware release, metrics; dùng một runtime-owned gate trong topology một API. Dedicated proactive process cần DB-backed dispatch leases hoặc lane cap riêng đã chứng minh tổng không vượt quota; không giả local semaphore shared qua process.

**Phụ thuộc/người làm:** P3-I01/I02; CODEX.

- [ ] Test 50 parent +2 specialist/workflow +journal/proactive, peak provider không vượt dispatch cap, parent counters không bị cộng child; 51 st có response/queue policy xác định.
- [ ] Thêm queue cap/wait deadline với error retryable và Retry-After phù hợp local policy; không giữ owner/advisory lock hay DB session khi chờ slot/provider.
- [ ] Wire toàn bộ provider paths và child calls; cancel khi đang queue không dispatch, permit không leak, starvation không làm cancel bị chặn.
- [ ] Chạy `test_v3_load.py`, `test_collaboration_load.py` và test dispatch mới, xem counter logical vs HTTP attempts.

**Nghiệm thu:** report `C_turn`, `C_run`, `C_provider` riêng; inflight bound đúng dưới fanout; queue finite; wait tính vào end-to-end deadline; shutdown/cancel peak quay 0. **Độ phức tạp:** L, 3–5 ngày. **Rủi ro:** nested permit deadlock hoặc interactive starvation. **Rollback:** gate về mode observe, giữ admission và financial guard; nếu bound không được bảo đảm, giữ claim 50 chưa đạt. **Chi phí:**$0 offline; không thêm replica.

### P3-I04 — MUST — Metrics đủ để quyết định 50

**Vấn đề/gốc:** `first_progress_ms` được set ngay trước model start sau policy check (`runtime.py:848`), không phải first provider token; hiện log cuối có duration/token/model_requests nhưng thiếu nhiều stage/percentile.

**Files:** `backend/app/ai/runtime.py`, `provider.py`, `core/outbound.py`, `core/streams.py`, `infrastructure/database/connection.py`, `app/main.py`, load scripts; dashboard/alarm plan tại các tài liệu liên quan.

**Giải pháp:** timestamps monotonic cho admission start/commit, queue acquire, memory query, provider start/first raw event/last event, DB publish, final/completed delivered, cancellation observed/settled. Counter low-cardinality theo workflow/lane/outcome; không prompt/memory/token secret và không user ID guest.

**Phụ thuộc/người làm:** P3-I01; CODEX, HUMAN kiểm tra dashboard production nếu cần.

- [ ] Test `test_stage_metrics_are_monotonic_and_content_free` với canary; phân biệt raw-event timing private và rendered-first-content timing.
- [ ] Add pool acquisition percentiles, active and queued dispatch gauges, per-origin financial ceilings, stream refusals, lease fencing and unresolved liabilities.
- [ ] Sampler local mỗi 1 s đo RSS/process, CPU, event-loop lag, pool checkout/wait/timeout, Postgres active/idle-in-transaction, pending jobs/oldest age; capture dispatch peak đủ dày hoặc event-driven counter.
- [ ] Tích hợp artifact có config fingerprint, commit/dirty state, warmup/duration/requested-vs-achieved load; không xuất credential/connection string.

**Nghiệm thu:** mỗi turn phân rã được latency và số call; first progress không gắn tên TTFT; graph chỉ rõ denied vs error vs cancelled; artifact fake được đánh nhãn. **Độ phức tạp:** M, 2–3 ngày. **Rủi ro:** high-cardinality/overhead. **Rollback:** disable detailed sampling, giữ counters/financial state. **Chi phí:**$0 local; ingest/retention cloud chưa định giá và chưa tạo trong audit.

### P3-I05 — MUST — SSE reconnect, disconnect và cancel nhất quán

**Vấn đề/gốc:** backend có durable cursor nhưng `consume()` luôn sequence 0, fetch một lần, không gửi cursor (`frontend/src/api/stream.ts:212`, `:232`); abort reader không gọi cancel endpoint. Chưa có bằng chứng frontend tự resume từ cursor sau network drop.

**Files:** `frontend/src/api/stream.ts`, chat/group API/controller consumers, `backend/app/ai/chat_routes.py`, `groups/routes.py`, `core/streams.py`; `frontend/src/api/stream.test.ts`, `streamReply.test.ts`, `streamOrchestration.test.ts`, `backend/tests/test_ai_events_v2.py`, `test_groups_turn.py`, `test_ai_recovery.py`.

**Giải pháp/interface:** `consume(..., resumeState?: {lastSeq: string, final?: ValidatedReply})`; cursor và pending final thuộc cùng run/protocol. Reconnect GET có cursor, backoff/jitter và finite attempts tới deadline; tuyệt đối không tự POST messages lại. Explicit Stop gọi durable cancel; unmount/disconnect tiếp tục run theo policy đã chọn, hiển thị trạng thái saved reload/ephemeral expired chính xác.

**Phụ thuộc/người làm:** P3-I03/I04; CODEX.

- [ ] Test network drop sau progress/final nhưng trước completed, duplicate/gap/revoked, mọi cursor v 1/v 2/v 3/group, resume khác session/user bị từ chối; completed chỉ render một lần.
- [ ] Thêm bounded reconnect và lưu final pending đúng cursor; tránh resume từ `lastSeq>0` khi parser vẫn kỳ vọng 1 hoặc chưa lưu final.
- [ ] Test đóng 50 stream cùng lúc slot trở 0; Stop đang queue/đang model/đang DB publish không late final, không trả lại uncertain money.
- [ ] Kiểm tra slow reader với final payload maximum; finite connection lifetime/global SSE quota, không giữ DB connection khi client chậm. Giữ validate-before-render/raw token không ra UI.

**Nghiệm thu:** reconnect không duplicate model call/output, mọi slot giải phóng, cancel được settle/fenced, replay saved sau restart rõ `AI_INTERRUPTED` khi chưa xong; ephemeral không hứa resume qua process restart. **Độ phức tạp:** M, 2–4 ngày. **Rủi ro:** cursor/final state mismatch hoặc retry storm. **Rollback:** tắt auto reconnect, quay reload status thủ công; không tự retry POST. **Chi phí:**$0 fake provider.

### P3-I06 — MUST — Fairness/background và chi phí embeddings

**Vấn đề/gốc:** journal auto memory ngoài semaphore, pass memory có thể giữ journal đợi; registered Voyage ngoài $20 ledger, client mới mỗi embed; quota/chi phí background chưa bao phủ bởi phép tính chat.

**Files:** `backend/app/main.py`, `ai/embeddings.py`, `ai/voyage.py`, `ai/journal_memory.py`, `modules/journal/indexing.py`, `modules/journal/retrieval.py`, `jobs/proactive.py`, `modules/guests/pricing.py`; test `test_journal_auto_memory.py`, `test_journal_worker_startup.py`, `test_guest_global_budget.py` và test mới `test_ai_background_fairness.py`.

**Giải pháp:** interactive/background lanes với dispatch caps/queue tuổi rõ; background yielding không đổi consent/user quota. Tạo mapping mọi paid operation→financial authority; ghi riêng Voyage/STT envelope nếu ngân sách 20 được định nghĩa toàn AI, hoặc HUMAN xác nhận phạm vi ngân sách riêng trước khi claim cost. Không tự tắt semantic để số load đẹp.

**Phụ thuộc/người làm:** P3-I02/I03/I04; CODEX; HUMAN chốt phạm vi budget, giá/quotas Voyage/STT từ nguồn chính thức/account.

- [ ] Test 50 interactive cùng journal/proactive backlog lớn; final latency không bị starve, queue không mất job, lease stale không publish, guest không được bypass paid kind guard.
- [ ] Bounded batch/time slice cho mỗi background lane, đo oldest age; re-use bounded Voyage client có close lifecycle và timeout/cancel.
- [ ] Hạch toán registered query/doc embeddings hoặc ghi external separate budget authority rõ ràng; unavailable pricing fail closed cho phạm vi hard cap, giữ fallback đã có.
- [ ] Chạy local `load_proactive.py` baseline/loaded và journal/memory tests; so p95, peak pool, backlog age; không suy ra từ fake sang provider thật.

**Nghiệm thu:** mọi outbound paid call có owner lane/budget/metric; background không làm interactive/cancel timeout; guest semantics giữ nguyên. **Độ phức tạp:** L, 3–5 ngày. **Rủi ro:** starvation ngược, queue retry phí lặp hoặc thay semantics budget. **Rollback:** background cap thấp như hiện tại, giữ ledger/uncertain; disable optimization mới theo flag, không xóa jobs. **Chi phí:**$0 local; provider price/query volume còn UNKNOWN.

### P3-I07 — MUST — Load harness 50×15 phút, không gọi cloud

**Vấn đề/gốc:** script hiện có là burst/scenario, dùng model fake và config override; chưa có duration/rate/mix đúng production budget. Tên file 50 không phải chứng minh sustained concurrency 50.

**Files:** mở rộng primitives từ `scripts/load_chat_memory.py`, `scripts/load_proactive.py`, `backend/tests/chat_load_server.py`; cùng P5-L01 tạo CLI duy nhất `scripts/scale_readiness.py`, fixture `backend/tests/scale_readiness_server.py` và `backend/tests/test_ai_load_contract.py`; artifacts mới ở đường dẫn timestamp không overwrite evidence cũ.

**Giải pháp/interface:** dùng CLI dự kiến `python scripts/scale_readiness.py run --case T4 --manifest <private-json> --output <new-path>` của [P5-L01](07-load-testing-and-benchmark-plan.md). Manifest ghi `users=50`, `concurrency=50`, `duration_seconds=900`, `warmup_seconds=60`, `workers=1`, `profile=bounded-budget20`, `provider=fake`, cùng token/workflow profile và completion distribution. Đây là **CLI chưa tồn tại**, phải implement trước khi chạy. P3 sở hữu fake provider barrier và workflow assertions, P5 sở hữu CLI/manifest/safety/output; không tạo harness thứ hai. Add open-loop offered-rate/drop counter và closed-loop active-turn occupancy, không chỉ số task tạo ra.

**Phụ thuộc/người làm:** P3-I01–I06 và baseline load plan chung; CODEX.

- [ ] Test CLI từ chối URL không phải local disposable `_test`, secrets/real credentials, existing output và workers>1 ở profile release single-process; không đụng project hosted.
- [ ] Tạo 50 identity/session local, seed 1000 user dữ liệu synthetic để đo scale dữ liệu; mô hình delay 6–12 s/success/tool/failure có phân phối và seed, budgets 20 bật.
- [ ] Chạy warmup 60 s rồi 900 s fake provider; tách direct no memory, direct memory+journal, collaboration, orchestration và group, sau đó mixed profile với weight được ghi. Không tuyên bố full mixed nếu chỉ direct pass.
- [ ] Báo requested/achieved occupancy, admitted/completed/rejected/failed/cancelled theo code, calls/turn, logical/HTTP dispatch peak, p50/p95/p99 từng stage, non-AI health, pool/RSS/loop lag/ledger invariant và 90 s drain.

**Tiêu chí dự kiến để chốt cùng tài liệu load chung:** đạt 50 parent active ở plateau profile có đủ remaining budget; mean occupancy≥45/50 ở cửa sổ đo sau warmup, chưa tính warmup/drain; 0 over spend/duplicate paid dispatch/cross-user output/permit leak; unexpected 5xx<1%; pool timeout=0; non-AI p95≤500 ms local; completion p95≤30 s direct, p99≤60 s theo profile bounded; memory/RSS không tăng đơn điệu sau drain. Các threshold latency là proposal/gate, chưa phải SLA hay kết quả đo. Profile budget exhausted đúng policy phải được ghi expected refusal, không trộn vào capacity success; long soak không dùng reset ledger giữa 900 s để giả $20 đủ tiền.

**Độ phức tạp:** M/L, 2–4 ngày. **Rủi ro:** workload quá nhẹ/giữ 50 socket nhưng ít turn. **Rollback:** harness độc lập không ảnh hưởng runtime; giữ toàn bộ evidence và report scope. **Chi phí:**$0 provider/cloud; local CPU/DB.

### P3-I08 — MUST — Fault matrix và invariants tài chính

**Vấn đề/gốc:** existing tests có cancel/recovery/budget nhưng thiếu bằng chứng tích hợp dưới 50 với DB chậm/fanout/stream churn. Không được coi đọc assertion là chạy thành công.

**Files:** `backend/tests/test_ai_recovery.py`, `test_budget_reservations.py`, `test_usage_accounting.py`, `test_sdk_adapter.py`, `test_guest_global_budget.py`, `test_guest_inflight.py`, `test_groups_turn.py`, `test_journal_auto_memory.py`; load harness P3-I07.

**Phụ thuộc/người làm:** P3-I02–I07; CODEX.

- [ ] Chạy fake 429/503/timeout/connect-fail/malformed-usage ở before/after dispatch marker, record calls/success, không tự retry HTTP request có thể đã tới provider.
- [ ] Kill process giữ turn sau request_started; recover chỉ expired lease, interrupted final không replay; simulate stale old worker return sau recovery.
- [ ] Inject DB lock wait/pool timeout lúc admission/publish/terminal và cancellation lặp; final CAS loser không emit output, pending terminal retry không gọi model lại.
- [ ] Race midnight UTC, user/day quota, guest purge, child settle, consent revoke, journal edit/delete, 50 tab disconnect/reconnect, HTTP slow reader. Query liability invariant sau mỗi fault/drain.

**Nghiệm thu:**0 unauthorized/late publish/duplicate dispatch; total authorized liability≤budget; unknown giữ bound; no-dispatch có thể release chắc chắn; no idle-in-transaction do provider wait; cancellable tasks/slots quay 0, terminal retry được đo. **Độ phức tạp:** M/L, 2–4 ngày. **Rủi ro:** test DB destructive, flaky timing. **Rollback:** chỉ fixtures local; kill đúng owned PID, không xóa user data/evidence. **Chi phí:**$0 offline.

### P3-I09 — MUST — HUMAN xác minh quota và duyệt live validation nhỏ

**Vấn đề/gốc:** official model/pricing docs không cho biết project/org quota thực tế; live script hiện cap 12, tạo synthetic nhưng vẫn gọi OpenAI thật.

**Files:** `backend/evals/concurrency_live.py`, `backend/evals/scenarios_live.py`, runbook và evidence mới; không cần sửa cap 12 chỉ để thử 50.

**Phụ thuộc/người làm:** P3-I01–I08, load gates offline và budget remaining report; HUMAN sở hữu quota/spend authorization, CODEX chuẩn bị lệnh/artifact và chỉ chạy khi scope được ủy quyền riêng.

- [ ] HUMAN lấy model/project/org RPM/TPM/shared limits, tier, effective service tier, spend settings và khả năng burst; ghi non secret evidence/time, không copy API key.
- [ ] So demand formula theo actual tokens/turn/call với limits+headroom; ghi UNKNOWN nếu không có access, không suy từ public table.
- [ ] Chốt finite max calls/tokens/$, stop threshold 429/503/timeouts và remaining budget trước mỗi level. Probe 1→2→5→10, tối đa 12 theo script hiện tại; canary small không thay thế test 50×900 s.
- [ ] Nếu cần live 50/sustained, tạo kế hoạch riêng có accounting 20 bật, no hosted DB reset, approvals thực tế và kill switch; không nới script cap hoặc gọi thử trong audit này.

**Nghiệm thu:** quota có nguồn account/header xác thực và còn hạn; real probe report kết quả thật với tokens/$/errors và giới hạn scope; claim 50 live chỉ sau load đúng 50/900 s được cho phép và vượt gates. **Độ phức tạp:** S/M, 0.5–1 ngày chuẩn bị cộng thời gian account. **Rủi ro:** phí/quota/billing hoặc nhầm database hosted. **Rollback:** dừng dispatch mới, drain/settle, hạ về baseline 10, giữ unknown; không tự retry. **Chi phí:** do HUMAN chốt trước; medium kịch bản 50/900 s 10 s turn đã≈$5.40 Standard 1 call hoặc $37.80 với 7 call, nên không mặc định 20 đủ. Probe nhỏ cũng có phí, chưa chạy.

### P3-I10 — SHOULD — Tối ưu transport sau khi đo

**Vấn đề/gốc:** OpenAI keepalive 20 có thể churn khi burst 50; Voyage mỗi call tạo client; max 100 không đồng nghĩa provider cap 100.

**Files:** `backend/app/core/outbound.py`, `ai/provider.py`, `ai/voyage.py`, `app/main.py`, `backend/tests/test_sdk_adapter.py`, `test_embeddings.py`.

**Phụ thuộc/người làm:** P3-I03/I04/I06; CODEX.

- [ ] Measure fake local socket reuse/connect latency/transport queue; thêm `test_transport_clients_close_on_shutdown` và cancellation-with-pooled-connection.
- [ ] Điều chỉnh keepalive/pool chỉ từ peak dispatch+lane accounting, share client lifecycle; giữ max_retries 0 và transport connect-only retry hiện tại trừ thay đổi được chứng minh riêng.
- [ ] So baseline vs thay đổi ở 50, verify shutdown không socket/task leak.

**Nghiệm thu:** giảm connect/pool wait có sốđo; không double dispatch hay thay pricing/retry semantics; bounded connections. **Độ phức tạp:** S/M, 1–2 ngày. **Rủi ro:** stale connection/file descriptor pressure. **Rollback:** trả limits/client factory cũ. **Chi phí:**$0 local; không mua capacity.

### P3-I11 — SHOULD — Giảm polling/lock pressure có kiểm chứng

**Vấn đề/gốc:**50 saved SSE+policy monitor có thể tạo≈300 transaction/s trước queries/tool writes; pool 7 là intentional connection budget, cần tối ưu query trước tăng pool.

**Files:** `backend/app/ai/chat_routes.py`, `ai/persistence.py`, `ai/runtime.py`, `core/streams.py`, group routes, DB query indexes theo audit DB riêng.

**Phụ thuộc/người làm:** P3-I04/I07, DB plan; CODEX.

- [ ] Lấy query count/latency/lock wait và explain ở DB synthetic 1000 users; xác định expensive auth/read/recovery/receipt queries.
- [ ] Dùng local wake/event cho active same-process SSE, periodic durable/session revalidation vẫn bounded; poll fallback/reconnect giữ durable cursor. Chỉ cân nhắc notification/shared bus khi có nhu cầu multi-process, không bắt buộc Redis cho target 1 process.
- [ ] Verify revoke/cancel staleness không tệ hơn policy hiện tại, saved reply atomic, slow reader không giữ session; compare pool wait/RPS/latency.

**Nghiệm thu:** giảm DB round trips/turn có sốđo; 0 pool timeout trong profile 50; không đánh đổi auth/consent freshness hoặc durable recovery; pool tổng vẫn trong approved role budget đã xác minh. **Độ phức tạp:** M, 2–3 ngày. **Rủi ro:** notification lost/privacy stale. **Rollback:** về periodic polling cũ; không thay ledger. **Chi phí:**$0 local; chưa thêm hạ tầng.

### P3-I12 — OPTIONAL — Multi-process sau single-process gate

**Vấn đề/gốc:** ephemeral context/run/event và stream slots local; admission DB global đã tồn tại nhưng chưa đủ hỗ trợ replicas.

**Files:** `backend/app/ai/store.py`, `runtime.py`, `chat_routes.py`, `core/streams.py`, `deploy/README.md`, deployment config và DB/queue architecture doc riêng.

**Phụ thuộc/người làm:** toàn bộ MUST đã đạt; HUMAN quyết định có cần topology mới; CODEX chỉ lập thiết kế khi được giao.

- [ ] Thiết kế shared ephemeral state/TTL/ownership, global SSE/dispatch leases, routing/fencing và rolling upgrade compatibility, không dựa sticky sessions làm financial authority.
- [ ] Fault test 2 process/rolling deploy với query routing ngẫu nhiên, policy revocation và 0 provider replay; verify connection demand `7*processes + worker + ops` trong role limit hiện tại.
- [ ] Chỉ đổi tài liệu supported topology sau khi có evidence, không dùng test fixture workers 2 cũ làm production approval.

**Nghiệm thu:** cùng một run/cursor/auth/cancel đúng qua mọi process; fail over không replay provider; shared budgets/slots không nhân bản. **Độ phức tạp:** L/XL, 5–10 ngày+infrastructure. **Rủi ro:** cao, privacy/state partition/cost. **Rollback:**1 API worker/replica theo baseline. **Chi phí:**hạ tầng thêm UNKNOWN, cần estimate riêng; target 50 hiện không đòi multi-process.

## Tái sử dụng test và lệnh: giới hạn phải giữ

| Công cụ hiện có | Giá trị tái sử dụng | Giới hạn/chú ý |
| --- | --- | --- |
| `scripts/load_chat_memory.py` |50 synthetic user, actual HTTP server, saved chat/memory/SSE/idempotency/cancel/crash scenarios, counters peak/pool/RSS (`:104`, `:589`, `:705`) |users 2..50, default workers 2, không duration (`:774`); fixture `ALL_FEATURES_OFF`, global 50, pool mặc định 5+5, fake model/Voyage (`backend/tests/chat_load_server.py:150`). Không chứng minh budget 20/multi-agent/provider latency. |
| `scripts/load_proactive.py` | Baseline/worker p95/p99, queue lag/connection/RSS, fake model, process riêng (`:1`, `:153`, `:169`) |reset/drop_all local (`:69`), no duration; overrides global 50/daily quota 1000 (`:174`), default budget 0. Cần thêm profile 20/mixed 50, không coi nó đã cover journal/guest/orchestration. |
| `backend/evals/concurrency_live.py` | Probe billable model latency/error ở levels nhỏ, artifact refuses overwrite (`:105`, `:112`) |cap 12, `--live` bắt buộc; Settings không đưa budget 20, dùng default 0 (`:40`); chuẩn bịDB qua helper. **Không chạy trong audit** và không đổi thành 50. |
| `scripts/provision_auth_test_accounts.py` |Review-only không flag không network (`:131`) |Chỉ 2 tài khoản A/B (`:1`, `:30`), hardcoded hosted project URL, create/configure gọi external Auth. Không phải tool seed 50; không sửa loop A/B để tạo hàng loạt. |
| `backend/tests/performance/benchmark.py` |Pattern local disposable DB/ASGI và evidence scope |Matching benchmark 5 sequential reads, AI disabled (`:24`, `:110`, `:112`); không phải AI/SSE capacity suite. |
| `backend/tests/test_budget_reservations.py`, `test_usage_accounting.py`, `test_ai_recovery.py`, `test_sdk_adapter.py` |Invariants atomic ledger, unknown usage, lease/finalization, three-call cap, cancellation/drain và connect-only retries |Fixture/unit/integration có assertion đúng không chứng minh sustained 50 hoặc hosted reliability; audit chỉ đọc. |
| `backend/tests/test_v3_load.py`, `test_collaboration_load.py` |Latency overhead từng workflow với synthetic model |Không đại diện account quota/paid latency; cần giữ behavior checks trong matrix 50 mới. |

Lệnh mẫu **dành cho lần thực thi được giao sau này**, PowerShell từ repository root, chỉ dùng disposable PostgreSQL localhost database có suffix `_test` do executor chuẩn bị. Các lệnh load hiện có reset dữ liệu test; không gán `TEST_DATABASE_URL` sang project người dùng hoặc hosted. `TEST_DATABASE_URL` phải set trong session trước; không ghi credential vào artifact. Không có lệnh nào sau đây đã được chạy trong audit.

```powershell
# Existing burst baseline: một worker, pool5+2; vẫn fake và chưa budget20/15phút.
$env:MOODPRINT_LOAD_POOL_SIZE = '5'
$env:MOODPRINT_LOAD_POOL_OVERFLOW = '2'
./backend/.venv/Scripts/python scripts/load_chat_memory.py --users 50 --workers 1 --model-delay 1.5 --output evidence/scale-readiness/chat-memory-local-new.json

# Existing worker-interference scenario: finite turns, không phải900s soak.
./backend/.venv/Scripts/python scripts/load_proactive.py --users 100 --chat 50 --turns 3 --concurrency 1 --worker-pool 2 --model-delay 1.5

# Run từ thư mục backend, không gọi cloud; Postgres fixtures phải trỏ local disposable DB.
./.venv/Scripts/python -m pytest tests/test_budget_reservations.py tests/test_usage_accounting.py tests/test_ai_recovery.py tests/test_sdk_adapter.py tests/test_guest_global_budget.py -q
./.venv/Scripts/python -m pytest tests/test_ai_events_v2.py tests/test_collaboration_dto.py tests/test_groups_turn.py tests/test_v3_load.py tests/test_collaboration_load.py tests/test_journal_auto_memory.py -q
```

Load output đường dẫn ví dụ phải đổi sang tên mới nếu đã tồn tại; không ghi đè evidence người dùng. CLI mới 900 s ở P3-I07 phải được implement/test trước; không copy lệnh chưa tồn tại rồi ghi PASS. Frontend chạy bằng command test được khai báo ở `frontend/package.json` sau khi kiểm tra script/runner, chọn stream suites; không tự cài dependencies hay giả lệnh từ stack đoán.

## Gate bàn giao và quan hệ với kế hoạch tổng thể

Hoàn thành audit có nghĩa tài liệu có evidence/UNKNOWN/task cards; không có nghĩa hệ thống đạt 50. Release claim 50 chỉ khi đủ fingerprint, money invariant, exact achieved active-parent plateau, fault results, resource metrics và quota evidence. Báo riêng **offline synthetic 50**, **live canary≤12**, **live sustained 50 nếu về sau được cho phép**; không nâng một cấp bằng kết quả của cấp khác.

Các hợp đồng liên tài liệu:00 định nghĩa mục tiêu/unknown và go/no-go; 02 xác nhận cấu hình/deployment baseline; 07 chứa strategy load/evidence; 08 hạch toán chi phí/ngân sách; 09 lập thứ tự task/dependencies; 10 là prompt thực thi của CODEX. Các đường dẫn chính xác sẽ được đồng bộ với index của bộ tài liệu trước bàn giao.
