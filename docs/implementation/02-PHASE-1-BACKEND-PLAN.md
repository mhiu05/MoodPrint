# Phase 1 — Real Backend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Dùng TDD và commit nhỏ.

**Goal:** thay mock bằng workflow thật có xác thực cho auth, hồ sơ, evidence, kế hoạch, người tin cậy, chia sẻ, và giữ nguyên trải nghiệm hiện có.

**Architecture:** thêm domain module vào backend Phase 0. Frontend có composition root chọn adapter theo `workspace.kind`. AI, Roleplay, Knowledge Hub, Voice, School Admin Demo giữ mock có nhãn.

**Tech Stack:** Phase 0 + `@supabase/supabase-js`, `tus-js-client`, `openapi-typescript`, Playwright.

**Spec:** bản yêu cầu của owner, `00`, `03`, `04`. **Điều kiện vào:** gate G0 (`07` §3) đạt.

## Global Constraints

- Mọi ràng buộc Phase 0 vẫn áp dụng.
- Không xóa component hiện có nếu chỉ cần đổi nguồn dữ liệu.
- Không feature flag rải rác. Lựa chọn adapter chỉ ở `frontend/src/services/composition.ts`.
- Không im lặng fallback sang dữ liệu mock khi request thật lỗi.
- Không trộn dữ liệu tổng hợp vào workspace thật. Không tự chuyển `moodprint-demo` lên server.
- Không lưu password trong bảng ứng dụng.
- Không có AI Vision, không có gửi thật ra ngoài ứng dụng.
- Không đổi thiết kế thị giác. Copy chỉ đổi khi đang nói sai sự thật (ví dụ "Chỉ lưu trên trình duyệt" trong workspace thật).
- `/support/urgent` chạy được khi backend chết và không đăng nhập.

## Review Focus

| # | Điều kiện | Kỳ vọng | Test tại |
|---|---|---|---|
| 1 | Mất mạng giữa upload evidence 20 MB trên mobile | Resume được, không tạo evidence trùng | F1-03.2 `E-EV-03` |
| 2 | Hai tab cùng sửa một hồ sơ hoặc kế hoạch | Tab sau thấy 409 và thông báo, nội dung nhập không mất | F1-02.2, F1-04.1 |
| 3 | Trình duyệt còn `moodprint-demo` cũ, rồi đăng nhập thật | Không thấy hồ sơ mẫu; dữ liệu demo còn nguyên khi quay lại demo | F1-07.3 |
| 4 | Token hết hạn khi đang viết wizard, rồi bấm Lưu | Refresh tự động; nếu thất bại thì giữ nội dung, yêu cầu đăng nhập, quay lại | F1-01.3 |
| 5 | Máy dùng chung: A đăng xuất, B đăng nhập | Không còn draft, cache, signed URL của A | F1-01.3 |

---

## F1-01 — Authentication

### F1-01.1 — Supabase client và AuthPort `[P0]`

- **Mục tiêu:** đăng ký, đăng nhập, đăng xuất, khôi phục phiên thật.
- **Phụ thuộc:** G0, F1-07.1.
- **File:** `frontend/src/services/supabase.ts`, `services/http/auth.ts`, `services/ports.ts`, `frontend/vite.config.ts` (`envDir: ".."`, `envPrefix: "VITE_PUBLIC_"`).
- **DB:** không. **API:** Supabase Auth, `GET /v1/me`.
- **Chi tiết:** `createClient` với publishable key, `persistSession: true`, `autoRefreshToken: true`, `detectSessionInUrl: true`, flow `pkce`. Token lấy qua `supabase.auth.getSession()` chỉ để gắn header, quyết định phân quyền luôn ở backend. `signUp` gửi `options.data = { nickname, age_band, start_interest }`. Không lưu email, password ở state ứng dụng.
- **Agent:** không.
- **Test:** `services/http/auth.test.ts`: `signup_passes_metadata_not_password_to_state`, `session_restored_on_load`, `logout_clears_session`.
- **Chấp nhận:** build production không chứa chuỗi `sb_secret_`; envPrefix không cho biến không có `VITE_PUBLIC_` lọt vào bundle.
- **Verify:** `npm run test && npm run build && npm run check:boundaries`

