# Auth, session và phân quyền

## Đăng nhập

1. Browser gửi email/password đến backend `/auth/login` với origin hợp lệ. Backend áp dụng IP/email attempt limits.
2. [SupabaseAuth](../../backend/app/modules/auth/provider.py) gọi provider qua HTTPS; Supabase chịu trách nhiệm password verification và recovery.
3. Backend lấy provider user/session identity, tạo hoặc tìm `User` theo `auth_subject`; tài khoản mới có eligibility unknown và consent tắt.
4. Backend tạo opaque random session/CSRF, lưu hash và `provider_session_id` trong `auth_sessions`.
5. Cookie `moodprint_session` HttpOnly, `moodprint_csrf` đọc được, SameSite strict; secure khi production hoặc flag bật. UI nhận `SessionView` và CSRF trong state.

Không giữ provider access/refresh token trong browser storage hoặc bảng app session. Server kiểm tra sliding idle expiry mặc định 12 giờ. `SESSION_MAX_DAYS` đặt browser cookie max-age mặc định 7 ngày; code hiện tại không có server-side absolute expiry dựa trên ngày tạo session. Các thời hạn này khác provider access token. Kiểm tra provider session hiện hành là điều kiện quan trọng để logout/revocation có tác dụng.

## Request sau đăng nhập

[require_actor/verify_session](../../backend/app/core/security.py) kiểm tra hash cookie, revoked/expiry, auth version, user status/suspension và private helper `moodprint.is_provider_session_active(uuid,uuid)`. Helper nhận app session ID/user ID, tìm provider session đã liên kết; không đưa token cho frontend.

Authenticated writes cần CSRF header khớp hash; origin nếu có phải khớp `FRONTEND_ORIGIN`. Public auth writes có check origin riêng. Transaction rechecks actor để quyền không chỉ được kiểm tra trước lúc đợi lock. Sliding idle expiry và last_seen được cập nhật có throttle khoảng 15 phút.

Nguồn helper được review ở [provider_session.sql](../../backend/app/infrastructure/database/provider_session.sql). Quyền EXECUTE, schema/search_path và quyền đọc `auth.sessions` phải đúng reviewed SQL; không cấp toàn quyền schema Auth cho runtime để sửa nhanh lỗi 401.

## Recovery, reauthentication và eligibility

Trong Supabase Authentication → URL Configuration, cho phép chính xác
`https://moodprint.duckdns.org/auth/callback` trong Redirect URLs. Provider adapter
gửi email redirect tới đường dẫn này; frontend đọc fragment một lần và xóa token
khỏi URL trước khi render. Giữ các callback khác khi cập nhật allowlist. Xem
[Supabase redirect URLs](https://supabase.com/docs/guides/auth/redirect-urls).

Khi bật CAPTCHA trong Supabase Auth, bật `AUTH_CAPTCHA_ENABLED=true` trong runtime
và đặt `GUEST_CAPTCHA_SITE_KEY` thành public site key của cùng widget Turnstile.
Site key này dùng chung cho auth và guest; không phải secret key. Secret CAPTCHA
chỉ cấu hình tại provider. Production từ chối khởi động nếu bật cờ auth mà thiếu
site key. `/public/experience` trả `authCaptchaRequired` và `captchaSiteKey` ngay
cả khi guest entry tắt, để đăng nhập thông thường vẫn dùng được widget.

Login, signup, password-recovery, confirmation resend và password step-up nhận
`captchaToken` tùy chọn trong contract; khi cờ bật phải có token mới cho mỗi lần
gửi. Backend chuyển token thành `gotrue_meta_security.captcha_token`, không lưu
token vào app session hay receipt và không ghi token/body provider vào log.
Thiếu token trả `422 CAPTCHA_REQUIRED`; provider từ chối token hết hạn/không hợp
lệ trả `422 CAPTCHA_FAILED`, không giả thành sai mật khẩu hay gửi mail thành công.
Rate limits, origin, CSRF và live provider-session validation vẫn giữ nguyên.
Đổi cờ runtime cần recreate API; đổi CAPTCHA tại provider phải phối hợp với bản
frontend/backend hỗ trợ token để không khóa đăng nhập.

Theo [Supabase CAPTCHA guide](https://supabase.com/docs/guides/auth/auth-captcha)
và [GoTrue route registration](https://github.com/supabase/auth/blob/master/internal/api/api.go),
`/resend` cũng có CAPTCHA middleware. Password reset bằng recovery bearer gọi
`PUT /user`, không tạo password grant nên không yêu cầu widget lần nữa.
[GoTrue middleware](https://github.com/supabase/auth/blob/master/internal/api/middleware.go)
miễn CAPTCHA cho refresh-token/PKCE grants; không thêm CAPTCHA vào việc đọc hoặc
refresh app session đang hợp lệ. Các nguồn này được kiểm tra ngày 2026-11-02.

Signup/confirmation/password-recovery trả thông báo theo route, tránh suy ra tồn tại email từ nội dung UI. Callback password-reset được frontend xử lý và bỏ token khỏi URL. Step-up `/auth/reauthenticate` khác đăng nhập lại toàn bộ; export/deletion/staff có yêu cầu thời gian reauth tương ứng.

Toàn bộ MoodPrint yêu cầu từ đủ 18 tuổi, gồm guest và session đã phát hành trước đây. `verify_actor` kiểm tra `AgeDeclaration` do backend lưu: band adult, policy được hỗ trợ, năm sinh hợp lệ, timestamp hợp lệ và xác nhận adult trong năm tròn 18. Band/JWT metadata riêng lẻ không cấp quyền. Khai báo mới dùng `self-declared-age-v2-18plus`; khai báo v1 của adult hợp lệ vẫn dùng được. Session, logout, khai báo tuổi, reauthentication, rút MATCH và xuất/xóa dữ liệu có ngoại lệ bảo mật cụ thể. Đây là tự khai báo, không phải xác minh giấy tờ. [Chi tiết policy và release](../release/moodprint-18plus-0020-rollout.md).

## Consent và resource ownership

`AI`, `MEM`, `MATCH`, `VOICE` là purpose riêng; MEM/VOICE cần AI, MATCH cần adult và không đang social restriction. `features` trong session phản ánh availability, không phải consent đã bật. Tùy chọn history/semantic memory cũng tách riêng.

ID resource do client gửi không đủ để truy cập: query/transaction phải ràng buộc owner hoặc pair membership và live policy. Candidate ref không phải user ID; reveal grant không phải public identity. Staff role lấy từ `staff_roles`, không từ user-editable metadata.

## Local/hosted mismatch

Một DB local có bảng app nhưng đăng nhập vào Auth hosted sẽ không thấy provider session trong local `auth.sessions`; request tiếp theo bị từ chối là đúng boundary. Không sửa helper để luôn trả true. Chọn một môi trường Auth/DB cùng hệ thống hoặc dùng synthetic test harness riêng. `DATABASE_URL` và `DATABASE_MIGRATION_URL` không bao giờ được dùng thay `TEST_DATABASE_URL` trong destructive tests.

Coverage: `test_auth_flows.py`, `test_eligibility.py`, `test_safety.py`, `test_privacy_lifecycle.py`, `test_moderation_admin.py` và frontend auth specs. Các ca tổng hợp không chứng minh email delivery/provider revocation trên hosted project.
