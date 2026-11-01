# 03 — Quyết định kiến trúc (ADR)

Mỗi ADR có trạng thái **Đề xuất (mặc định đã chọn)** trừ khi ghi "cần owner duyệt". Dữ kiện nền ở [01](01-current-codebase-audit.md), SDK ở [02](02-openai-agents-sdk-research.md). Tên migration dùng ký hiệu `M-P1-A`, `M-P1-B`, `M-P2-A`; số Alembic thực tế được gán lúc triển khai (dự kiến 0021, 0022, 0023 nếu không có migration khác chen vào).

| ID | Chủ đề | Quyết định ngắn |
| --- | --- | --- |
| ADR-01 | Lưu nhiều bubble | Mỗi bubble là một row `ai_messages`; unique `(run_id, actor, part_index)` |
| ADR-02 | Version/sequence | Giữ bất biến `version == max(sequence)`; mỗi bubble chiếm một sequence |
| ADR-03 | Tiến hóa SSE | Thêm `ai-events-v2` theo `?protocol=2`; v1 vẫn phục vụ client cũ bằng bản ghép |
| ADR-04 | Danh tính run chủ động | Principal hệ thống `proactive_schedule`; `ai_runs.origin='proactive'`; không có session, không có tin nhắn giả của người dùng |
| ADR-05 | Scheduler | ~~Worker trong process API~~ → service Compose riêng `proactive` ([96 HD-01](96-architecture-hardening-review.md#2-quyết-định-kiến-trúc-thay-đổi-so-với-bộ-kế-hoạch)), hàng đợi bảng PostgreSQL; không pg_cron/pgmq ở Phase 1 |
| ADR-06 | Job queue & claim | `ai_proactive_jobs` lease + `SKIP LOCKED` + unique `(user, bot, slot, local_date)` |
| ADR-07 | Vị trí tin chủ động | Ghép vào hội thoại đã lưu gần nhất của bot nếu đủ điều kiện, nếu không tạo hội thoại mới |
| ADR-08 | Context policy cho tin chủ động | `proactive-text-v1` / `proactive-journal-v1`; tin journal chỉ vào context sau khi **revalidate provenance** |
| ADR-09 | Điều phối đa agent | Code-driven, coordinator ẩn; không handoff, không `Agent.as_tool()` nguyên bản |
| ADR-10 | Uỷ quyền liên agent | Ma trận cạnh cố định + quyền chia sẻ opt-in theo cạnh + chỉ trường enum/đã kiểm |
| ADR-11 | Lưu sự kiện cộng tác | `ai_collaborations` content-free (digest), run con riêng; tóm tắt hiển thị render từ template |
| ADR-12 | Trạng thái chưa đọc | `ai_conversation_reads.last_read_sequence`; đếm theo **lượt giao** (run), không theo bubble |
| ADR-13 | OD-01…OD-07 | Owner ủy quyền; giữ mặc định sau khi so sánh phương án (bảng ở cuối tài liệu) |

---

## ADR-01 — Lưu nhiều bubble cho một run

**Bối cảnh.** `ai_messages` unique `(run_id, actor)` ([ai/models.py:53](../../../backend/app/ai/models.py#L53)) chỉ cho một tin bot/run. P1.1 cần 1–4 bubble.

**Phương án.**
1. Một row, `parts jsonb` chứa danh sách bubble.
2. Nhiều row, thêm `part_index`/`part_count`, đổi unique thành `(run_id, actor, part_index)`.
3. Bảng con `ai_message_parts`.

**Quyết định.** Phương án 2.

**Lý do.** Phân trang, sao chép, đánh dấu đã đọc, export và context đều đã làm việc theo row + `sequence`; mỗi bubble cần `id` riêng để làm cursor (`before=<message id>`) và khóa React. Phương án 1 bắt client cũ hiểu cấu trúc mới và phá giới hạn `text varchar(6000)`; phương án 3 thêm join ở mọi truy vấn.

**Bị loại.** (1) phá tương thích client và cursor; (3) phức tạp không cần thiết.

**Rủi ro.** Trang lịch sử có thể cắt giữa nhóm bubble → xử lý ở [phase-1/02 §6](phase-1/02-multi-message-contract.md). Code cũ dùng `scalar(select … where run_id, actor='bot')` ([chat_routes.py:522-526](../../../backend/app/ai/chat_routes.py#L522)) sẽ chỉ lấy một row.

**Tương thích.** Cột mới có `server_default` (0 và 1) → row cũ hợp lệ, image cũ chèn được (không ghi cột mới). Image cũ đọc lịch sử nhiều bubble vẫn hiển thị thành nhiều tin riêng.

**Kiểm chứng.** Migration test (constraint swap), test persist N bubble, test cursor giữa nhóm, test image cũ (insert không có cột mới).

**Rollback.** Code rollback an toàn. **Không** khôi phục unique cũ sau khi có dữ liệu nhiều bubble (sẽ fail); giữ forward-only như các migration 0015–0020.

## ADR-02 — Version và sequence của hội thoại

**Bối cảnh.** `version` là precondition gửi tin và bằng `max(sequence)` ([01 §4](01-current-codebase-audit.md)).

**Phương án.** (a) Một run tăng version 1 lần, bubble dùng `sequence` con; (b) mỗi bubble tăng version 1 và nhận sequence liên tiếp.

**Quyết định.** (b). Run N bubble: `version += N`, bubble i có `sequence = old_version + 1 + i`, tất cả trong một transaction giữ `SELECT … FOR UPDATE` trên `ai_conversations`.

**Lý do.** Không phải đổi kiểu `sequence`, unique `(conversation_id, sequence)` giữ nguyên, phân trang `sequence < cursor` giữ nguyên.

**Rủi ro.** Tin chủ động làm version tăng trong khi người dùng đang mở hội thoại → lần gửi tiếp nhận `409 STALE_VERSION`. Xử lý: frontend tải lại và giữ bản nháp ([phase-1/06 §7](phase-1/06-frontend-ux-and-notifications.md)); worker hoãn giao khi hội thoại đang có run hoặc vừa hoạt động ([ADR-07](#adr-07--vị-trí-tin-chủ-động)).

**Tương thích / Rollback.** Không đổi schema version. Rollback không ảnh hưởng.

**Kiểm chứng.** Property test: sau mọi chuỗi thao tác, `version == max(sequence)` và sequence liên tục.

## ADR-03 — Tiến hóa giao thức SSE

**Bối cảnh.** `consumeAIEvents` từ chối mọi khóa lạ trong `final` ([stream.ts:110-121](../../../frontend/src/api/stream.ts#L110)). Tab cũ còn mở trong lúc deploy sẽ chạy JS cũ với server mới.

**Phương án.** (1) Đổi `final` của v1; (2) thêm event mới trong v1; (3) envelope `ai-events-v2` chọn bằng query `?protocol=2`; (4) stream từng bubble ngay khi model sinh.

**Quyết định.** (3). Server: không có `protocol=2` → v1, `final.data = {text: join(bubbles, "\n\n"), cards: concat(cards)}`; có → v2, `final.data = {messages: [...]}`. Vẫn 5 loại event, persistent replay vẫn seq 1–3.

**Lý do.** Client cũ không vỡ; không cần feature negotiation phức tạp vì SPA và API cùng image. Phương án (4) bị loại vì structured output chỉ hợp lệ khi đủ JSON và guardrail chạy trên output cuối — hiện bubble sớm là hiện nội dung chưa kiểm.

**Rủi ro.** Tổng text ghép phải ≤ 6.000 ký tự (client v1 kiểm `Array.from(text).length`) → giới hạn tổng 5.900 ký tự cho mọi bubble.

**Tương thích.** v1 giữ nguyên byte-for-byte cho run một bubble.

**Kiểm chứng.** Contract test cả hai version; test client v1 với run 3 bubble.

**Rollback.** Rollback frontend → client v1 → server vẫn phục vụ v1.

## ADR-04 — Danh tính run chủ động (server-originated)

**Bối cảnh.** Run người dùng gắn `Actor(user_id, session_id, auth_version)`; `check()` đòi session ([runtime.py:291-317](../../../backend/app/ai/runtime.py#L291)). Tin chủ động phát sinh khi người dùng vắng mặt.

**Phương án.** (1) Dựng tin nhắn người dùng giả ("Chào buổi sáng") rồi chạy pipeline chat; (2) dùng session gần nhất của người dùng; (3) principal hệ thống riêng với ủy quyền bền vững (opt-in lịch).

**Quyết định.** (3). `ProactivePrincipal(user_id, schedule_id, schedule_version, settings_version, job_id)`. Ủy quyền = lịch đang bật + settings version khớp + tài khoản `registered`, `status='active'`, không `deletion_pending`, không `suspended`, `age_band ∈ {teen, adult}`, AI khả dụng, `last_seen_at` trong `PROACTIVE_INACTIVE_DAYS`. Lưu vết: `ai_runs.origin='proactive'`, `ai_runs.proactive_slot ∈ {morning, evening}`, `ai_turns.origin='proactive'`, `ai_turns.session_id = NULL` (CHECK: chỉ được NULL khi `origin='proactive'`), `client_message_id = job_id`.

**Lý do.** (1) là "fake user message" bị cấm và làm sai transcript; (2) mượn session là bypass session security và hỏng khi session hết hạn.

**Bị loại.** (1), (2).

**Rủi ro.** Một đường quyền mới → test ma trận đủ trường hợp ([phase-1/09](phase-1/09-testing-and-acceptance.md)). Proactive không bao giờ được cấp tool ghi (`propose_memory`) vì không có người xem/duyệt tại thời điểm chạy.

**Tương thích.** Cột mới có default `'user'`; `session_id` chuyển nullable (metadata change) cùng CHECK.

**Kiểm chứng.** Test: guest/under16/deleted/suspended/inactive → `skipped`; không có row `ai_messages(actor='self')` cho run proactive.

**Rollback.** Tắt `PROACTIVE_WORKER_ENABLED`; run proactive đã giao vẫn hiển thị với image cũ (image cũ bỏ qua cột mới).

## ADR-05 — Chọn công nghệ scheduler

> **Cập nhật 31/10/2026 (gia cố kiến trúc):** phần *vị trí chạy* của quyết định này được thay bằng [HD-01](96-architecture-hardening-review.md#2-quyết-định-kiến-trúc-thay-đổi-so-với-bộ-kế-hoạch): worker chạy trong **service Compose riêng `proactive`** (cùng image, `python -m app.jobs.proactive`), không chạy trong lifespan API. Hàng đợi bảng PostgreSQL, không pg_cron/pgmq, claim/lease giữ nguyên. Lý do: owner ưu tiên độ trễ/ổn định hơn tối thiểu chi phí; ngân sách kết nối vẫn đạt nhờ pool worker 2+0 ([96 §4](96-architecture-hardening-review.md#4-ngân-sách-kết-nối-supabase)).

**Bối cảnh.** Một EC2, một container API (768 MB, 1,5 CPU), một uvicorn worker, pool 5+2, role limit 20 ([01 §10](01-current-codebase-audit.md)). Đã có 4 vòng lặp nền trong lifespan. pg_cron/pgmq có sẵn nhưng chưa cài. AWS không kiểm được trong phiên.

**Ma trận quyết định** (điểm 1–5, cao = tốt):

| Tiêu chí (trọng số) | A. Worker trong process API + bảng queue | B. Container worker riêng (cùng image) | C. Supabase Cron (pg_cron) enqueue + worker Python | D. EC2 systemd timer gọi CLI | E. pgmq + worker | F. Edge Function + Cron |
| --- | --- | --- | --- | --- | --- | --- |
| Đơn giản vận hành (3) | 5 | 3 | 2 | 2 | 2 | 1 |
| Không thêm kết nối DB (3) | 5 | 2 (vượt headroom) | 4 | 4 | 4 | 3 |
| Bền vững khi restart (3) | 4 | 4 | 5 | 4 | 5 | 4 |
| Kiểm thử local/CI (2) | 5 | 4 | 2 (image test không có pg_cron) | 2 | 2 | 1 |
| Cách ly khỏi web (2) | 2 | 5 | 3 | 4 | 3 | 5 |
| Phù hợp mẫu codebase (2) | 5 | 4 | 2 | 2 | 2 | 1 |
| Cần duyệt hạ tầng/DDL hosted mới (2) | 5 | 3 | 1 | 2 | 1 | 1 |
| **Tổng có trọng số** (tối đa 85) | **76** | 59 | 49 | 50 | 49 | 40 |

**Quyết định.** A. Module `app/jobs/proactive.py` cung cấp `proactive_tick(app)`; lifespan thêm vòng lặp `proactive_worker` (60 s) chỉ khi `PROACTIVE_WORKER_ENABLED=true`. Mã được viết để có thể chạy như entrypoint riêng (`python -m app.jobs.proactive`) sau này mà không đổi logic.

**Lý do.** Không thêm kết nối (dùng chung pool; concurrency 1–2), khớp mẫu `embedding_worker`; PostgreSQL là nguồn sự thật nên restart/chồng deploy an toàn. Tải dự kiến rất nhỏ ([91](91-performance-cost-and-capacity.md)).

**Bị loại.** B: thêm 2+ kết nối × 2 process chồng → headroom < `MINIMUM_HEADROOM=4` ([budget.py](../../../backend/app/infrastructure/database/budget.py)); cần đổi `deploy.sh`. C/E: DDL extension hosted cần duyệt, CI image không có pg_cron, vẫn cần worker Python. D: cấu hình host ngoài CI. F: cần credential DB/Deno ngoài BFF.

**Rủi ro.** Model call chia event loop với request web → giới hạn `PROACTIVE_WORKER_CONCURRENCY` (mặc định 1), tick dùng `asyncio.timeout`, jitter phút giao trong khoảng ±0 (giờ do người dùng chọn) nhưng xử lý tuần tự.

**Kiểm chứng.** Load test: 200 lịch đến hạn cùng phút + 20 người chat đồng thời; p95 latency chat không tăng quá 10 %.

**Rollback.** Đặt `PROACTIVE_WORKER_ENABLED=false` (không cần migration).

## ADR-06 — Hàng đợi job và claim

**Quyết định.**
- Bảng `ai_proactive_jobs` với unique `(user_id, bot_id, slot, local_date)` → chống tạo trùng kể cả khi lịch bị xóa/tạo lại.
- Materialize: `ai_proactive_schedules.next_due_at` (timestamptz) là con trỏ bền; tick chọn lịch `enabled and next_due_at <= now()` `FOR UPDATE SKIP LOCKED LIMIT 100`, `INSERT … ON CONFLICT DO NOTHING`, rồi tính `next_due_at` kế tiếp trong cùng transaction.
- Claim: giống `process_embedding_jobs` — chỉ khóa row job trong transaction ngắn, đặt `status='running'`, `lease_token`, `lease_until = now()+90s`, `attempts += 1`; sau đó mới khóa owner (thứ tự owner → job trong transaction publish).
- Publish: một transaction giữ owner lock → job lock (kiểm `lease_token`) → conversation lock; ghi run/turn/usage/messages/sources và `status='delivered'` cùng lúc ⇒ **hiển thị đúng một lần**.

**Bị loại.** Advisory lock theo user (không bền khi crash); pgmq (xem ADR-05).

**Rủi ro.** Crash sau model call trước commit → chạy lại (tốn thêm một lần gọi model, tối đa `PROACTIVE_MAX_ATTEMPTS=3`). Chấp nhận vì chi phí rất nhỏ và đúng nguyên tắc "không replay ngầm sau khi đã hiển thị".

**Kiểm chứng.** Test hai worker claim song song, test crash giữa các bước, test lease hết hạn reclaim.

**Rollback.** Job còn `pending` sẽ hết hạn (`expires_at`) và bị đánh `skipped(expired)` khi bật lại.

## ADR-07 — Vị trí tin chủ động

**Bối cảnh.** Client tự mở hội thoại mới nhất theo `updated_at` của bot ([RealApp.tsx:1273-1291](../../../frontend/src/features/real/RealApp.tsx#L1273)). Hội thoại hết hạn cố định 30 ngày sau khi tạo. Tối đa 500 hội thoại đã lưu/người dùng.

**Phương án.** (1) Luôn tạo hội thoại mới mỗi lần; (2) một thread "Lời hỏi thăm" cố định mỗi bot; (3) ghép vào hội thoại đã lưu gần nhất nếu đủ điều kiện, nếu không tạo mới.

**Quyết định (cần owner xác nhận, mặc định đã chọn).** (3). Đủ điều kiện = persistent, chưa hết hạn và còn ≥ 48 giờ, không có run `running`, không có tin `self` trong 10 phút gần nhất. Nếu có run hoặc tin vừa gửi → hoãn 5 phút (tối đa tới `expires_at`), hết hạn → `skipped(active_chat)` vì người dùng đang trò chuyện. Nếu không có hội thoại phù hợp → tạo mới, tiêu đề `"{Tên bot} · Buổi sáng 31/10"`.

**Lý do.** (1) làm phình lịch sử (≤10 thread/ngày); (2) thread vô hạn trái với retention 30 ngày; (3) giữ cảm giác "một cuộc trò chuyện tiếp diễn" như ứng dụng nhắn tin.

**Rủi ro.** Xen vào hội thoại cũ có thể lạc đề → nội dung proactive **không đọc transcript cũ** (ADR-08), nhãn "Lời hỏi thăm buổi sáng" phân biệt rõ.

**Kiểm chứng.** Test các nhánh chọn hội thoại; E2E hội thoại đang mở nhận tin mới.

**Rollback.** Chỉ là logic chọn; đổi sang (1) không cần migration.

## ADR-08 — Context policy cho tin chủ động

**Bối cảnh.** `model_messages()` cắt tại stamp lạ; `journal-turn-v1` chỉ sống trong run hiện tại ([context.py:46-71](../../../backend/app/ai/context.py#L46)). Nếu áp nguyên quy tắc journal, câu trả lời của người dùng cho lời gợi ý buổi sáng sẽ mất toàn bộ ngữ cảnh.

**Quyết định.**
- Input sinh tin chủ động **không** gồm transcript cũ; chỉ dữ liệu có cấu trúc được phép (persona, khung giờ, ngày, dữ liệu persona-specific).
- Stamp mới: `proactive-text-v1` (không dùng dữ liệu riêng) xử lý như `text-v1`; `proactive-journal-v1` (dùng nhật ký) chỉ được đưa vào context ở lượt sau nếu **revalidate** thành công dưới owner lock: mọi row `ai_message_sources` của run còn đúng revision, `status='saved'`, trong cửa sổ 90 ngày, `journal_context_enabled` còn bật với cùng `journal_context_version`, và `data_version` khớp. Chỉ áp dụng cho tin proactive-journal **mới nhất** trong 36 giờ.
- Lượt người dùng dùng context có tin proactive-journal được stamp `journal-turn-v1` (fail closed cho lượt sau nữa).

**Lý do.** Provenance nằm trong DB (không suy từ văn bản), revocation vẫn cắt ngay (data_version + consent version), continuity được giữ cho trường hợp phổ biến nhất (trả lời ngay lời gợi ý).

**Bị loại.** Giữ nguyên quy tắc journal (UX vỡ); lưu "tóm tắt an toàn" (tạo dữ liệu dẫn xuất mới).

**Rủi ro.** Thêm truy vấn ở đầu `drive()` → chỉ khi tin cuối là proactive-journal. **Giới hạn đã biết:** vì lượt trả lời đầu tiên được stamp `journal-turn-v1`, từ lượt thứ hai trở đi context lại bị cắt tại lượt đó (đúng hành vi fail-closed hiện có của chat có đọc nhật ký). Continuity được giữ cho **một** lượt trả lời — trường hợp phổ biến nhất ("ok mình thử").

**Kiểm chứng.** Test revalidate: sửa/xóa entry, tắt consent, đổi data_version → tin bị loại khỏi context.

**Rollback.** Bỏ policy khỏi tập hợp nhận diện → fail closed (an toàn).

## ADR-09 — Mẫu điều phối đa agent (Phase 2)

**Quyết định.** Code-driven orchestration: `CollaborationCoordinator` là **lớp định tuyến ẩn ở backend**, không phải agent, không phải trợ lý thứ sáu. Luật xác định (R1–R4) quyết định khi nào hỏi specialist; specialist chạy `Runner.run` riêng với `SpecialistContext` tối thiểu, input/output Pydantic, `max_turns ≤ 2`, timeout 8 s, run con + usage riêng. Primary nhận kết quả như dữ liệu có cấu trúc. So sánh đầy đủ ở [phase-2/02](phase-2/02-orchestration-architecture.md).

**Bị loại.** Handoff (chuyển quyền sở hữu câu trả lời, mặc định chuyển toàn bộ lịch sử); `Agent.as_tool()` nguyên bản (chia sẻ context cha, hooks None, max_turns 10, vượt CHECK `ai_usage`); hybrid "model tự gọi tool hỏi bot khác" bị hoãn vì khó dự đoán chi phí và khó giải thích.

**Rollback.** `AI_COLLABORATION_ENABLED=false` → primary chạy một mình như Phase 1.

## ADR-10 — Uỷ quyền liên agent

**Quyết định.** Ma trận cạnh **tĩnh trong code** (`collaboration/policy.py`), mỗi cạnh có: requester, specialist, purpose, schema input (chỉ enum/số có giới hạn), schema output, nguồn dữ liệu specialist được đọc, quyền chia sẻ cần có (`ai_sharing_permissions`, mặc định tắt), giới hạn ngày. Kiểm quyền ba lần: trước khi tạo request, trước khi specialist đọc dữ liệu, trước khi publish câu trả lời. Cầu Nối không có cạnh nhận dữ liệu riêng tư. Chi tiết [phase-2/03](phase-2/03-agent-communication-and-consent.md).

## ADR-11 — Lưu sự kiện cộng tác

**Quyết định.** `ai_collaborations` lưu metadata content-free: cạnh, rule, trạng thái, version quyền/data, `input_digest`/`output_digest` (SHA-256 của JSON chuẩn hóa), run con. **Không lưu nội dung** request/response. Câu tóm tắt hiển thị ("Nhịp đã gợi ý… Rủ Rê đã dựa vào đó…") được backend render từ template theo `(edge, status)` và chỉ gắn vào tin khi receipt `completed` **và** kết quả đã được đưa vào input của primary. LLM không bao giờ viết câu tóm tắt cộng tác.

## ADR-12 — Trạng thái chưa đọc

**Quyết định.** `ai_conversation_reads(conversation_id, user_id, last_read_sequence)` tăng đơn điệu (`GREATEST`). Unread = số **run proactive đã giao** có bubble đầu `sequence > last_read_sequence` trong hội thoại còn hạn. Một lượt giao 3 bubble = 1 thông báo. Không có preview nội dung ngoài hội thoại. Chi tiết [phase-1/05 §4](phase-1/05-backend-api-and-agent-runtime.md).

## ADR-13 — Quyết định OD-01…OD-07 (owner ủy quyền, 31/10/2026)

**Bối cảnh.** Owner ủy quyền tự quyết OD-01…OD-07 ([94 §4](94-dependencies-risks-and-open-decisions.md)) theo thứ tự ưu tiên: trải nghiệm, độ trễ, độ tin cậy, quyền riêng tư, accessibility, bảo trì, chi phí. Mặc định là điểm xuất phát, không phải ràng buộc.

| ID | Phương án đã cân nhắc | Quyết định | Lý do |
| --- | --- | --- | --- |
| OD-01 | (a) hội thoại đã lưu gần nhất còn ≥ 48 h, nếu không tạo mới; (b) luôn tạo mới; (c) một hội thoại "Lời hỏi thăm" cố định | **(a)** | Giống ứng dụng nhắn tin: một luồng liên tục với mỗi trợ lý, danh sách lịch sử không phình thêm 1–4 mục/ngày như (b); người dùng trả lời ngay trong ngữ cảnh. (c) tách lời hỏi thăm khỏi nơi người dùng thật sự trò chuyện. Chống xung đột: hoãn khi hội thoại có run hoặc tin người dùng < 10 phút |
| OD-02 | Cap 2/4/6; khung rộng hơn (04:00–12:00, 16:00–23:00); bước 5/15/30 phút | **4/ngày; sáng 05:00–11:30, tối 17:00–22:30; bước 15 phút** | 4 = đủ cho sáng + tối của hai trợ lý mà không thành "spam"; khung đã có CHECK trong 0022 (không cần migration); bước 15 phút cho danh sách chọn ngắn (≤ 27 lựa chọn) dễ dùng với screen reader |
| OD-03 | Chặn hoàn toàn 16–17; cho phép có giới hạn | **Cho phép trừ Cầu Nối; tối ≤ 21:00; giờ yên lặng mặc định 21:30–07:00** | Cầu Nối đã chỉ dành cho adult ([security.py](../../../backend/app/core/security.py) `assert_purpose MATCH`); các trợ lý khác đang phục vụ teen trong chat thường nên chặn lời hỏi thăm không giảm rủi ro mà làm giảm giá trị. Giới hạn buổi tối + lớp prompt `PROACTIVE_TEEN` |
| OD-04 | Opt-in mặc định tắt; opt-out mặc định bật; không có tính năng | **Opt-in mặc định tắt**, văn bản [phase-1/06 §9](phase-1/06-frontend-ux-and-notifications.md) gắn `policy_version = proactive-v1`; tắt có hiệu lực ngay (tăng `journal_context_version` + `data_version`) | Đọc nhật ký là dữ liệu nhạy cảm nhất; không suy diễn consent. Không mở rộng quyền dữ liệu so với hiện trạng (chat Nhịp đã đọc nhật ký khi người dùng hỏi) |
| OD-05 | 7/14/30 ngày; auto-pause 2/3/5 lời | **14 ngày không hoạt động → bỏ qua; auto-pause sau 3 lời liên tiếp chưa mở của cùng trợ lý** | 14 ngày đủ cho kỳ nghỉ ngắn mà vẫn ngừng sớm với người đã rời đi; 3 lời = khoảng 1,5–3 ngày, đủ tín hiệu mà không làm phiền. Bật lại một chạm |
| OD-06 | 30/50/70 % | **50 % `AI_DAILY_BUDGET_USD`** | Chat do người dùng chủ động luôn còn ≥ 50 % ngân sách; cấu hình 0,1–0,9 |
| OD-07 | Số khẩn cấp theo quốc gia; không số | **Không có số điện thoại** | Múi giờ mặc định `Asia/Bangkok` dùng chung cho VN/TH nên không suy ra quốc gia đáng tin; số sai trong tình huống nguy cấp gây hại hơn không có. Mẫu tin hướng tới người tin cậy ở gần và dịch vụ cấp cứu nơi người dùng đang ở |

**Hệ quả.** Không cần migration mới; mọi giá trị là hằng/cấu hình đã có trong [phase-1/05 §8](phase-1/05-backend-api-and-agent-runtime.md). Không quyết định nào mở rộng quyền đọc dữ liệu nhạy cảm. OD-08…OD-12 giữ nguyên trạng thái (Phase 2 hoặc không cần quyết thêm).

> **Cập nhật 01/11/2026:** OD-03 (cho phép 16–17 tuổi) bị thay thế bởi chính sách 18+ toàn cục của `origin/main`: tài khoản chưa đủ điều kiện không có lịch, lời hỏi thăm hay cộng tác nào (`authorize_proactive` kiểm bằng `is_adult_eligible()`).

**Rollback.** Đổi hằng/cấu hình; cap và khung giờ hẹp hơn chỉ cần một migration CHECK nhỏ.

