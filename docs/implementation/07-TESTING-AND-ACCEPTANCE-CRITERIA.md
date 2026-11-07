# 07 — Testing and Acceptance Criteria

## 1. Các tầng test

| Tầng | Công cụ | Vị trí | Cần | Chạy mặc định |
|---|---|---|---|---|
| Unit Python | pytest | `shared/tests`, `agent/tests`, `backend/tests` | Không | Có |
| Integration Python | pytest `-m integration` | `backend/tests/integration` | Local Supabase | Theo lệnh |
| SQL | pgTAP | `supabase/tests` | Local Supabase | Theo lệnh |
| Contract | pytest | `shared/tests` | Không | Có |
| Agent deterministic | pytest + `ScriptedModel` | `agent/tests` | Không | Có |
| Agent live | pytest `-m live_agent` | `agent/tests/live` | `OPENAI_API_KEY`, trần chi phí | Thủ công |
| Unit frontend | Vitest | `frontend/src/**/*.test.ts(x)` | Không | Có |
| E2E `demo` | Playwright project `demo` | `frontend/e2e` | Vite | Có |
| E2E `real` | Playwright project `real` | `frontend/e2e/*-real.spec.ts` | Local Supabase + FastAPI | Theo lệnh |
| Smoke hosted | Script | `scripts/smoke_hosted.py` | Secret hosted trong `.env`, user tổng hợp | Agent chạy sau mỗi lần push hosted |
| Smoke giao diện hosted | Claude in Chrome | Báo cáo phase | Frontend dev trỏ vào hosted | Agent chạy ở F1-08.3 |

Đặt tên test ID: `U-` unit, `I-` integration, `P-` pgTAP, `E-` E2E, `IT-` integration hai phase.

## 2. Dữ liệu test

- Chỉ dữ liệu tổng hợp, theo tinh thần `docs/prototype/05`. Bí danh hư cấu, email `@example.test`.
- User tạo qua Auth admin của local stack trong fixture, xóa sau session test.
- Không test nào đọc `.env` khi `APP_ENV=test`.
- Không ảnh thật. File upload test sinh từ byte ngẫu nhiên hoặc SVG trong `public/fixtures/`.
- Trường học chỉ `verification_status='synthetic'`, chỉ seed ở local.

## 3. Gate G0 — Phase 0

| ID | Tiêu chí | Lệnh / test |
|---|---|---|
| G0-01 | Workspace import được, không `sys.path` | F0-01.1 |
| G0-02 | Lint, type, import boundary sạch | `scripts/check.py` |
| G0-03 | Thiếu biến báo đúng tên, không lộ giá trị; test env từ chối host thật | `shared/tests/test_settings.py` |
| G0-04 | `/health` không phụ thuộc; `/ready` báo đúng thành phần | `test_app.py` |
| G0-05 | Startup và shutdown đóng tài nguyên | `test_startup_shutdown_closes_engine` |
| G0-06 | JWT: 12 ca trong F0-04.1 | `test_auth.py` |
| G0-07 | Cô lập user, gồm 50 lượt đồng thời | `test_rls_context.py`, `test_me.py` |
| G0-08 | Mọi bảng có RLS và policy; `anon` không có quyền | `P-00`, `P-05` |
| G0-09 | Bucket private, không giới hạn; JWT người dùng không đọc, liệt kê, ghi; signed URL hết hạn; resume TUS | `test_storage_access.py`, S-01 |
| G0-10 | SDK session tồn tại sau khi tạo lại engine; tiếng Việt UTF-8 | `test_conversations.py` |
| G0-11 | Memory CRUD, candidate, tìm không dấu, không trả "tất cả" khi không khớp | `test_memory_*.py` |
| G0-12 | Context Builder có budget, provenance, dropped | `test_context_builder.py` |
| G0-13 | Agent stream với `ScriptedModel`, usage lưu lại, tracing tắt, `store=False` | `test_agent_stream.py` |
| G0-14 | Gửi đồng thời trả 409, retry idempotent | `test_conversations.py` |
| G0-15 | Approval contract, S-03 có kết luận | `test_agent_approval.py` (P1) |
| G0-16 | Contract snapshot, `KnowledgeRetrieverContract` với fixture | `shared/tests` |
| G0-17 | Schema drift không có | `test_schema_drift.py` |
| G0-18 | Frontend không đổi; 54 Vitest vẫn pass | `git diff --stat`, `npm test` |
| G0-19 | Spike S-01..S-05 có kết luận | `docs/implementation/spikes/` |
| G0-20 | Hosted: lịch sử migration khớp repo, advisor không còn WARN `rls_auto_enable`, smoke pass và đã dọn | F0-10.3 |
| G0-21 | Cấu hình dashboard ghi trong báo cáo; Auth settings đúng | F0-11.1, `check_hosted_auth_settings.py` |

