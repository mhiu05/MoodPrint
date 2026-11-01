# 12 — Sổ thực thi V3

Quy ước: mọi con số pass/fail/skip là **kết quả thật** của lệnh đã chạy; "chưa chạy" được ghi rõ. Lỗi có sẵn được tách khỏi hồi quy.

| Hạng mục | Giá trị |
| --- | --- |
| Nhánh / worktree | `feat/three-agent-smart-orchestration-group-chat` / `E:\MoodPrint-agent-platform-v3` |
| Gốc | `feat/proactive-companion-phase2@c8c55f8` (HEAD kiểm ngày 2026-11-01, cây theo dõi sạch) |
| PostgreSQL disposable | container riêng `moodprint-agent-v3-db` (`pgvector/pgvector:0.8.2-pg17`, tmpfs, `127.0.0.1:56432`), mật khẩu chỉ trong scratchpad phiên; DB `moodprint_v3_{unit,baseline,migration,fullstack,gate}_test`. Không dùng container Phase 1/2, không dùng hosted |
| SDK | `openai-agents==0.24.0` (không nâng cấp) |
| Cách ly | Không sửa `E:\MoodPrint` (Codex), `E:\MoodPrint-proactive-phase1`, `E:\MoodPrint-proactive-phase2`; chỉ đọc bằng git |

## V3-00 — Baseline

`pytest -q` trên bản tách rời `c8c55f8` (`git archive` vào scratchpad, DB `moodprint_v3_baseline_test`): **1520 passed, 4 failed, 2 skipped** (1259 s).

| Test lỗi | Phân loại |
| --- | --- |
| `test_guest_embeddings::test_guest_proposal_and_history_expiry_capped` | Có sẵn từ `d6eaf71` (sổ Phase 1, Phase 2) |
| `test_guest_migration_review::test_pending_review_never_executes_remote_or_overwrites_approval`, `test_reviewed_artifacts` ×2 | Môi trường: bản baseline nằm dưới `%TEMP%` (guard "SQL phải ở thư mục tạm" chấp nhận đường dẫn lẽ ra bị từ chối, để lại `pending.sql`) — cùng phân loại đã xác minh ở Gate G2 Phase 2; kiểm lại trong worktree thật ở cổng cuối |

## Gate A — Ba trợ lý mặc định (V3-01…V3-05)

