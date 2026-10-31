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