### F1-01.2 — Trang Auth, guard, xác minh email `[P0]`

- **Mục tiêu:** giữ nguyên layout `/auth`, đổi nội dung theo workspace.
- **Phụ thuộc:** F1-01.1. Chạy với hosted cần F0-11.1 (redirect URL, email confirmation).
- **File:** `features/auth/index.tsx`, `app/route-layouts.tsx`, `features/onboarding/index.tsx`, `features/profile/index.tsx`, `components/layout/StudentShell.tsx`.
- **Chi tiết:**
  - Form thật: bí danh, nhóm tuổi, email, mật khẩu, điều muốn bắt đầu. Giữ khu vực "Vào thử với tài khoản demo" tách biệt có nhãn.
  - Đăng ký có email confirmation: hiện màn "Kiểm tra email"; đăng nhập trước khi xác nhận hiện lỗi dễ hiểu.
  - Quên mật khẩu: `resetPasswordForEmail`, route mới `/auth/reset`.
  - `Guard`: chờ khởi tạo phiên, hiện `Skeleton`, không nháy về `/auth`.
  - `returnTo` giữ đúng kiểm tra open-redirect đang có.
  - Copy giả như "Chưa có tài khoản nào được tạo trên server" chỉ hiện ở demo.
  - Lỗi: `email_exists`, sai mật khẩu, rate limit, mạng, map sang tiếng Việt, không tiết lộ email có tồn tại hay không.
- **Test:** `auth.test.tsx`; E2E `E-AUTH-01..04`, `E-ONB`.
- **Chấp nhận:** deep link giữ nguyên sau đăng nhập; đăng ký không đưa thẳng vào app khi email chưa xác nhận.
- **Verify:** `npm test`, `npx playwright test e2e/auth-real.spec.ts`

### F1-01.3 — Phiên, hết hạn, đăng xuất `[P0]`

- **Mục tiêu:** xử lý các ca khó của phiên.
- **Phụ thuộc:** F1-01.2, F1-07.2.
- **File:** `services/http/client.ts`, `services/session-reset.ts`.
- **Chi tiết:** `apiFetch` gắn Bearer, gặp 401 thì `refreshSession()` một lần rồi retry; thất bại thì chuyển `/auth` kèm `returnTo`, **không** xóa sessionStorage draft của wizard. Đăng xuất chủ động: `supabase.auth.signOut()`, xóa store, xóa key `moodprint-*-draft-v1:<userId>:*`, `moodprint-sim-v1:<userId>`.
- **Test:** `client.test.ts`: `retry_once_after_refresh`, `no_infinite_retry`, `401_preserves_draft`; E2E `E-AUTH-05` (A đăng xuất, B đăng nhập không thấy gì của A).
- **Chấp nhận:** không có vòng lặp refresh.
- **Verify:** `npm test`

---

## F1-02 — Incident management

### F1-02.1 — Migration và module cases `[P0]`

- **Mục tiêu:** `cases`, `case_events`, tạo, đọc, xóa.
- **Phụ thuộc:** G0.
- **File:** `*_f1_cases.sql`, `backend/app/modules/incidents/*`, `backend/app/api/v1/cases.py`.
- **DB:** `cases`, `case_events`, FK ghép `conversations.linked_case_id`.
- **API:** `POST/GET /v1/cases`, `GET/DELETE /v1/cases/{id}`.
- **Agent:** implement `IncidentService.list_cases`, `get_case`.
- **Test:** `I-CASE-01` `test_create_active_requires_summary`, `test_draft_allows_empty`, `test_create_idempotent_same_id`, `test_create_with_first_event`; `I-CASE-02` `test_list_only_own`, `test_filter_status`, `test_search_without_diacritics`, `test_sort_title_vi`, `test_cursor_pagination`, `test_plan_progress_in_summary`; `I-CASE-04` `test_delete_cascades`, `test_delete_unlinks_conversation`, `test_user_b_404`.
- **Chấp nhận:** pgTAP `01`, `02` cập nhật và pass.
- **Verify:** `npx supabase db reset && uv run pytest -m integration backend/tests/integration/test_cases.py`