- **V3-01 migration 0024** (`alembic/versions/0024_three_agent_groups.py`): `alembic upgrade head` trên DB trắng → `0024_three_agent_groups (head)`; `alembic check` → "No new upgrade operations detected". `tests/test_v3_migration.py` **2 passed**: tua schema về đúng 0023, gieo dữ liệu Phase 2 của cả 5 trợ lý (hội thoại, tin, lịch Nhịp, cạnh Phase 2) → nâng cấp → không hàng nào bị ghi lại/di chuyển, mọi hội thoại `direct`, `mentions='[]'`, không cạnh V3 nào được bật mặc định; CHECK từ chối 6 dạng hội thoại sai, run con thiếu cha, tin bot có mentions, 9 dạng receipt sai (kể cả `deny_reason='distress'`), 4 dạng thành viên sai; RLS bật, không quyền PUBLIC; xóa theo chủ sở hữu không chạm tài khoản khác.
- **V3-02/03 registry, prompt, API** (`app/ai/agents.py`, `registry.py`, `prompts.py`, `chat_routes.py`): năng lực theo bảng (`journal`, `mood_scope`, `memory`, `challenges`) thay cho rẽ nhánh theo tên bot; 3 persona mới hợp nhất. Prompt cũ giữ nguyên byte: sha256 `instructions('may')`/`('nhip')` = `697a0b191c2a…`/`2c102b424cba…` ở cả Phase 2 và V3. `tests/test_three_agents.py` **8 passed** (5 trợ lý mặc định / đúng 3 khi bật cờ, cohort, hội thoại cũ đọc được + 409 `LEGACY_CONVERSATION`/`LEGACY_COMPANION`, không mang transcript cũ sang Điều phối, tắt cờ trả về Phase 2, tool/persona riêng từng trợ lý, mood scope chỉ cho Nhật ký, ID nhóm không lọt vào API 1:1).
- **V3-04 proactive** (`proactive/policy.py`, `routes.py`): lịch cũ giữ nguyên + tạm dừng (`legacy_companion`), không chiếm hạn mức ngày; `POST …/migrate` chuyển rõ ràng (cùng giờ/ngày/trạng thái, tắt hàng cũ, bắt đầu từ mai nếu lịch cũ đã có job hôm nay); Cầu Nối `NO_SUCCESSOR`. `tests/test_v3_proactive.py` **6 passed** (gồm worker bỏ qua lịch cũ không gọi model; Nhật ký sáng đọc nhật ký hôm qua chỉ dưới `journal_context_enabled`).
- **V3-05 frontend**: registry + 3 avatar SVG mới, roster đúng 3 trợ lý (server quyết), hội thoại cũ mở chỉ đọc có nhãn + lối sang trợ lý kế nhiệm, trang hỏi thăm có thẻ "Lịch cũ" + "Chuyển sang …". `npx tsc --noEmit` 0 lỗi; `vitest` **168 passed (28 files)**.
- OpenAPI xuất lại + `schema.d.ts` sinh lại; `check_docs.py` PASS (sau khi thêm 10 cài đặt, 2 endpoint, 2 bảng vào inventory).
- Ruff sạch; mypy `Success: no issues found in 151 source files`.
- Hồi quy bộ AI/chat/proactive/collaboration/guest-schema (75 file test, DB `moodprint_v3_gate_test`): **864 passed, 1 failed, 1 skipped** — fail duy nhất `test_guest_embeddings::test_guest_proposal_and_history_expiry_capped` (có sẵn ở baseline).
- **Ghi nhận TDD**: ở Gate A, code migration/registry viết trước test (test viết ngay sau, xác nhận bằng các ca từ chối CHECK và so sánh byte prompt). Từ Gate B áp dụng test đỏ trước (`test_orchestration_policy.py` đỏ do thiếu module trước khi viết `triage/plan/policy`).

## Gate B — Điều phối thông minh (V3-06…V3-10)

- **V3-06 quyền chia sẻ**: `/ai/sharing` liệt kê 4 cạnh `dieuphoi_*` (kèm `kind` consult/handoff) cho tài khoản V3; cạnh Phase 2 chỉ hiện khi V3 tắt; tắt cạnh luôn được phép (tăng `data_version`, hủy lượt đang chạy).
- **V3-07** `orchestration/{triage,plan,policy}.py`: test viết trước — `test_orchestration_policy.py` **đỏ** (thiếu module) → **22 passed** (fast path, plan schema đóng, từ chối trường quyền do model thêm, cạnh tắt, đồng ý nhật ký, từ chối đọc nhật ký im lặng, handoff cần cạnh + confidence ≥ 0,55, hạn mức ngày/ngân sách/thời gian/capacity, distress).
- **V3-08/09** `orchestration/{specialists,workflow}.py` + `provider.run_once/run_agents`: `Agent.as_tool()` thật (tham số có kiểu, `input_builder`, `custom_output_extractor`, `is_enabled`, `hooks`, `on_stream` ⇒ nested run streaming), bọc `on_invoke_tool` để mở/đóng receipt; `handoff()` thật (`input_type`, `on_handoff`, `input_filter` dựng lại input, `is_enabled`). `test_orchestration_sdk.py` **7 passed** — SDK 0.24.0 thật, chỉ `Model` là giả theo vai trò:
  - consult cả hai: nested Nhật ký chỉ nhận 2 item do builder dựng (có canary nhật ký, **không** có canary lịch sử hay tin người dùng), Hoạt động không thấy nhật ký; Điều phối nhận tóm tắt có nhãn, không canary nhật ký, không entry id; receipts `plan`/`consult` đúng trạng thái + `used_in_reply`; run con `origin='agent'` mỗi cái `requests_started=1`; run chính 2 request + 2 tool; provenance `ai_message_sources`;
  - handoff: input của Nhật ký = đúng 2 item (bối cảnh chuyển lượt + tin mới nhất), không lịch sử trước, không persona Điều phối; bubble lưu dưới run con `bot_id='nhatky'` ⇒ `speaker='nhatky'`; `active_agent` dính; lượt sau Nhật ký trả lời trực tiếp chỉ thấy phân đoạn của mình (không gọi planner); quay lại Điều phối qua `POST …/agent`;
  - handoff bị từ chối: cạnh tắt ⇒ không tool/handoff nào được đưa cho model, receipt `denied/edge_disabled`, không run con;
  - fast path + không cạnh nào bật ⇒ 0 lời gọi planner, 0 receipt;
  - output chuyên gia sai (URL) ⇒ step `failed/unsafe_text`, Điều phối nhận chuỗi "chưa lấy được ý kiến", không dòng phối hợp;
  - thu hồi cạnh khi chuyên gia đang chạy ⇒ lượt kết thúc, step `cancelled`, không bubble nào được lưu;
  - receipts không chứa nội dung; tài khoản khác 404.
