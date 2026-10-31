# Sổ tiến độ triển khai Phase 2 — Trợ lý phối hợp

Nhánh `feat/proactive-companion-phase2`, worktree `E:\MoodPrint-proactive-phase2`, tách từ `feat/proactive-companion-phase1@44f4201` (HEAD Phase 1 đã kiểm, cây sạch phần được theo dõi). Kế hoạch: [phase-2/06](../phase-2/06-implementation-plan.md). Quy ước: số pass/fail/skip là **kết quả thật** của lệnh đã chạy; "chưa chạy" được ghi rõ.

| Hạng mục | Giá trị |
| --- | --- |
| PostgreSQL disposable | Container riêng `moodprint-proactive-p2-db` (`pgvector/pgvector:0.8.2-pg17`, tmpfs, `127.0.0.1:46432`), mật khẩu chỉ trong scratchpad phiên. Không dùng container Phase 1, không dùng hosted |
| DB | `moodprint_p2_{baseline,unit,migration,fullstack,load,rehearsal,gate}_test` |
| SDK | `openai-agents==0.24.0` (không nâng cấp); `Runner.run_streamed` như Phase 1 (fake model của repo chỉ hỗ trợ streaming) |
| Chi tiêu API | **0 USD** — không có lời gọi model thật nào trong Phase 2 (ngân sách Phase 2 chưa được duyệt) |
| Cách ly | Không sửa `E:\MoodPrint` (Codex) hay `E:\MoodPrint-proactive-phase1`; chỉ đọc bằng `git log/diff/show` |

## P2-00 — Cổng Phase 1 (baseline)

`pytest -q` trên bản tách rời `44f4201` (scratchpad, DB `moodprint_p2_baseline_test`): **1346 passed, 7 failed, 1 skipped** (2040 s). Phân loại (chạy lại riêng):

| Test | Phân loại |
| --- | --- |
| `test_guest_embeddings::test_guest_proposal_and_history_expiry_capped` | Có sẵn từ `d6eaf71` (ghi ở sổ Phase 1) |
| `test_runtime_provision::…`, `test_guest_schema::test_guest_tables_are_private` | Do phiên này tạo role cluster-wide `moodprint_runtime` cho diễn tập 0023 **trong lúc** baseline chạy; xóa role → chạy lại **pass** |
| `test_guest_inflight::test_idle_sse_closes_at_deadline…` | Flake do tải (chạy song song); chạy lại **pass** |
| `test_guest_migration_review::test_pending_review…`, `test_reviewed_artifacts` ×2 | Môi trường: bản baseline nằm dưới `%TEMP%` nên guard "SQL phải ở thư mục tạm" chấp nhận đường dẫn lẽ ra bị từ chối, để lại `pending.sql`; xác minh lại trong worktree thật ở Gate G2 |

Không có sự cố rò rỉ/giao trùng mở nào trong sổ Phase 1. Owner chưa xác nhận G2-entry bằng văn bản (prompt phiên này cho phép bắt đầu).

## P2-01 — M-P2-A `0023_collaboration` — `9f4c19d`

- File: `alembic/versions/0023_collaboration.py`, `app/ai/collaboration/models.py`, `infrastructure/database/models.py` (`AiRun.parent_run_id`, CHECK `origin`/`parent`), lifecycle (account + guest `INVENTORY`), retention 90 ngày, `READY_REVISIONS=("0023_collaboration",)`, `docs/supabase/schema.md`.
- RED 6 failed → GREEN `test_collaboration_migration.py` **6 passed**: upgrade từ schema 0022 có run cũ, CHECK ma trận 5×5×3 cạnh, `parent_run_id` iff `collaboration`, deny/failure/used/digest, unique 1 lần/run, RLS + không quyền PUBLIC, xóa tài khoản/`all_private`, guest inventory, retention, cascade.
- Bổ sung so với đặc tả: CHECK `ck_ai_collaborations_deny_reason` (chỉ lý do vận hành — DB **từ chối** ghi `distress`/`edge_disabled`), cột `failure_code`, CHECK digest hex.
- Chuỗi Alembic sạch tới `0023_collaboration (head)`, `alembic check` không drift. Test pin head cũ (readiness/foundation/guest schema/rollback) cập nhật → **57 passed**.
- Offline SQL [sql/0022-0023-offline.candidate.sql](sql/0022-0023-offline.candidate.sql) (107 dòng, không `%%`, sha256 `b785c737…c1e1e8`) — **ứng viên chưa duyệt**. Diễn tập: DB 0022 + role giống hosted + run `user`/`proactive` tổng hợp → `psql -v ON_ERROR_STOP=1` một transaction → exit 0, version 0023, run cũ nguyên vẹn, 2 policy `backend_access`, client role 0 quyền, `moodprint_app` có DML, insert run con OK. Đã xóa DB và role.