### F1-02.2 — Cập nhật và version `[P0]`

- **Mục tiêu:** `PATCH /v1/cases/{id}` có optimistic concurrency, chuyển trạng thái đúng sơ đồ.
- **Phụ thuộc:** F1-02.1.
- **API:** `PATCH /v1/cases/{id}`.
- **Chi tiết:** cho phép chuyển `draft→active`, `active↔monitoring`, `active|monitoring→closed`, `closed→active`. Sai trả 422. Trạng thái do người dùng tự đổi, không ngụ ý xác nhận từ trường.
- **Test:** `I-CASE-03` `test_stale_version_409_returns_latest`, `test_invalid_transition_422`, `test_closed_case_still_readable`.
- **Chấp nhận:** 409 có `details.latest`.
- **Verify:** `uv run pytest -m integration backend/tests/integration/test_cases.py -k version`

### F1-02.3 — Timeline `[P0]`

- **Mục tiêu:** quản lý mốc theo provenance.
- **Phụ thuộc:** F1-02.1.
- **API:** `POST/PATCH/DELETE /v1/cases/{id}/events[/{eventId}]`.
- **Agent:** implement `IncidentService.add_event`.
- **Test:** `I-EVENT-01` `test_unknown_time_never_invents_date`, `test_exact_requires_datetime`, `test_day_requires_date`, `test_client_cannot_set_mock_extracted`, `test_user_entered_default`, `test_when_round_trip_matches_ui_type`, `test_edit_does_not_touch_evidence`, `test_events_sorted_nulls_last`.
- **Chấp nhận:** `when` trả về khớp logic sắp xếp ở `CaseDetail`.
- **Verify:** `uv run pytest -m integration backend/tests/integration/test_case_events.py`

### F1-02.4 — Hồ sơ liên quan `[P1]`

- **Mục tiêu:** thay `related` client-side.
- **Phụ thuộc:** F1-02.1.
- **API:** `GET /v1/cases/{id}/related`.
- **Test:** `I-CASE-05` `test_max_three_same_owner_excludes_self`, `test_prefers_tag_overlap`.
- **Chấp nhận:** tối đa 3.
- **Verify:** `uv run pytest -m integration -k related`

---

## F1-03 — Evidence

### F1-03.1 — Backend evidence `[P0]`

- **Mục tiêu:** vòng đời file theo `03` §7.
- **Phụ thuộc:** F1-02.1, F0-06.2.
- **File:** `*_f1_evidence.sql`, `backend/app/modules/evidence/*`, `backend/app/api/v1/evidence.py`.
- **DB:** `evidence_items`, `case_event_evidence`, `evidence_derivatives`, trigger bất biến.
- **API:** toàn bộ nhóm Evidence ở `04` §3.
- **Agent:** implement `EvidenceService`.
- **Chi tiết:** transaction DB ngắn: tạo row trước, rồi gọi Storage **ngoài** transaction. Kiểm quota bằng tổng `byte_size` cộng dự kiến. `complete` lấy `object_info`, kiểm size khớp, đặt `uploaded`. `purpose` trong `open_read_url` ghi audit.
- **Test:** `I-EV-01` `test_init_creates_pending_with_safe_key`, `test_filename_only_in_metadata`, `test_init_idempotent`, `test_oversize_413`, `test_quota_429`; `I-EV-02` `test_complete_requires_object`, `test_complete_size_mismatch_failed`, `test_complete_twice_idempotent`; `I-EV-03` `test_download_url_owner_only`, `test_download_audited`, `test_pending_has_no_url`; `I-EV-04` `test_note_has_no_file`, `test_unlinked_listed`; `I-EV-05` `test_patch_cannot_change_original_text`, `test_edit_keeps_original`, `test_review_status_values`; `I-EV-06` `test_unlink_keeps_file`, `test_unlink_removes_from_events`, `test_delete_removes_object_and_row`, `test_storage_failure_stays_deleting_then_retries`; `I-EV-07` `test_derivative_never_changes_original`, `test_derived_key_prefix`; `I-EV-08` `test_user_b_404_all_routes`.
- **Chấp nhận:** evidence đầy đủ provenance; `original_text` không đổi được kể cả qua SQL với role `authenticated`.
- **Verify:** `uv run pytest -m integration backend/tests/integration/test_evidence.py`

