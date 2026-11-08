# Phase 3 — AI Companion: báo cáo thực thi (bàn giao một phần)

**Trạng thái: `PHASE_3 = NOT_VERIFIED`** — triển khai một phần, các kiểm chứng live **BLOCKED**.
Đây **không** phải `PARTIALLY_VERIFIED` cho toàn Phase 3: chỉ các mục ghi `VERIFIED` bên dưới có
bằng chứng chạy thật; phần còn lại là `NOT_STARTED`, `BLOCKED` hoặc `UNMEASURED`.

| Mục | Giá trị |
|---|---|
| Branch | `feat/agent-companion` (worktree do owner tạo đang ở nhánh gõ nhầm `mhiu05/agent-companin`, cùng SHA; đã `git switch` sang nhánh có sẵn, không tạo nhánh/worktree mới) |
| SHA nền | `fc84d1fa` (HEAD lúc bắt đầu). Tag `baseline/phase-2-3-start-rc2` **không tồn tại**; chỉ có `rc1` (`65d38e49`, tổ tiên của HEAD) |
| SHA cuối | ghi trong thông điệp bàn giao (commit chứa báo cáo này) |
| Model / SDK | `gpt-6-luna` (không thay), `openai-agents==0.24.*` (khóa), chưa gọi API lần nào |
| Chi tiêu | **0 USD, 0 lời gọi, 0 token** — không có `.local/eval-budget.json`, không có `OPENAI_API_KEY` |

## 1. Chặn / blocker (theo mức ảnh hưởng)