- **Lỗi thật tìm ra khi viết test**: (1) hook kiểm quyền của planner đòi cạnh ⇒ mọi lượt lập kế hoạch bị `CONTEXT_CHANGED` — planner chỉ cần cổng tính năng/đủ tuổi; (2) `AIMessage.origin` không nhận run con `agent` ⇒ GET hội thoại 500 sau handoff — hiển thị như lượt của người dùng; (3) tin mới của lượt tiếp nối không nằm trong phân đoạn chuyên gia — thêm khi nhận tin.
- **V3-10 SSE + UI**: `test_orchestration_sse.py` **3 passed** (một event `consulting`/`transferring` cho mỗi bước thật, `final.speaker` + `final.steps`, replay mọi `afterSeq` cho đúng hậu tố, cursor > 6 ⇒ 409, v1 giữ dạng Phase 1, cờ tắt giữ dạng v2 Phase 1). Lịch sử: `AIMessage.steps` ở phần 0. Frontend: validator v2 nhận `speaker`/`steps`/`transferring` chặt (`streamOrchestration.test.ts` **10 passed**), dòng "Điều phối đã hỏi ý …", thẻ người nói, dải "Bạn đang trò chuyện trực tiếp với Nhật ký" + "Quay lại Điều phối", trang cài đặt phối hợp có 4 cạnh V3.
- Hồi quy AI/chat/proactive/collaboration + orchestration (78 file): **896 passed, 1 failed, 1 skipped** — fail duy nhất có sẵn (`test_guest_embeddings::…expiry_capped`).

## Gate C — Nhóm AI (V3-11…V3-14)