## P2-02 — API quyền chia sẻ — `1aa4850`

`GET/PUT /ai/sharing[/{edge}]`, cài đặt `AI_COLLABORATION_{ENABLED,DAILY_CAP,TIMEOUT_SECONDS,BUDGET_SHARE,ROLLOUT_USER_IDS}` (validator: cần `AI_MULTI_MESSAGE_ENABLED`; production cần accounting), `features.collaboration`, OpenAPI + `schema.d.ts`, api-reference, configuration. RED 11 failed → `test_sharing_api.py` + guest permissions **80 passed**. Mutation: bỏ tăng `data_version` / bỏ yêu cầu journal / bỏ kiểm 18+ / bỏ hủy run khi tắt → **4/4 bị bắt**. Tắt cạnh luôn được phép kể cả khi cờ tắt.

## P2-03 — Policy, ma trận, hợp đồng — `4c6b76d`

`policy.py` (3 cạnh, luật thuần, thứ tự cổng cố định, `allowed_context` không nhận transcript, template), `contracts.py` (tách fact / ước lượng suy ra / gợi ý sinh / metadata). **68 passed**; mutation **13/13 bị bắt**. Ghi nhận TDD: code viết trước test ở task này; sức bắt lỗi xác nhận bằng mutation.

## P2-04 — Specialist runner — `03a4da2`

`SdkProvider.run_specialist` + `collaboration/specialist.py`; `_BudgetHooks(model_limit, tool_limit)` (chat giữ 3/2). RED → **21 passed**: tools rỗng, tracing `DISABLED`, `store=False`, không retry, 1 input item, timeout, check trước request, usage của run con, giới hạn 1 call/0 tool, context không phải `LiveRun`. Test bắt được lỗi thật: chặn tên trợ lý không phân biệt hoa/thường đã loại cả "nhịp thở" → đổi sang phân biệt hoa/thường.

## P2-05/06/07 — Coordinator, R2, receipt/DTO/SSE — `ef7c79a`