### F1-03.2 — UI upload `[P0]`

- **Mục tiêu:** chọn file thật, tiến độ, resume.
- **Phụ thuộc:** F1-03.1, F1-07.2.
- **File:** `features/incidents/evidence.tsx`, `index.tsx`, `wizard.tsx`, `services/http/evidence.ts`, `services/mock/evidence.ts`.
- **Chi tiết:**
  - `real`: `<input type="file" multiple accept="image/*,audio/*,video/*,application/pdf,*/*">` thêm nút "Thêm tệp", giữ khu vực ghi chú. Không gọi fixture.
  - `demo`: giữ `EvidencePicker` hiện tại.
  - TUS: `endpoint` hostname `<ref>.storage.supabase.co`, `chunkSize` từ API, `retryDelays`, `removeFingerprintOnSuccess: true`, `findPreviousUploads` để resume. Khi 401, gọi `upload-token` rồi tiếp tục.
  - Wizard: file tải ngay, `draft.attachments` chỉ giữ `evidenceId`, nên không vượt quota sessionStorage. Lưu hồ sơ thì link.
  - SHA-256 phía client: P2, bỏ qua với file quá 200 MB.
  - Hiển thị: tiến độ, hủy, thử lại, loading/empty/error, giữ tiêu chí touch target 44px.
  - Ảnh xem bằng signed URL, không lưu URL vào store, refetch khi hết hạn.
  - Bỏ `window.confirm` hiện có ở thao tác bỏ nguồn, dùng `Modal` sẵn có, cũng để Playwright không bị chặn.
- **Test:** `evidence.test.tsx`; E2E `E-EV-01` upload ảnh, reload còn; `E-EV-02` xem qua signed URL; `E-EV-03` chặn route giữa chừng rồi resume; `E-EV-04` hủy upload không để lại evidence hiển thị.
- **Chấp nhận:** wizard vẫn lưu được khi không có tệp.
- **Verify:** `npm test`, `npx playwright test e2e/evidence-real.spec.ts`

---

## F1-04 — Action Plans

### F1-04.1 — Backend plan `[P0]`

- **Mục tiêu:** mô hình một plan mỗi hồ sơ.
- **Phụ thuộc:** F1-02.1.
- **File:** `*_f1_plans.sql`, `backend/app/modules/plans/*`, `backend/app/api/v1/plans.py`.
- **DB:** `action_plans`, `plan_items`.
- **API:** `GET/PUT /v1/cases/{id}/plan`, `PATCH /v1/plans/{id}/items/{itemId}`, `GET /v1/plans/active`.
- **Agent:** implement `ActionPlanService`.
- **Chi tiết:** `PUT` upsert trong một transaction: thêm, sửa, xóa item theo mảng, đặt `position` theo chỉ số. Validate giống `validatePlan`.
- **Test:** `I-PLAN-01` `test_upsert_creates`, `test_one_plan_per_case`, `test_reorder_atomic`; `I-PLAN-02` `test_pause_resume`, `test_completed_requires_all_done`, `test_review_date`, `test_notes_persist`; `I-PLAN-03` `test_stale_version_409`; `I-PLAN-04` `test_item_patch_bumps_version`, `test_active_plan_for_home`, `test_multiple_cases_not_mixed`; `I-PLAN-05` `test_user_b_404`, `test_no_field_claims_contact_or_resolution`.
- **Chấp nhận:** thứ tự giữ nguyên sau reload.
- **Verify:** `uv run pytest -m integration backend/tests/integration/test_plans.py`

### F1-04.2 — UI plan và Home `[P0]`