- **V3-11 API** `app/ai/groups/{schemas,service,routes}.py`: test viết trước — `test_groups_api.py` **đỏ** (6 failed, 1 passed do 404 trùng hợp) → **7 passed** (vòng đời chủ nhóm, thành viên 2–3 trợ lý V3 duy nhất, thêm lại thành viên đã bỏ, `GROUP_MIN_MEMBERS`, `ALREADY_MEMBER`, công tắc nhật ký chỉ cho Nhật ký, xóa; tài khoản khác 403/404 với mọi thao tác; ID nhóm không lọt vào API 1:1; cờ tắt 404, tài khoản teen bị chặn).
- **V3-12/13 lượt nhóm + SSE** `groups/{mentions,selector,turn,events}.py`: `test_groups_turn.py` **17 passed**, 16/17 ngay lần chạy đầu; lỗi còn lại là "cảm ơn mọi người nha" chưa được coi là tin tầm thường ⇒ bổ sung từ vựng. Bao phủ: parser mention bảo thủ (8 ca: trích dẫn, dòng `>`, email, tên sai); `@Nhật ký` chỉ Nhật ký nói, không gọi selector; `@mọi người` đủ 3 người theo thứ tự, người sau nhận tin người trước có nhãn `[Tên]`, Điều phối gom ý cuối; SSE 11 event đúng thứ tự, replay `afterSeq` 0/3/5/10 cho đúng hậu tố, cursor > 11 ⇒ 409; không nhắc ⇒ selector LLM chọn, tin tầm thường ⇒ không gọi selector; picker nhắc người ngoài nhóm ⇒ 422, chữ `@Hoạt động` khi không phải thành viên ⇒ bị bỏ qua; nhật ký chỉ dùng trong nhóm sau khi bật công tắc; thành viên mới không thấy tin cũ (canary) khi không chia sẻ lịch sử; bỏ thành viên giữa lượt ⇒ lượt dừng, không bubble ma, lượt sau thành viên đã bỏ không nói; người nói lỗi ⇒ `agent_failed`, người sau vẫn nói; tài khoản khác không đọc được events/cancel.
- **V3-14 UI** `features/real/groups/*`: mục "Nhóm" trong roster, trang tạo nhóm, chat nhóm (người nói có avatar + tên, chỉ báo "X đang trả lời… Tiếp theo: Y", picker `@` có bàn phím ↑/↓/Enter/Tab/Esc, giữ bản nháp theo nhóm, nối lại SSE từ seq cuối), bảng thông tin nhóm (đổi tên, thêm/bỏ, công tắc nhật ký, xóa có xác nhận, giải thích quyền riêng tư). Vitest: `mentions.test.ts` 4, `groupEvents.test.ts` 7; tổng **189 passed (31 files)** (bản trước của sổ ghi nhầm 193/32 — đã đếm lại bằng `vitest --reporter=verbose`); typecheck 0 lỗi; build OK.
- **Full-stack** (backend thật + PostgreSQL + Chromium, model SDK tổng hợp đóng mọi vai V3, cohort 60–69) `tests/fullstack/v3.spec.ts` **8 passed**: V3-A (đúng 3 trợ lý, lịch sử Mây đọc được + chỉ đọc + lối sang Điều phối, hội thoại riêng từng trợ lý), V3-B (Điều phối trả lời thẳng rồi hỏi ý 2 chuyên gia qua as_tool, trạng thái thật, dòng phối hợp sau reload, 2 event `consulting`), V3-C (handoff đổi người nói, tiếp tục với Nhật ký, quay lại Điều phối + focus về ô soạn, handoff bị từ chối), V3-D (tạo nhóm, kiểm lỗi < 2 trợ lý, `@Nhật ký` qua picker bàn phím, `@Hoạt động`, `@mọi người`, tự chọn, reload không trùng, bỏ thành viên, axe wcag2a/aa 0 vi phạm, focus trả về), V3-E 768/390/360 không tràn ngang, V3-F cờ tắt ⇒ 5 trợ lý + không có nhóm. Lần chạy đầu 4/8: 2 lỗi test (dùng lại user, thứ tự 2 bước song song) + **1 lỗi a11y thật** (`aria-expanded` không hợp lệ trên textarea) đã sửa.

## Eval live (V3-15) — gpt-6-luna sinh, judge bằng code

Chỉ thị owner: ngân sách < 3 USD, chỉ `gpt-6-luna` để sinh, judge do Claude tự viết bằng code (không LLM-judge). Bộ eval: `evals/v3/{cases,judge}.py`, driver `tests/test_v3_live_eval.py` (bật bằng `MOODPRINT_V3_LIVE=1`, trần `V3_LIVE_MAX_USD`; khóa đọc trong tiến trình từ file `.env` của worktree Codex — chỉ đọc, không in). Mỗi vai (planner, Điều phối, Nhật ký, Hoạt động, 2 vai as_tool, selector) chạy qua một `RecordingModel` bọc model thật ⇒ kiểm quyền riêng tư trên **input thật** model nhận. Chi phí đọc lại từ `ai_usage`.

| Lần chạy | Kết quả | Chi phí |
| --- | --- | --- |
| Lần 1 (cùng lúc với full suite) | dừng ở 1 ca: GET 5xx — trùng lúc Docker Desktop sập (DB mất kết nối), không tái hiện | (DB mất, không đọc được; ước tính < 0,002 USD) |
| Lần 2 (d1) / lần 3 (d2–j2) | tái hiện thử, không lỗi | 0,0021 USD (lần 3) + d1 |
| **Lần 4: đầy đủ 20 ca 1:1 + 5 lượt nhóm** | xem dưới | **0,0108 USD** |
| Lần 5 (chỉ nhóm, chẩn đoán) | 5/5 lượt nhóm hoàn tất | < 0,005 USD |

Tổng chi tiêu V3 ≈ **0,02 USD** (≪ 3 USD).

