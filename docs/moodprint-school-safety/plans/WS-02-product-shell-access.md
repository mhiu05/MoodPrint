# WS-02 — Product shell và truy cập

Ưu tiên P0. Độ phức tạp M: thay đổi nhỏ nhưng chạm cổng eligibility toàn cục. Nhánh `mhiu05/feat-refactor-ws02-access`.

## 1. Mục tiêu và giá trị

Học sinh hư cấu 11–17 vào được sản phẩm mới bằng tài khoản demo, xác nhận điều khoản ngắn. Production 18+ không đổi.

## 2. Hiện trạng đã xác minh

- `verify_actor` gọi `is_adult_eligible` cho mọi `transaction(eligible=True)`. `_session_view` tính `eligible` riêng.
- `POST /auth/login` tự tạo `users` và `consents` cho mọi tài khoản Supabase hợp lệ.
- `POST /auth/signup` mở, chỉ kiểm tra tuổi.
- `deploy.sh` bắt buộc `APP_ENV=production`.
- `/public/experience` đọc được không cần danh tính, chỉ dựa cấu hình.
- Guest: frontend gửi `persistent` theo `historyAvailable`, không ép tạm.

## 3. Khoảng trống

Không có khái niệm profile, nhóm tuổi 11–17, điều khoản demo, route public cho hỗ trợ.

## 4. Kiến trúc đề xuất

- `APP_PROFILE` trong `Settings`. Validator ép tắt các cờ, ghi vào `_clamped`, không raise.
- `Database` truyền profile qua `async_sessionmaker(..., info={"app_profile": ...})`. `verify_actor` đọc `db.info`. Không dùng biến global, để nhiều app trong test không ảnh hưởng nhau.
- `require_school_eligible`: khi profile demo, cần hàng `school_profiles` và `terms_accepted_at`, thay cho adult. Hai cổng đổi: `verify_actor`, `_session_view`. 13 call site `is_adult_eligible` còn lại giữ nguyên: chúng phục vụ tính năng bị tắt, và **không** được mở cho trẻ vị thành niên.
- `ProfileRouteGuard`: middleware trả 404 envelope cho denylist khi demo.

**Vì sao không dùng hàng DB làm quyền duy nhất**: tránh việc tồn tại hàng `school_profiles` mở cổng trên production. Cần cả profile lẫn hàng.

## 5. Phạm vi

Trong: profile, cổng, điều khoản, seed, guest tạm, chọn shell. Ngoài: UI các tab (WS-09).

## 6. File và symbol bị ảnh hưởng

`core/config.py` (`Settings`, `FEATURE_FLAGS`); `infrastructure/database/connection.py` (`Database`); `core/security.py` (`verify_actor`); `modules/auth/routes.py` (`_session_view`, `signup`); `modules/guests/availability.py`, `schemas.py`, `service.py`; `ai/chat_routes.py` (`create_conversation`); `ai/agents.py`; `ai/prompts.py` (`RUNTIME_VARIANTS`, `VERSIONS`); `contracts.py` (`BotId`, `FeatureView`, `SessionView`); `main.py`; `frontend/src/AppEntry.tsx`, `appEntryRoute.ts`; `frontend/src/companions/registry.ts`.

## 7. File mới

`backend/app/core/profile.py`; `backend/app/modules/school/{__init__,models,schemas,service,routes,eligibility}.py`; `backend/app/modules/school/seed/personas.json`; `scripts/seed_school_demo.py`; `backend/alembic/versions/0030_school_profiles.py`; `frontend/src/features/school/{SchoolApp.tsx,school.css,useExperience.ts,TermsGate.tsx,SchoolLanding.tsx}`.

## 8. API contract

```python
class TermsView(DTO):
    terms_version: str
    accepted_at: datetime | None
    age_group: Literal["11-14", "15-17"] | None
    version: int

class TermsAccept(DTO):
    terms_version: str
    age_group: Literal["11-14", "15-17"]
    expected_version: int = Field(ge=1)
```