- **Mục tiêu:** Home và trang plan dùng cùng state đã persist.
- **Phụ thuộc:** F1-04.1, F1-07.2.
- **File:** `features/action-plans/index.tsx`, `features/home/index.tsx`, `services/http/plans.ts`, `services/mock/plans.ts`.
- **Chi tiết:** giữ `mergePlanDraft`, thay `JSON.stringify(baseRevision)` bằng `version`. 409 dùng thông báo có sẵn. Tick ở Home gọi `PATCH` item, lỗi thì rollback tick và hiện toast, không báo thành công giả.
- **Test:** cập nhật `plans.test.tsx`, `model.test.ts`; E2E `E-PLAN-01` tạo, reorder, pause, reload; `E-PLAN-02` tick ở Home, sang plan thấy đúng.
- **Chấp nhận:** tiêu chí F3 của PRD đạt trên dữ liệu thật.
- **Verify:** `npx playwright test e2e/plans-real.spec.ts`

---

## F1-05 — Trusted contacts `[P0]`

- **Mục tiêu:** lưu người tin cậy theo chủ sở hữu.
- **Phụ thuộc:** G0, F1-07.2.
- **File:** `*_f1_trusted_contacts.sql`, `backend/app/modules/contacts/*`, `backend/app/api/v1/trusted_contacts.py`, `features/support/index.tsx`, `features/incidents/wizard.tsx`.
- **DB:** `trusted_contacts`.
- **API:** `/v1/trusted-contacts`.
- **Agent:** Support Tool đọc ở Phase 3, chỉ tiết lộ `label`, `role`.
- **Chi tiết:** workspace thật không seed sẵn "Giáo viên mình tin tưởng". Không có trường liên lạc. Không có gửi tin.
- **Test:** `I-TC-01` `test_crud`, `test_length_limits`; `I-TC-02` `test_user_b_404`; `I-TC-03` `test_schema_has_no_contact_fields`.
- **Chấp nhận:** dữ liệu còn sau reload, thiết bị khác cũng thấy.
- **Verify:** `uv run pytest -m integration backend/tests/integration/test_trusted_contacts.py`

---

## F1-06 — School sharing

### F1-06.1 — Mô hình chia sẻ `[P0]`

- **Mục tiêu:** hợp đồng ổn định, không có truy cập toàn cục cho trường.
- **Phụ thuộc:** F1-03.1.
- **File:** `*_f1_sharing.sql`, `backend/app/modules/sharing/*`, `backend/app/api/v1/{shares,schools,school_access}.py`.
- **DB:** `schools`, `school_memberships`, `case_shares`, `case_share_evidence`.
- **API:** nhóm Sharing ở `04` §3.
- **Chi tiết:**
  - Chỉ học sinh khởi tạo. Không có API staff yêu cầu hồ sơ.
  - `sharedFields` mặc định rỗng. Preview hiển thị chính xác nội dung và cả định danh. Với `alias`: dùng bí danh, kèm giải thích không phải ẩn danh tuyệt đối, đúng D08.
  - `submit` kiểm `previewHash`, yêu cầu Auth live (AD-07), tạo snapshot, ghi audit.
  - Không gửi email, không gọi hệ thống trường.
  - Trường chỉ là seed `synthetic` trong local test. Hosted không seed.
- **Agent:** không có tool. Agent **không** thể submit.
- **Test:** `I-SHARE-01` `test_draft_has_no_school_visibility`, `test_submit_requires_confirmation`, `test_preview_hash_mismatch_409`, `test_snapshot_only_selected_fields`, `test_snapshot_immutable_after_case_edit`; `I-SHARE-02` `test_staff_school_x_sees_submitted`, `test_staff_school_y_404`, `test_staff_cannot_read_cases_table`, `test_staff_cannot_read_unselected_evidence`, `test_staff_cannot_list_all_students`; `I-SHARE-03` `test_withdraw_removes_access_immediately`, `test_delete_case_withdraws_share`; `I-SHARE-04` `test_evidence_download_by_staff_audited`, `test_non_member_403`, `test_no_global_admin_role_exists`.
- **Chấp nhận:** pgTAP `04_school_scope.sql` pass.
- **Verify:** `npx supabase test db && uv run pytest -m integration backend/tests/integration/test_sharing.py`