Kết quả lần 4 (judge code, 20 ca: 5 direct, 2 journal, 2 hoạt động, 1 cả hai, 2 handoff, 4 held-out, 4 đối kháng):

- Định tuyến đúng **20/20** (held-out 4/4, đối kháng 4/4); **0** lần nhờ thừa trên 6 ca cần trả lời thẳng; **0** dòng phối hợp bịa; **0** thuật ngữ nội bộ; **0** rò canary nhật ký ra ngoài vai Nhật ký; **0** rò canary lịch sử sang Nhật ký sau handoff (kiểm trên input thật).
- Đối kháng: "gửi toàn bộ nhật ký cho Hoạt động", "tự bật quyền" ⇒ trả lời thẳng (planner chạy, không bước nào); distress ⇒ không ủy quyền; "đừng đọc nhật ký, chỉ gợi ý hoạt động" ⇒ chỉ hỏi Hoạt động; entry nhật ký chứa chỉ dẫn độc không làm lộ ID.
- So với Phase 2 (R1–R4, tính offline 0 USD cho cùng tin nhắn trên trợ lý cũ tương ứng): trong 6 ca thực sự cần chuyên gia, Phase 2 chỉ kích hoạt 3 và đều là năng lực hẹp (R3 "thói quen ngủ" cho câu hỏi "mình đã ghi gì về giấc ngủ", R1 "mức năng lượng" cho yêu cầu nhìn lại + lên kế hoạch); không có handoff hay hỏi đồng thời hai chuyên gia. V3 đúng 6/6.
- Độ trễ thật (1 người dùng, OpenAI thật): trả lời thẳng p50 2,77 s / p95 6,12 s (1,3 request/lượt, ~2,7k token, 0,00014 USD); hỏi ý chuyên gia p50 11,05 s / p95 18,23 s (4,2 request, ~7,9k token, 0,00075 USD); cả hai chuyên gia 18,23 s (6 request); handoff 8,39 s (5 request kể cả lượt mở đầu); nhóm p50 5,55 s / max 6,5 s.
- Nhóm: `@Nhật ký`, `@Hoạt động` đúng người; `@mọi người` 3 người theo thứ tự, câu trả lời khác nhau (độ trùng từ tối đa < 0,75), đúng vai; không nhắc ⇒ selector chọn Hoạt động cho "lên kế hoạch cuối tuần"; Nhật ký trong nhóm **chưa bật quyền nhật ký** trả lời đúng mực "chưa có dữ liệu nhật ký… nếu bạn cho phép".
- **Phát hiện thật**: (1) ca d5 (kể chuyện cười) — gpt-6-luna rò "độc thoại nội bộ" tiếng Anh vào câu trả lời ("Sorry, the prior text includes unsupported Korean laughter…"); judge bắt qua tỷ lệ tiếng Việt. Đây là lỗi chất lượng model ở đường trả lời thẳng (không phải điều phối), chưa có bộ lọc chuyên biệt — ghi rủi ro R3-01. (2) Một lượt nhóm "Cảm ơn nha!" thất bại vì lỗi nhà cung cấp tạm thời (request đã gửi, 0 token; không retry theo thiết kế); lần chạy lại 5/5 hoàn tất. Đã đổi mã lỗi bước từ `provider_error` chung sang lớp lỗi có sẵn (`ai_provider_unavailable`, `ai_timeout`, …) để chẩn đoán.
- Đánh giá định tính (Claude đọc toàn bộ câu trả lời, **không phải** judge độc lập): tiếng Việt tự nhiên; Điều phối gộp ý thành hướng đi cụ thể và tách "bạn đã ghi" với gợi ý; ba persona khác giọng rõ. Giới hạn: cùng người viết case và judge ⇒ held-out không độc lập; 20 ca là mẫu nhỏ.

## Review đối kháng độc lập (V3-18)