1. **Live bị chặn**: thiếu ngân sách do owner duyệt và khóa API ⇒ L-AG-01…06, S-06, S-07, eval live, đo độ trễ/chi phí đều `BLOCKED/UNMEASURED`. Cổng chi tiêu đã dựng và kiểm chứng từ chối (exit 3).
2. **CI đỏ trên mọi SHA** (`Foundation`, bước *Parallel phase ownership*, jobs `offline` + `integration`; ví dụ https://github.com/mhiu05/MoodPrint/actions/runs/42486453883): `ci_ownership.py` so với tag `rc1` và thấy 4 tệp do commit tích hợp `67130be3` đổi (`.claude/settings.local.json`, `.cursor/mcp.json`, `.gitignore`, `.mcp.json`). Không phải tệp của Phase 3; cần integrator phát hành tag `rc2`. Không sửa policy/CI.
3. **CC-P3-002**: `backend/tests/integration/test_schema_drift.py` (đóng băng) cứng 22 bảng `app` ⇒ mọi bảng Phase 3 làm nó đỏ. 89 integration pass, 1 fail (test này).
4. **CC-P3-001**: `migration_scope_check.py` cấm trigger/plpgsql, `auth.*`, `~` ⇒ ràng buộc DB yếu hơn đặc tả (xem §6).
5. Lỗi có sẵn ở baseline: `shared/tests/test_knowledge_fixture.py::test_positive_timeout_is_enforced` đỏ trên Windows (timeout `1e-12` không kích hoạt) — xác nhận đỏ ở worktree `knowledge-base` chưa sửa gì; tệp đóng băng.
6. Docker Desktop không chạy lúc đầu; đã khởi động thủ công, stack `ag` (+200) dùng được.

## 2. Ma trận tác vụ

| Task | Trạng thái | Ghi chú |
|---|---|---|
| P3-00 | **PARTIAL** | Cổng ngân sách + ledger + guard HTTP (20 test) **VERIFIED**; `test_live_compat.py` viết nhưng **chưa chạy**, L-AG-04/05/06 chưa cài; baseline số liệu xem §8 |
| P3-01 | VERIFIED (offline) | Config (`AgentConfig`/`MemoryConfig`), 4 prompt có ghim sha256, `register_group`, preview bất đồng bộ từ bản lưu, `CompanionToolContext`, `ToolDeps`, factory. Chưa sửa khối `agent` của `.env.example` |
| P3-02 | **PARTIAL** | Tầng khẩn cấp tất định VERIFIED về nhất quán; **recall trên cụm chưa thấy lần đầu chỉ 0.74/0.79** (xem §7). S-06/S-07 `UNMEASURED` |
| P3-03 | VERIFIED (có lệch đặc tả) | 5 migration `*_ag_*`, 4 pgTAP; 18 file / 401 test PASS |
| P3-04 | **PARTIAL** | Có: wiring thật, B-12 (citations+structured lưu/phát lại), trần token ngày (429 `ai_tokens`), liên kết quyết định↔đề xuất. **Chưa**: `GET /runs/{id}/approvals`, đính kèm ảnh/`/attachments`, chọn chế độ roleplay, ma trận cô lập Phase 3, Retry-After, OpenAPI không đổi |
| P3-05 | VERIFIED (fixture) | `knowledge_search` + sổ cái citation; INT-03 đo lại bằng retriever thật |
| P3-06 | VERIFIED | Tool + adapter PostgreSQL; 11 integration test (xem §5) |
| P3-07 | VERIFIED (tool) | 18 test tool + 1 integration (crash/phục hồi); chưa có integration ma trận đầy đủ như P3-06 |
| P3-08 | **PARTIAL** | Có `propose_memory` + bộ lọc tất định. **Chưa**: chọn lọc theo ý định/stale/domain, chính sách nén, test DB |
| P3-09 | NOT_STARTED | Phân tích ảnh (chưa có `evidence/`, endpoint, consent, bảng dùng chưa có code) |
| P3-10 | NOT_STARTED | Roleplay (chỉ có prompt + bảng `roleplay_sessions`) |
| P3-11 | VERIFIED (tool) | `support_directory`, `draft_support_message`; chặn khẩn cấp ở runtime. Không có `backend/.../safety.py` riêng |
| P3-12 | **PARTIAL** | Checkpoint v2 (sổ cái citation + mức khẩn cấp), sửa lỗi mất `tool.completed` sau resume. **Chưa**: grace-period hủy, timeout/refusal bổ sung, heartbeat/repair, test race |
| P3-13…P3-16 | NOT_STARTED | Frontend chưa đụng tới |
| P3-17 | NOT_STARTED | Chưa có harness `run.py`/`summarize.py`; chỉ có bộ cụm khẩn cấp offline |
| P3-18 | NOT_STARTED | Chưa có `ai-real.spec.ts`, scripted E2E, tải |
| P3-19 | PARTIAL | Báo cáo này; CI không xanh (blocker 2) |

## 3. Tiêu chí D3

| D3 | Trạng thái |
|---|---|
| D3-01 chat thật `gpt-6-luna` | **BLOCKED** (không ngân sách/khóa) |
| D3-02 session/ký ức bền | không xác minh mới; test hiện có xanh, không có E2E |
| D3-03 tool + citation hợp lệ | VERIFIED ở mức fixture (U-AG-40…55 tương đương) |
| D3-04 mọi ghi cần approval | **VERIFIED ở mức tool+PostgreSQL** (sự kiện, kế hoạch); chưa E2E UI |
| D3-05 phân tích ảnh | NOT_STARTED |
| D3-06 roleplay | NOT_STARTED |
| D3-07 frontend | NOT_STARTED |
| D3-08 cô lập người dùng | một phần: pgTAP `ag_01` + 11 integration; chưa ma trận route |
| D3-09 toàn bộ xanh | không: 1 integration + 1 shared đỏ (§1) |
| D3-10 eval | UNMEASURED |
| D3-11 ownership/CI | **FAIL** (blocker 2) |
| D3-12 báo cáo | file này (chưa đủ mục §7 của handoff vì thiếu phần chưa làm) |

## 4. Tool, prompt, phiên bản

`prompt_version=companion_v2` (+ `roleplay_partner_v1`, `roleplay_coach_v1`, `evidence_reader_v1`; sha256 ghim trong `test_prompts.py`).
Tool đã đăng ký (10): `knowledge_search`(read) · `get_case_context`(read) · `propose_case_event`(prepare) · `save_confirmed_event`(**write, approval**) · `get_action_plan`(read) · `propose_action_plan`(prepare) · `save_plan`(**write, approval**) · `propose_memory`(prepare, chỉ tạo candidate) · `support_directory`(read) · `draft_support_message`(prepare). Chưa có: `analyze_evidence`, `report_turn_assessment` (S-06). `tools_version` là hàm của policy, ghim bằng `test_tool_inventory`.
Bất biến được test: không tool nào có `send|post|email|call|submit|share`; tool ghi chỉ nhận `proposal_id`; không tham số định danh; mọi tool có nhãn tiếng Việt.

## 5. Bằng chứng đề xuất → duyệt → lưu (D3-04)

PostgreSQL thật, chỉ model là `ScriptedModel` — `backend/tests/integration/agent/test_incident_tools.py` (11 passed):
không ghi `case_events` trước duyệt; duyệt → đúng 1 sự kiện `user_confirmed`, id = UUIDv5(owner, proposal), nội dung = bản đã hiện, đúng 1 audit; từ chối → 0 ghi; đề xuất hết hạn → quyết định bị hoàn tác (409), `tool_approvals` vẫn `pending`; preview bị sửa sau khi hiển thị → không duyệt được; user B không đọc/quyết/áp dụng, không đề xuất lên hồ sơ của A; crash sau commit domain nhưng trước `applied` → retry cùng UUID, không thêm audit/version; 4 `apply` đồng thời → 1 sự kiện; version hồ sơ cũ → `failed` + `conflict`; run đã hủy → không bắt đầu ghi; payload bị sửa → `payload_mismatch`; kế hoạch: áp dụng một lần + phục hồi crash.
Cơ chế: `ApprovalService.decide` gắn quyết định với đề xuất **cùng transaction** (khớp hash, preview, hội thoại, chưa hết hạn); writer kiểm lại mọi ràng buộc trước khi gọi domain service (`add_confirmed_event`, `upsert`).

## 6. Migration và lệch so với đặc tả

`20261108100100_ag_proposals`, `…100200_ag_analysis_requests`, `…100300_ag_roleplay_sessions`, `…100400_ag_message_attachments`, `…100500_ag_message_assessments`. `migration_scope_check` VERIFIED (5), `migration_order_check --self-test` 19 passed. Không ALTER bảng `f0/f1`; không hosted.
Lệch (xem CC-P3-001): không có trigger; bất biến nội dung bằng **column-level GRANT**, trạng thái cuối bị đóng băng bằng RLS, `approval_binding` ràng buộc bằng CHECK; đồ thị chuyển trạng thái/write-once/hết hạn do `UPDATE … WHERE` (compare-and-set) ở ProposalStore. Không FK tới `auth.users` (owner đi qua FK ghép). Chính sách dùng `current_setting('request.jwt.claims')` thay `auth.uid()`.

## 7. Giới hạn đã biết — an toàn khẩn cấp (đọc kỹ)

Tầng tất định (`tools/safety.py`) **không** chứng minh an toàn. 226 cụm tổng hợp do chính coding agent viết:
- bộ viết cùng lúc với luật: recall `immediate` 79/79, báo động giả 0/91 — chỉ phản ánh độ nhất quán;
- hai bộ *chưa thấy* chạy lần đầu: recall `immediate` **14/19 (0.74)** và **11/14 (0.79)**, báo động giả 2/22 và 1/16 — thấp hơn nhiều ngưỡng 0.95. Sau đó luật được vá theo các ca sót (khái quát hóa, không khớp chuỗi), nên bộ đó không còn độc lập.
Vì vậy Q3-03/Q3-04 `UNMEASURED` cho hệ thống thật; các câu trả lời rủi ro cao (SC-04/07/09/24) chưa có đầu ra model nào để đọc. Chưa dùng dữ liệu thật; chưa sẵn sàng cho học sinh thật.
Khác: ước lượng token prompt = ký tự/3 (~980), chưa dùng tokenizer thật; S-06 chưa quyết định nên `structured` hiện chỉ chứa `reply`, `urgency`, `citations`.

## 8. Lệnh và kết quả (SHA `c470059d` trừ khi ghi khác)

| Lệnh | Kết quả |
|---|---|
| `scripts/check.py` | exit 1 **chỉ vì** test baseline đỏ ở §1.5; ruff/format/pyright(strict)/lint-imports xanh; pytest 1171 passed, 1 failed, 90 deselected |
| `pytest -m integration` (stack ag, env ag) | 89 passed, 1 failed (`test_schema_drift`, CC-P3-002), 1172 deselected |
| pgTAP (`supabase_worktree.py test`) | exit 0, 18 file, 401 test PASS |
| `export_contract_schemas.py --check`, `export_openapi.py --check` | exit 0 (không đổi API/contract) |
| `migration_scope_check`, `migration_order_check --self-test` | VERIFIED (5) / 19 passed |
| `ci_ownership.py --branch feat/agent-companion --local` | **FAIL** — chỉ 4 đường dẫn của commit tích hợp (§1.2); mọi tệp của Phase 3 hợp lệ |
| `pytest -m live_agent agent/tests/live` (không ngân sách/khóa) | exit 3, thông điệp `BLOCKED` (test: `test_live_gate.py`) |
| `test_live_gate.py` | thêm sau lần chạy đầy đủ cuối, chạy riêng: 1 passed |
| Frontend (npm) / Playwright / `verify_phase*.py` / E2E | **không chạy** (chưa động tới frontend) |

## 9. Việc còn lại / giao integrator

- Owner: duyệt `.local/eval-budget.json` + khóa ⇒ chạy L-AG-01…06, S-06/S-07 rồi mới mở eval live.
- Integrator: tag `rc2` (hoặc xử lý drift ownership), CC-P3-001 (trigger an toàn), CC-P3-002 (`test_schema_drift`), INT-03 retriever thật.
- Phase 3 tiếp theo theo thứ tự: hoàn P3-04 (approvals GET, attachments, roleplay, ma trận cô lập, OpenAPI), P3-12, P3-09, P3-10, P3-08 còn lại, rồi frontend P3-13…16, P3-17 (harness+eval), P3-18, P3-19.
- Mọi tuyên bố "xong" cho các mục trên cần chạy lại trên SHA cuối; số liệu cũ không áp cho SHA mới.