| Route | Mô tả | Lỗi |
| --- | --- | --- |
| `GET /api/v1/school/terms` | Dùng `eligible=False` | 404 ở profile default |
| `PUT /api/v1/school/terms` | Cần `Idempotency-Key` | `TERMS_VERSION_MISMATCH`, `STALE_VERSION` |
| `GET /api/v1/public/experience` | Thêm `appProfile: "default" \| "school_safety_demo"`, `termsVersion` | |
| `POST /api/v1/auth/signup` | Demo: 403 `SIGNUP_CLOSED` | |

`FeatureView` thêm `schoolSafety: bool`, `ageGroup`, `termsRequired: bool`.

**Denylist khi demo** (`core/profile.py`, so theo tiền tố đường dẫn sau `/api/v1`, lấy từ `backend/openapi.json` tại HEAD đã review): `/activities`, `/admin`, `/ai/groups`, `/ai/inbox`, `/ai/maps-searches`, `/ai/proactive`, `/ai/prompt-capabilities`, `/ai/sharing`, `/blocks`, `/connection-requests`, `/connections`, `/feedback`, `/journal`, `/matching`, `/memories`, `/moods`, `/profiles`, `/proposals`, `/reports`, `/reveal-grants`, `/reveal-requests`, `/social`, `/taxonomy`.

Giữ: `/ai/conversations`, `/ai/preferences`, `/ai/runs`, `/auth/*`, `/bots`, `/consents`, `/data-deletions`, `/exports`, `/health`, `/public/experience`, `/session`, `/users/me`, `/voice`, cùng các route mới. Test ở T04 sinh danh sách từ `app.routes`, nên route thêm sau này mà chưa phân loại sẽ làm test fail.

## 9. Dữ liệu và migration