**Đạt G0:** mọi mục P0 pass; G0-15 có thể ở trạng thái P1 nhưng **phải** đạt trước G2.

## 4. Gate G1 — Phase 1

### 4.1 Backend

| Nhóm | Test ID | Tối thiểu |
|---|---|---|
| Auth | `I-AUTH-*` | JWT thật từ local Auth, token user đã xóa |
| Profile | `I-ME-*` | Lazy-create, cô lập, xóa tài khoản (P1) |
| Cases | `I-CASE-01..05` | Idempotent, version, chuyển trạng thái, tìm không dấu, cô lập |
| Timeline | `I-EVENT-01` | Không bịa ngày, chặn `mock_extracted` |
| Evidence | `I-EV-01..08` | Vòng đời, bất biến, quota, quyền tải, xóa có retry |
| Plans | `I-PLAN-01..05` | Một plan mỗi hồ sơ, reorder nguyên tử, version |
| Trusted contacts | `I-TC-01..03` | Cô lập, không có trường liên lạc |
| Sharing | `I-SHARE-01..04` | Phạm vi trường, rút lại, staff không thấy `cases` |
| Support drafts | `I-SD-01` | Không có giá trị `demo_*` |
| SQL | `P-00..07` | Như `03` §9 |

**Ma trận cô lập bắt buộc:** với mỗi route `/v1/*` có ID, có test user B nhận 404 trên tài nguyên của user A. Test tham số hóa, lấy danh sách route từ OpenAPI, nên route mới không có test sẽ fail.

### 4.2 Frontend E2E

| ID | Project | Kịch bản |
|---|---|---|
| `E-ONB` | demo, real | Welcome → Skip → Auth |
| `E-AUTH-01` | real | Đăng ký, màn xác nhận email (Inbucket local), đăng nhập |
| `E-AUTH-02` | real | Reload giữ phiên |
| `E-AUTH-03` | real | Deep link `/cases/:id` khi chưa đăng nhập, quay lại sau đăng nhập |
| `E-AUTH-04` | real | Sai mật khẩu hiện lỗi tiếng Việt |
| `E-AUTH-05` | real | A đăng xuất, B đăng nhập, không còn dữ liệu A |
| `E-DEMO-01` | demo | "Vào thử với tài khoản demo" như hiện tại |
| `E-DEMO-02` | real | Có `moodprint-demo` sẵn, đăng nhập thật không thấy hồ sơ mẫu |
| `E-CASE-01` | real | Wizard 6 bước, lưu nháp, reload, hoàn tất, xuất hiện ở Home và danh sách |
| `E-CASE-02` | real | Timeline thêm, sửa; tóm tắt; copy; tải `.txt` |
| `E-CASE-03` | real | Hai context cùng sửa → 409, không mất nhập |
| `E-EV-01..04` | real | Upload, xem, resume, hủy |
| `E-PLAN-01..02` | real | Plan đầy đủ; tick ở Home đồng bộ |
| `E-SUP-01` | real | Soạn, preview, lưu, copy; không có trạng thái "đã gửi" giả |
| `E-AI-01` | real | Chat mô phỏng có nhãn, không có request ghi |
| `E-URG-01` | real | Tắt FastAPI, `/support/urgent` vẫn mở, có `tel:111` |
| `E-SCH-01` | demo, real | School Admin Demo độc lập, không có request backend |
| Hiện có | demo | `journey`, `responsive` (14 route × 8 viewport), `entry-admin`, `ui-refinement` vẫn xanh |