### F1-06.2 — Support drafts `[P1]`

- **Mục tiêu:** bản nháp hỗ trợ không còn nằm local ở workspace thật.
- **Phụ thuộc:** F1-02.1, F1-07.2.
- **File:** `*_f1_support_drafts.sql`, `backend/app/modules/support/*`, `backend/app/api/v1/support_drafts.py`, `features/support/index.tsx`.
- **API:** `/v1/support-drafts`.
- **Chi tiết:** `real` chỉ có `draft|prepared`. Giữ preview, copy, download, recovery. Theo quy tắc `04` §5.
- **Test:** `I-SD-01` `test_crud`, `test_delete_case_keeps_draft_unlinked`, `test_status_rejects_demo_values`; `E-SUP-01`.
- **Chấp nhận:** UI không có "đã gửi trường" khi không có `case_shares`.
- **Verify:** `npx playwright test e2e/support-real.spec.ts`

### F1-06.3 — UI chia sẻ tối thiểu `[P2]`

- **Mục tiêu:** học sinh chọn trường, chọn trường dữ liệu, xác nhận.
- **Phụ thuộc:** F1-06.1, và O-11 có trường thật hoặc synthetic test.
- **Chi tiết:** có thể hoãn vì chưa có trường đối tác. Contract đã ổn định từ F1-06.1. Khi `GET /v1/schools` rỗng thì hiện "Chưa có trường kết nối".
- **Chấp nhận:** E2E với seed synthetic trên local.
- **Verify:** `npx playwright test e2e/sharing-real.spec.ts`

---

## F1-07 — Frontend integration

### F1-07.1 — Chuẩn bị boundary `[P0]`

- **Mục tiêu:** tooling cho phép mạng, nhưng vẫn giữ an toàn.
- **Phụ thuộc:** G0.
- **File:** `frontend/scripts/check-boundaries.mjs`, `package.json`, `e2e/journey.spec.ts`, `frontend/README.md`, `README.md` root.
- **Chi tiết:**
  - Network: chỉ cho `fetch` trong `src/services/http/`; `getUserMedia`, `WebSocket`, `sendBeacon` vẫn cấm toàn bộ.
  - Dependency: cho `@supabase/supabase-js`, `tus-js-client`; vẫn cấm `openai`, `aws-sdk`, `apify`.
  - Secret: thêm `sb_secret_`. Giữ pattern JWT, vì dùng `sb_publishable_`, không dùng legacy anon JWT.
  - Pin `thinking-orbs`.
  - Tách `page.screenshot` ghi vào `docs/prototype/screenshots/` ra sau biến `CAPTURE_SCREENSHOTS=1`, để test không làm bẩn file đã track.
  - `npm i` thêm `@supabase/supabase-js`, `tus-js-client`, `openapi-typescript` (dev), pin qua lockfile.
- **Test:** script fail với file giả có `fetch` ngoài `services/http/`.
- **Chấp nhận:** cả suite cũ còn xanh, chạy E2E không đổi file đã track.
- **Verify:** `npm run build && npm run check:boundaries && npm run test:e2e && git status --short docs/prototype/screenshots`

### F1-07.2 — Ports, composition, store `[P0]`