- Chat (R1/R3/R4) `test_collaboration_chat.py` **21 passed**; R2 `test_collaboration_proactive.py` **6 passed**; DTO/SSE `test_collaboration_dto.py` **15 passed** (event list là hàm thuần của trạng thái DB, prefix ổn định, reconnect mọi `afterSeq` 0–5, v1/cờ tắt giữ dạng Phase 1).
- Mutation coordinator (kiểm quyền #3, revision nguồn, distress trong excerpt, `used_in_reply`, brief) → **5/5 bị bắt**.
- Hồi quy chat/proactive/inbox: **245 passed, 1 failed** (`test_inbox_query_p95_under_50ms…` 151,8 ms khi chạy song song). Chạy lại cô lập: Phase 2 54,2 ms; **baseline Phase 1 không sửa trên cùng máy: 27,9 ms rồi 84,9 ms** ⇒ nhiễu môi trường, không phải hồi quy; đo lại ở Gate G2.
- Bộ gộp collaboration + session + guest: **290 passed**.

## P2-08 — UI phối hợp và cài đặt — `379f4f5`, `908de71`

Stream v2 validate progress/collaboration; trạng thái "A đang hỏi B một chút…" chỉ từ event `consulting` thật; dòng cộng tác (template backend, 2 avatar 16 px `aria-hidden`) trong nhóm bubble; hộp "Vì sao?" chỉ nêu loại dữ liệu (OD-10 mặc định); trang `/companion-sharing`; thẻ trong Tài khoản. Unit frontend **165 passed (28 files)**, typecheck 0 lỗi, build OK. Fixture E2E `collaboration.spec.ts` **17 passed** (axe wcag2a/aa 0 vi phạm ở 1440/768/390/360). Hồi quy E2E multi-message/proactive/chat-history/states **39 passed**.

## P2-09 — Bảo mật, eval, E2E — `0da552e`, `015b613`

- `test_collaboration_privacy.py` **9 passed**: injection qua nhật ký và chat, cross-user, câu trả lời tự xưng "Nhịp đã gợi ý" không có receipt → không có dòng, xóa tài khoản/thu hồi session giữa lượt, log không nội dung, 1 lần nhờ/lượt + độ sâu 1, idempotency.
- Eval offline (`python -m evals.collaboration --offline`): routing **44/44** (held-out 16/16), 0 nhờ thừa, 0 rò chữ người dùng, **60/60** đầu ra lậu dữ liệu bị từ chối. **Giới hạn:** case và nhãn do chính người viết regex soạn cùng phiên ⇒ held-out không độc lập, 100 % là lạc quan. Live mode chỉ chạy với `--confirm-live --max-usd` và key — **chưa chạy (0 USD)**. Ước tính (chars/3, chưa đo): ~0,00015–0,00017 USD/lần nhờ với gpt-6-luna; bộ live đề xuất (20 case năng lượng) cần ≤ 0,05 USD, đề nghị owner duyệt trần 0,25 USD.
- Hiệu năng (`MOODPRINT_COLLAB_LOAD=1`, model giả: primary 1,5 s, specialist 1,0 s, pool 5+2 như production, 8 người dùng đồng thời × 5 lượt):

| Kịch bản | p50 | p95 | p99 | call/lượt | kết nối DB đỉnh |
| --- | --- | --- | --- | --- | --- |
| Một trợ lý | 2,47 s | 3,11 s | 3,20 s | 1,0 | 7/7 |
| Phối hợp | 4,25 s | 5,08 s | 5,14 s | 2,0 | 7/7 |
| Cờ tắt | 2,99 s | 3,95 s | 4,11 s | 1,0 | 7/7 |
| Specialist trả sai → fallback | 5,38 s | 6,30 s | 7,09 s | 2,0 | 7/7 |

  p95 thêm **+1,97 s** (≤ 4 s của P2-NFR-01; 1,0 s là thời gian specialist giả). Kịch bản chạy tuần tự có trôi ~0,5 s (hai kịch bản giống hệt "một trợ lý" và "cờ tắt" lệch 0,5 s) ⇒ so sánh giữa hàng có sai số ±0,5 s. 1 người dùng: một trợ lý p50 1,77 s, phối hợp 3,06 s, fallback 2,92 s. Pool bão hòa 7/7 ở 8 người dùng kể cả không phối hợp (đặc tính Phase 1: monitor 0,5 s).
- Fullstack (backend thật + PostgreSQL + Chromium) `tests/fullstack/collaboration.spec.ts` **4 passed** (E2E-17/18/19, timeout/invalid, R1 + cờ tắt); Phase 1 fullstack multi-message/proactive/chat-history **4 passed**.
- **Lỗi thật do E2E-19 tìm ra:** sau mọi thu hồi giữa lượt server kết thúc stream bằng `event: revoked`, client coi là stream sai ("Chưa nhận được phản hồi hợp lệ") — lỗi có sẵn từ Phase 1. Sửa test-first: thành dừng đã xác nhận ("Đã dừng phản hồi.").
- agent-browser 0.39.2 (Chrome thật, stack local thật, user 56): trang cài đặt 1440/768/390/360 không tràn ngang; trạng thái thật "Mây đang hỏi Nhịp một chút…" rồi dòng cộng tác; **tải lại giữa lúc đang hỏi → nối lại đúng trạng thái `consulting`**; "Vì sao?" mở/đóng bằng bàn phím, focus trả về nút; reduced motion 0 animation; đổi trợ lý không mang dòng sang; cờ tắt → 0 dòng, thẻ tài khoản ẩn; xóa cookie (hết phiên) → không có công tắc; 0 page error. **Lỗi thật:** ở 360 px viền focus của nút "Vì sao?" (hộp cao 44 px) đè chữ dòng trên → hộp ôm chữ, vùng chạm 44 px bằng `::before`. Ảnh chụp ở scratchpad phiên (ngoài git).

## P2-10 — Vận hành — `6d87f7d`

`operations.md` (thứ tự bật, metric, bảng sự cố, dừng khẩn cấp, rollback R2→R1), `runtime.md`, `ARCHITECTURE.md`, `cloudwatch-alarms.json` (+3 filter, +2 alarm, `test_ops_config` xanh). `check_docs.py` PASS. Checklist owner: chưa ký.

## Lệch đặc tả (đã quyết, có lý do)

| # | Đặc tả | Đã làm | Lý do |
| --- | --- | --- | --- |
| D-01 | R3 cần intent `support`/`practical` | Thêm `conversation` (vẫn loại `listening`, `analysis`) | `conversation_intent()` xếp ví dụ chuẩn UC-3 "mấy hôm nay mất ngủ" là `conversation` |
| D-02 | Ghi `denied` cho mọi từ chối | Chỉ ghi lý do vận hành; cạnh chưa bật và distress **không để lại dấu vết** (CHECK DB) | Tối thiểu hóa; khớp quy tắc an toàn Phase 1 |
| D-03 | `max_tokens=300` cho specialist | 600 + `reasoning.effort=low` | Giới hạn gồm cả reasoning token (R-15) |
| D-04 | `Runner.run` cho specialist | `Runner.run_streamed`, `max_turns=1` | Một đường SDK đã kiểm chứng; fake model chỉ hỗ trợ streaming |
| D-05 | Receipt `completed` khi primary publish | `completed` khi specialist xong; `used_in_reply=true` khi publish | Cần trạng thái kết thúc cho event `composing` |
| D-06 | Đủ tuổi AI (16+) | **Chỉ 18+** (`age_band=='adult'`) trong một hàm | Quy tắc sản phẩm 18+; đổi sang `is_adult_eligible()` sau tích hợp Codex |
| D-07 | Chat tạm có thể phối hợp | Chỉ hội thoại đã lưu | Dòng cộng tác phải kiểm chứng được từ DB |
| D-08 | Avatar chồng trong dòng trạng thái "đang hỏi" | Chỉ văn bản (avatar có ở dòng cộng tác) | Giữ component trạng thái Phase 1; tên hai trợ lý đã có trong câu |
| D-09 | Văn bản specialist "sau lịch sử" | Ngay **trước** tin mới nhất của người dùng | Tin người dùng vẫn là mục cuối primary đọc |
| D-10 | Không đổi client v1 | Khung `revoked` = dừng đã xác nhận (v1 và v2); progress v1 vẫn bị bỏ qua như Phase 1 | Sửa lỗi E2E-19 (bản đầu cũng siết progress v1 và gây hồi quy `real:563`, đã hoàn tác) |
| D-11 | T-11: validator lọc tên trợ lý khác trong output primary | **Chưa làm**; chỉ prompt (cấm nhắc trợ lý kia) + dòng cộng tác do backend dựng | Chặn nhầm "Nhịp" hợp lệ (card điều hướng) sẽ làm hỏng lượt; dòng giả không thể xuất hiện vì cần receipt |
| D-12 | Template R2 "Nhịp đã gợi ý một hoạt động nhẹ nhàng…" | "Nhịp đã gợi ý mức năng lượng phù hợp với bạn. Rủ Rê đã dựa vào đó để chuẩn bị thử thách hôm nay." | Câu cũ sai khi energy=high (review) |
| D-13 | R2 kiểm `data_version` như chat | R2 kiểm version cạnh + journal consent + revision nguồn, không kiểm `data_version` | Lưu mood/entry không liên quan không được hủy lời hỏi thăm (review) |

## Review đối kháng độc lập — `1a2bc62`

Subagent chỉ đọc (không chạy test) rà diff `44f4201..HEAD`. Kết quả và xử lý (test hồi quy viết trước, 6 + 3 RED → GREEN):

| # | Mức | Phát hiện | Xử lý |
| --- | --- | --- | --- |
| 1 | High | R1 vẫn đọc nhật ký khi chính tin hiện tại nói "đừng đọc nhật ký" | `Signals.journal_refused`; R1 không khớp, không đọc, không ghi |
| 2 | Medium | R2 hủy lời hỏi thăm (ghi nhầm là thu hồi) khi `data_version` đổi vì lưu mood/entry; nhánh `source_changed` không tới được | R2 không kiểm `data_version` (D-13) |
| 3 | Low–Med | Receipt kẹt `authorized` khi settle lỗi hoặc recovery theo lease usage chạy trước | Retention đóng receipt/run con mồ côi |
| 4 | Low | Template R2 sai với energy cao | D-12 |
| 5 | Low | Cờ tắt vẫn có khóa `collaboration: null`, `features.collaboration`, route `/ai/sharing` | Chấp nhận (bổ sung, không đổi SSE/model call/accounting); tắt cạnh luôn được phép theo thiết kế |
| 6 | Low | Mọi tin khớp luật lấy advisory lock toàn cục kể cả khi chưa bật cạnh | Quyết định không cần bộ đếm trả về trước khi khóa |
| 7 | Low | Validator client chấp nhận `caunoi` làm specialist, không ràng `companions` với cạnh | Ràng theo bảng cạnh |
| P | — | Lỗi bất ngờ trong `open()` làm hỏng cả lượt | Savepoint + fallback trả lời đơn (chat và lời hỏi thăm) |
| P | — | Client coi mọi `event: revoked` là dừng | Giữ: server chỉ gửi khi lượt không còn hợp lệ cho người xem; client luôn tải lại trạng thái thật từ server sau đó |

Bộ collaboration sau sửa: **223 passed, 1 skipped** (benchmark opt-in); frontend **168 passed**; mypy sạch.

## Tích hợp với nhánh Codex (`feat/friendship-discovery-18plus`, đọc chỉ bằng git)

- HEAD Codex lúc kiểm: `047fe6a`; không có migration mới (`READY_REVISIONS = ("0020_private_profile_retirement",)`); worktree `E:\MoodPrint` không bị phiên này chạm.
- Chồng lấn code (so với `d6eaf71`): `infrastructure/database/models.py` (Codex xóa 1 import `Text`), `contracts.py` (Codex: eligibility 18+ khi signup), `modules/auth/routes.py` (Codex: 18+; Phase 2: `features.collaboration`), `ai/chat_routes.py` (Codex: export `eligible=False`), `RealApp.tsx` (+31 dòng Codex), `openapi.json`/`schema.d.ts` (sinh lại sau merge), test readiness/foundation/guest (pin revision).
- Chồng lấn tài liệu: Codex commit bộ kế hoạch gốc ở `efb597e` (26 file) — nhánh Phase 1/2 đã sửa chính các file đó ⇒ conflict add/add; giữ bản Phase 2 (mới hơn).
- Thứ tự đề xuất: (1) rebase Phase 1 lên Codex khi Codex ổn định, giải conflict, `down_revision` của 0021 vẫn là 0020 (Codex không có migration); (2) cập nhật R1 `READY_REVISIONS` chấp nhận 0022 **và** 0023 (điều kiện rollback của Phase 2); (3) rebase Phase 2 lên Phase 1 đã tích hợp; (4) trong `collaboration/eligibility.py` thay kiểm `age_band` bằng `await is_adult_eligible(db, user)`; (5) sinh lại OpenAPI/TS; (6) chạy lại backend/frontend/fullstack + diễn tập offline SQL 0020→0023 trên bản sao schema hosted (U-04).
- 18+: Phase 2 không đưa lại quy tắc 16+; bảng và route Phase 2 không có điều kiện `teen`.

## Gate G2 — kiểm chứng cuối (31/10/2026, HEAD `1a2bc62`)

| Hạng mục | Kết quả thật |
| --- | --- |
| Backend toàn bộ (`pytest -q`, DB `moodprint_p2_gate_test`) | **1523 passed, 1 failed, 2 skipped** (1305 s). Fail duy nhất `test_guest_embeddings::test_guest_proposal_and_history_expiry_capped` — có sẵn từ `d6eaf71`. Skip: 1 có sẵn + benchmark opt-in. `test_inbox_query_p95…`, `test_reviewed_artifacts`, `test_guest_migration_review` **pass** trong worktree thật (xác nhận phân loại môi trường ở P2-00) |
| Ruff / mypy | sạch / Success (148 files) |
| OpenAPI | export lại không drift; `schema.d.ts` sinh từ cùng file |
| Alembic | chuỗi sạch tới `0023_collaboration (head)`, `alembic check` không drift |
| `check_docs.py` | PASS (sau khi thêm sổ này) |
| Frontend unit / typecheck / build | **168 passed (28 files)** / 0 lỗi / OK |
| Fixture E2E toàn bộ (`npx playwright test`) | **344 passed, 14 failed**. 13 fail **trùng từng dòng** với tập có sẵn ở Gate G1 (`auth` :141/:166/:188, `discovery` :76/:148, `real` :471, `ux-redesign` :186/:901/:1128×2/:1180/:1196/:1273). Fail thứ 14 `real.spec.ts:563` là **hồi quy do Phase 2 gây ra**: D-10 bắt client từ chối progress v1 có dữ liệu, trong khi hợp đồng Phase 1 là bỏ qua im lặng (raw delta). Đã hoàn tác phần v1 (v2 vẫn chặt) → chạy lại `real` + `collaboration` + `multi-message`: **53 passed, 1 failed** (`real` :471 có sẵn) |
| Fullstack | collaboration **4 passed**; Phase 1 multi-message/proactive/chat-history **4 passed**; bộ fullstack toàn phần: GATE_FULLSTACK |
| agent-browser | xem P2-09 (0 page error, 2 phát hiện thật đã sửa) |
| Review độc lập | subagent đối kháng chỉ đọc; 1 High + 1 Medium + Low đã sửa (mục trên) |
| Chi tiêu API | 0 USD |

## Rủi ro còn lại

- **R2-01** Văn bản specialist "kiểu chỉ dẫn" không chứa link/tên vẫn qua validator, nhưng chỉ vào kênh dữ liệu có nhãn (test xác nhận); phòng thủ cuối là guardrail/validator của primary. Cần red-team live (chưa chạy).
- **R2-02** Sau một lượt R1, câu trả lời được stamp `journal-turn-v1` ⇒ các lượt sau cắt ngữ cảnh trước đó (fail-closed như Nhịp đọc nhật ký). Đúng đặc tả, có thể làm Rủ Rê "quên" nhanh hơn.
- **R2-03** Chất lượng specialist thật chưa đo (0 lời gọi live); routing eval không có tập held-out độc lập.
- **R2-04** Pool 5+2 bão hòa ở 8 lượt đồng thời (có từ Phase 1); phối hợp thêm vài transaction ngắn/lượt.
- **R2-05** Cổng G2 cần 7 ngày staging và owner duyệt OD-08…OD-10 — chưa thể có trong phiên local.