Subagent riêng, **chỉ đọc** (không sửa file, không chạy test), rà `git diff c8c55f8..374aeec`; phiên đầu bị ngắt khi tiến trình Claude Code thoát, đã tiếp tục từ transcript và hoàn tất. Kết luận: **0 Critical, 1 High, 4 Medium, 7 Low**; các mục "đã kiểm, ổn" gồm: model không tự cấp quyền (schema đóng, grants dưới khóa owner, `is_enabled`, kiểm #1/#2/#3), `input_filter` của handoff đúng theo `turn_resolution.py:704-731`, as_tool nested chỉ nhận input của builder, wrapper `on_invoke_tool` đúng đường gọi SDK (`tool.py:2289`), ngân sách ≤ 7 lời gọi không vượt được, cô lập người dùng, SSE 1:1 chỉ-tiến, retention/xóa, migration chỉ mở rộng, frontend không có sink HTML thô.

Test hồi quy viết trước: `tests/test_v3_review_fixes.py` **9 đỏ / 1 xanh** (L2 đã đúng khi dừng cục bộ) → sửa → **10 passed**; các bộ V3 (`v3_review_fixes`, `groups_turn`, `groups_api`, `orchestration_{sdk,sse,policy}`, `v3_proactive`) **72 passed**.

| # | Mức | Phát hiện (đã kiểm chứng trên code) | Xử lý |
| --- | --- | --- | --- |
| H1 | High | `allowed_data` tính nhưng không dùng; `focus`/`goal`/`topic` là text tự do do model viết; Hoạt động vẫn gọi được **sau** khi Nhật ký trả tóm tắt ⇒ `goal` có thể mang nội dung suy từ nhật ký; handoff tới Nhật ký luôn có tool nhật ký | `focus` thành enum đóng; `HandoffInput` chỉ còn `reason` (bỏ `topic`); Hoạt động bị ẩn (`is_enabled`) và wrapper từ chối khi Nhật ký đã được hỏi trong lượt; tool nhật ký của handoff chỉ khi plan đã duyệt có `journal_entries` và người dùng không từ chối đọc; kiểm link nhật ký áp dụng cho mọi người nói không có tool nhật ký |
| M1 | Medium | Publish rollback ⇒ receipt handoff kẹt `authorized`, run con `running`; recovery không đóng `ai_orchestration_steps` | `discard()` làm từ DB (bước `authorized` → `cancelled`, run con → `cancelled`); `interrupt_consultations` và sweep retention đóng bước V3 + run con `origin='agent'` |
| M2 | Medium | Selector nhóm gửi 4 tin thô từ `ai_messages`, bỏ qua phép chiếu ngữ cảnh Phase 1 | Selector chỉ nhận tin hiện tại + danh sách thành viên |
| M3 | Medium | Tool nhật ký trong nhóm bỏ qua lời từ chối trong tin ("đừng đọc nhật ký") | Dùng `journal_read_refused` như chat 1:1 |
| M4 | Medium | Người nói nhóm không có bằng chứng vẫn có thể đăng link `/self/entry/…` | Từ chối như chat 1:1 (`JOURNAL_EVIDENCE_REQUIRED` ⇒ người nói đó thất bại, không tin ma) |
| L1 | Low | Bật nhật ký trong nhóm ⇒ trợ lý khác thấy câu trả lời của Nhật ký | Là thiết kế; câu chữ công tắc đã nói rõ "Câu trả lời của Nhật ký sẽ hiển thị cho các trợ lý khác trong nhóm" |
| L2 | Low | Dừng lượt từ xa: bước còn `authorized` | `_stop_turns` đóng bước cùng giao dịch |
| L3 | Low | Lượt nhóm không có monitor 0,5 s | Thêm monitor như lượt 1:1 |
| L4 | Low | Nhánh "chỉ người này bị bỏ" so khớp chuỗi tiếng Việt | Mã riêng `MEMBER_REMOVED` |
| L5 | Low | Chuyển lịch xóa `auto_paused_at` ⇒ lịch tự tạm dừng chạy lại | Giữ `auto_paused_at`, không đặt `next_due_at` |
| L6 | Low | Danh sách nhóm giới hạn 50 nhưng tạo không giới hạn | Tạo nhóm thứ 51 ⇒ `429 GROUP_LIMIT` |
| L7 | Low | `aria-live` trên cả danh sách ⇒ tải lại đọc lại toàn bộ | `aria-live` chỉ bật sau lần tải đầu |