- **Mục tiêu:** tách UI khỏi nguồn dữ liệu, thay đổi tối thiểu.
- **Phụ thuộc:** F1-07.1.
- **File tạo:** `src/services/ports.ts`, `composition.ts`, `workspace.ts`, `http/client.ts`, `http/schema.gen.ts`, `http/mappers.ts`, `mock/*.ts`.
- **File sửa:** `src/types/index.ts`, `src/app/store.ts`, các điểm ghi trực tiếp liệt kê ở `00` §1.2.
- **Chi tiết:**
  - `types`: `demo: true` → `demo?: boolean`, `AgeBand` giữ en dash ở UI, mapper chuyển. Thêm `version?: number`.
  - Đổi tên store thành `useWorkspaceStore`, giữ `useDemoStore` làm alias export để diff nhỏ. Persist chỉ khi `kind === "demo"`. `real`: store là cache trong bộ nhớ, nạp từ port.
  - `services/mock/*` bọc `demoService` hiện có, giữ độ trễ và `failNextSave`.
  - Mọi ghi đi qua port. Danh sách điểm cần đổi: `incidents/index.tsx` (`persist`, `saveEvent`, `attach`, `putEvidence`, `deleteCase`), `wizard.tsx`, `home/index.tsx`, `support/index.tsx`, `knowledge/index.tsx`, `profile/index.tsx`, `action-plans/index.tsx`.
  - Không thêm React Query ở bước này. Refetch sau mutation là đủ cho một người dùng. Nếu F1-08 cho thấy cần thì đánh giá riêng.
  - Loading và lỗi: thêm trạng thái hydrate ở `Root`, dùng `Skeleton`, `Notice`, retry sẵn có. Lỗi hydrate hiện nút thử lại, không hiện dữ liệu rỗng giả.
- **Test:** `composition.test.ts`: `real_never_returns_mock_case_port`, `http_error_does_not_fall_back_to_mock`, `demo_uses_only_mock`, `sim_ports_labeled`; suite Vitest cũ chạy ở `demo` không đổi kỳ vọng.
- **Chấp nhận:** không có `import { useDemoStore }` cho mục đích ghi ngoài `services/mock`; 54 test cũ vẫn pass (hoặc thay đổi có giải thích).
- **Verify:** `npm test && npm run typecheck && npm run lint`

### F1-07.3 — Xử lý state demo cũ `[P0]`

- **Mục tiêu:** quy tắc rõ ràng với dữ liệu mock trong trình duyệt.
- **Phụ thuộc:** F1-07.2.
- **File:** `services/workspace.ts`, `features/profile/index.tsx`.
- **Quyết định:**
  - `moodprint-demo`, `moodprint-school-demo` **không** bao giờ gửi lên server, không migrate.
  - Đăng nhập thật không đọc, không xóa `moodprint-demo`.
  - Vào demo khi đang có phiên thật: yêu cầu đăng xuất trước, tránh hai workspace cùng lúc.
  - Settings ở `real` có "Xóa dữ liệu demo trên trình duyệt này".
  - "Khôi phục dữ liệu mẫu" chỉ hiện ở `demo`.
  - "Mô phỏng lỗi ở lần lưu tiếp theo" chỉ hiện ở `demo`.
- **Test:** `workspace.test.ts`: `existing_demo_state_not_visible_in_real`, `demo_state_intact_after_real_session`, `no_demo_payload_sent` (assert request body); E2E `E-DEMO-02`.
- **Chấp nhận:** Review Focus #3 đạt.
- **Verify:** `npx playwright test e2e/workspace-separation.spec.ts`

### F1-07.4 — Banner và copy trung thực `[P0]`

- **Mục tiêu:** người dùng luôn biết cái gì mô phỏng.
- **Phụ thuộc:** F1-07.2.
- **File:** `features/ai/*`, `features/profile/index.tsx`, `features/incidents/*`, `features/onboarding/index.tsx`.
- **Chi tiết:** `real`: "AI mô phỏng" giữ ở Chat, Analysis, Roleplay, thêm notice nội dung nằm trên thiết bị. Thay copy "demo" ở chức năng thật ("Đã lưu hồ sơ", không "trong demo"). Chặn fixture theo `04` §5. Welcome không còn nói "không gửi thông tin ra ngoài" ở bản có backend.
- **Test:** `copy.test.tsx`; E2E `E-AI-01`: chat mô phỏng trong `real` có nhãn, không tạo request ghi.
- **Chấp nhận:** không có chữ "demo" trên hồ sơ thật; có nhãn mô phỏng trên mọi tính năng mô phỏng.
- **Verify:** `npm test`

### F1-07.5 — Bookmark, đã đọc, profile `[P1]`