`0030_school_profiles`, xem [05 §2](../05-data-model-and-migrations.md#2-nhận-dạng-và-điều-khoản).

## 10. Task

Viết test thất bại trước, rồi code.

| ID | Ưu tiên | Phụ thuộc | Thay đổi, ở đâu | Hành vi mong đợi | Lệnh test | Pass / fail |
| --- | --- | --- | --- | --- | --- | --- |
| WS-02-T01 | P0 | WS-01 | `app_profile`, `terms_version_current` trong `Settings`; validator `apply_profile`; `core/profile.py` với `FORCED_OFF`, `DEMO_DENYLIST`, `is_demo()`; cập nhật 3 file env example, `docs/backend/configuration.md` | Demo: mọi cờ trong `FORCED_OFF` là false kể cả khi env đặt true; `degraded_features` liệt kê; default: không đổi | `pytest -q tests/test_school_settings.py tests/test_default_flags.py` | Pass: `Settings()` default bằng snapshot cũ. Fail: bất kỳ flag default đổi |
| WS-02-T02 | P0 | T01 | Migration 0030, ORM `SchoolProfile`, `troly` vào `ALL_IDS`, `BotId`, `DISPLAY_NAMES`, `RUNTIME_VARIANTS` (`assistant`), `VERSIONS`; frontend `BotId` | `alembic upgrade head`, `alembic check` sạch; `is_v3("troly")` false; `is_legacy("troly")` false; `/bots` không liệt kê `troly` ở default | `pytest -q tests/test_school_migration.py tests/test_foundation.py`; `alembic check` | Pass: head 0030. Fail: drift |
| WS-02-T03 | P0 | T02 | `Database.__init__` thêm `info`; `school/eligibility.py::is_eligible(db, user)`; đổi `verify_actor`, `_session_view` | Demo + đủ điều kiện: 200; demo + 18+ không có hàng: 403 `ELIGIBILITY_REQUIRED` với thông điệp demo; default + có hàng `school_profiles` nhưng `age_band=teen`: vẫn 403 | `pytest -q tests/test_school_eligibility.py tests/test_eligibility.py` | Pass: 4 tổ hợp đúng. Fail: default thay đổi |
| WS-02-T04 | P0 | T01 | `ProfileRouteGuard` trong `main.py`, chạy trong `BodyLimitMiddleware` | Demo: route denylist 404 `NOT_FOUND`; route giữ lại không đổi; default: không có route nào bị chặn. Test sinh danh sách từ `app.routes` và so với bảng phân loại đầy đủ | `pytest -q tests/test_school_route_guard.py` | Pass: mọi route được phân loại. Fail: route chưa phân loại |
| WS-02-T05 | P0 | T03 | `signup` 403 khi demo; `experience_view` thêm trường; `FeatureView` thêm trường; OpenAPI, schema.d.ts, api-reference | Đăng ký đóng; login tài khoản thường trả session với `eligible=false` | `pytest -q tests/test_school_auth.py`; `npm run contracts:generate` | Pass: không drift |
| WS-02-T06 | P0 | T03 | `school/routes.py` terms; router trong `main.py` | Xác nhận lưu `terms_version`, thời điểm; đổi phiên bản bắt xác nhận lại; 404 ở default | `pytest -q tests/test_school_terms.py` | Pass: replay idempotent |
| WS-02-T07 | P1 | T06 | Guest demo: `GuestEligibility` nhận `school-terms-v1` với `age_group` (không dùng `birth_year`); `create_conversation` ép `persistent=False` cho guest khi demo; từ chối `case`, `practice` | Không có `ai_messages` của guest; disclosure nói thật. `/auth/guest` giữ nguyên ở default | `pytest -q tests/test_school_guest.py tests/test_guest*.py` | Pass: 0 hàng `ai_messages`. Fail: có hàng |
| WS-02-T08 | P0 | T06 | `scripts/seed_school_demo.py --apply \| --reset \| --rotate`; Auth Admin qua `httpx`, key từ environment; email `*@demo.moodprint.invalid` hoặc miền owner chỉ định; `email_confirm=true`; mật khẩu ngẫu nhiên, không in, ghi vào file mode 600 do người chạy chỉ định | Idempotent; `--reset` chỉ xóa dữ liệu user có `demo_persona` không NULL; từ chối chạy nếu `SUPABASE_URL` không khớp project; `--rotate` đổi mật khẩu | `pytest -q tests/test_seed_school_demo.py` với transport giả | Pass: không chạm user khác |
| WS-02-T09 | P0 | T05 | `classifyEntry` nhận `/ho-tro`, `/trung-tinh`; `useExperience`; `AppEntry` chọn `SchoolApp` khi demo; `TermsGate`; `SchoolLanding`; không tải `RealApp` trong demo | Default: DOM giống cũ, test `appEntryRoute` cũ pass. Demo: landing mới, login, điều khoản | `npm test`; `npx playwright test tests/e2e/school-entry.spec.ts` | Pass: spec cũ không đổi |
| WS-02-T10 | P1 | T02 | Thêm `school_profiles` vào `modules/users/export.py`; kiểm tra purge | Export có; xóa tài khoản xóa hàng | `pytest -q tests/test_data_lifecycle.py` | Pass |

## 11. An toàn và bảo mật

- `FORCED_OFF` không cho phép bật qua env.
- Mọi kiểm tra ở server, UI chỉ phản ánh.
- Không hạ `AGE_POLICY_VERSION`, không sửa `is_adult_eligible`.
- Điều khoản không nói "bí mật tuyệt đối".
- Mật khẩu demo không vào log, không vào repo.

## 12. Test và dataset

Xem cột test. Thêm `school-entry.spec.ts` vào `testMatch`.

## 13. Acceptance criteria

- Toàn bộ test hiện có pass ở profile default.
- Tài khoản demo đăng nhập, xác nhận điều khoản, vào shell rỗng.
- Tài khoản 18+ ở profile demo không vào được app.
- Đăng ký đóng.

## 14. Phụ thuộc và blocker

WS-01. OD-05 quyết định guest. Seed trên hosted cần Auth Admin key (OD-12).

## 15. Rollback

Bỏ `APP_PROFILE`. Bảng không ảnh hưởng.

## 16. Definition of Done

Tất cả task xong; CI xanh; `check_docs.py` pass.

## 17. Ghi chú cho Grok

`conftest` ép cờ false; khi test default dùng `Settings(_env_file=None)`. Đặt validator `apply_profile` **trước** các `model_validator` hiện có (Pydantic chạy theo thứ tự khai báo): `local_live_scope` sẽ raise nếu SSM đặt tường minh `PROACTIVE_WORKER_ENABLED=true` trong khi `proactive_enabled` đã bị ép tắt. `_dependent` raise nếu flag được đặt tường minh, nên profile dùng hàm riêng không raise, vì SSM có thể đang đặt tường minh các cờ.