**Existing E2E nào dùng gì:**

| Spec hiện có | Sau Phase 1 |
|---|---|
| `journey.spec.ts` | Giữ ở `demo`: luồng dài dựa trên fixture 8 ảnh, chat script, roleplay script. Không có giá trị thật để chạy với Supabase |
| `responsive.spec.ts` | Chạy cả `demo` và `real` (route sau đăng nhập) để bắt layout của trạng thái loading/error mới |
| `entry-admin.spec.ts` | `demo` |
| `ui-refinement.spec.ts` | `demo` |
| Mới `*-real.spec.ts` | `real`, cần local Supabase |

### 4.3 Phi chức năng

| ID | Tiêu chí |
|---|---|
| N-01 | Viewport 320/360/375/390/430/768/1024/1440: không tràn ngang trên route mới |
| N-02 | axe WCAG 2A/AA trên `/auth`, `/auth/reset`, upload, xóa tài khoản: không lỗi nghiêm trọng |
| N-03 | Không console error trong E2E |
| N-04 | Bundle không có `sb_secret_`, `sk-`, private key |
| N-05 | `real` không có request tới domain ngoài allow-list |
| N-06 | Không có log chứa nội dung hồ sơ, evidence text, memory (quét log của test integration) |
| N-07 | Trạng thái empty, loading, error, retry trên mọi màn chuyển sang dữ liệu thật |

**Đạt G1:** mọi mục P0 trong §4 pass, có báo cáo `phase-1-report.md`.

## 5. Gate G2

Xem `06` §8.

## 6. Agent smoke (Phase 0)

| ID | Kiểm | Chế độ |
|---|---|---|
| A-01 | `get_server_time` qua `Runner.run` | `ScriptedModel` |
| A-02 | Stream đúng thứ tự event | `ScriptedModel` |
| A-03 | Budget vượt → `tool_budget_exceeded` | `ScriptedModel` |
| A-04 | Timeout run → `run_timeout` | `ScriptedModel` chậm |
| A-05 | Hai conversation, memory tạo ở một cái xuất hiện trong context của cái kia | `ScriptedModel` + DB |
| A-06 | Live: một lượt tiếng Việt, ghi usage | `live_agent`, `gpt-6-luna`, trần chi phí |

A-06 là P1, chạy khi O-01 đã có `OPENAI_API_KEY`. **Không** chạy A-06 với nội dung giống dữ liệu thật của trẻ.

## 6.1 Quy tắc model và chấm điểm

- Mọi test, smoke, eval gọi OpenAI chỉ dùng `gpt-6-luna` (AD-14). Test `test_every_model_setting_is_gpt_6_luna` và `test_no_other_model_literal_in_source` chạy trong suite mặc định.
- Không có model judge. Không dùng metric LLM-as-judge (DeepEval `GEval`, `AnswerRelevancy`…, Promptfoo `llm-rubric`, `model-graded-*`).
- Assertion tất định chấm bằng code.
- Rubric chất lượng do coding agent đang chạy eval tự chấm, ghi `grades.jsonl` theo `05` §7. Case chưa có grade thì không tính là đạt.
- Báo cáo eval ghi: số case, số đạt assertion, điểm rubric trung bình theo tiêu chí, danh sách case dưới 2 điểm kèm lý do, agent chấm, commit.

## 7. Lệnh

```bash
uv sync --all-packages
uv run python scripts/check.py
npx supabase start
npx supabase db reset
npx supabase test db
uv run pytest -m integration
uv run python scripts/verify_phase0.py
uv run python scripts/verify_phase1.py
cd frontend && npm run typecheck && npm run lint && npm test && npm run build && npm run check:boundaries
cd frontend && npx playwright test --project=demo
uv run python scripts/e2e_stack.py --run   # project real
```