- **Mục tiêu:** phần còn lại của personal scope.
- **Phụ thuộc:** F1-07.2.
- **File:** `*_f1_knowledge_state.sql`, `backend/app/modules/knowledge_state/*`, `features/knowledge/index.tsx`, `features/profile/index.tsx`.
- **API:** `/v1/knowledge/article-states`, `PATCH /v1/me`.
- **Test:** `I-KS-01` `test_bookmark_toggle`, `test_read_timestamp`, `test_owner_only`.
- **Chấp nhận:** đồng bộ giữa thiết bị.
- **Verify:** `uv run pytest -m integration -k article_state`

### F1-07.6 — Xóa tài khoản `[P1]`

- **Mục tiêu:** quyền xóa dữ liệu.
- **Phụ thuộc:** F1-03.1, F1-06.1.
- **API:** `DELETE /v1/me`.
- **Chi tiết:** thứ tự ở `03` §6, xác nhận hai bước trong Settings. Idempotent nếu bước giữa lỗi.
- **Test:** `I-ME-05` `test_delete_removes_storage_auth_and_rows`, `test_partial_failure_resumable`.
- **Chấp nhận:** không còn row và object của user.
- **Verify:** `uv run pytest -m integration -k delete_account`

---

## F1-08 — Integration và regression

### F1-08.1 — Hạ tầng E2E `[P0]`

- **Mục tiêu:** chạy E2E hai chế độ.
- **Phụ thuộc:** F1-07.2.
- **File:** `frontend/playwright.config.ts`, `frontend/e2e/helpers/*`, `scripts/e2e_stack.py`.
- **Chi tiết:** hai project Playwright.

| Project | Môi trường | Spec |
|---|---|---|
| `demo` | Vite, không backend | `journey`, `responsive`, `entry-admin`, `ui-refinement` |
| `real` | Local Supabase + FastAPI + Vite, user tạo bằng script | `*-real.spec.ts`, `workspace-separation` |

Bảo đảm `demo` vẫn assert không có request ra ngoài. `real` allow-list API và Supabase local, assert không có request tới `*.supabase.co` hay `api.openai.com`.

- **Test:** tự thân.
- **Chấp nhận:** `npm run test:e2e -- --project=demo` không cần Docker.
- **Verify:** `uv run python scripts/e2e_stack.py --run`

### F1-08.2 — Hồi quy và báo cáo `[P0]`

- **Mục tiêu:** đạt gate G1.
- **Phụ thuộc:** tất cả task P0.
- **File:** `scripts/verify_phase1.py`, `docs/implementation/reports/phase-1-report.md`.
- **Chi tiết:** chạy toàn bộ `07` §4, gồm E2E 320, 390, 1440 px, responsive 14 route, axe trên các route auth mới, `E-URG-01` khi tắt backend.
- **Chấp nhận:** G1 đạt, báo cáo nêu phần mô phỏng còn lại.
- **Verify:** `uv run python scripts/verify_phase1.py`

### F1-08.3 — Áp dụng lên hosted `[P0]`

- **Mục tiêu:** hosted có schema Phase 1, smoke với user tổng hợp. Agent tự làm.
- **Phụ thuộc:** F1-08.2.
- **Chi tiết:** như F0-10.3, `push_hosted.py --dry-run` rồi `--apply`. Smoke bằng API: user test tổng hợp, tạo hồ sơ, upload 1 MB, tải, xóa, xóa user. Thêm smoke giao diện bằng Chrome: mở frontend dev trỏ vào hosted, đăng ký user `@example.test`, xác nhận qua admin API, tạo một hồ sơ, reload, xóa tài khoản. Chạy `get_advisors`.
- **Chấp nhận:** advisor không có lỗi bảo mật mới. Không còn dữ liệu test.
- **Verify:** `uv run python scripts/smoke_hosted.py --phase 1`

## Tiêu chí xong

- [ ] Mọi task P0 pass.
- [ ] Gate G1 (`07` §4) đạt.
- [ ] Không có fallback mock im lặng.
- [ ] Báo cáo `phase-1-report.md` đã tạo.
- [ ] Không tuyên bố đã sẵn sàng cho dữ liệu thật: §6 của `00` vẫn áp dụng.
