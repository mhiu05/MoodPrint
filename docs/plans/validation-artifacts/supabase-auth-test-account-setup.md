# Hai synthetic Auth accounts — cấu hình đã hoàn tất

24/10/2026. User chọn tự tạo đúng hai accounts qua Dashboard/Auto confirm; không dùng Auth Admin key. Credentials được nhập bằng terminal ẩn qua helper dưới đây, không lấy password từ chat. Helper dùng publishable key đã có để kiểm trusted login/getUser và revoke riêng session kiểm tra, sau đó lưu email/user ID/password-base64 vào backend/.env. Base64 chỉ bảo toàn parsing, không phải encryption. Không lưu provider token, không gửi email, không sửa Auth bằng SQL.

```powershell
uv run --directory E:\MoodPrint\backend python E:\MoodPrint\scripts\provision_auth_test_accounts.py --configure-existing
```

Helper đã thành công; không cần nhập lại nếu credentials không đổi. User-created fixtures đã qua real UI/API login, provider revoke và logout/replay trong hosted E2E. Public signup/email delivery/recovery chưa được kiểm chứng. Không ghi password/email thực vào tài liệu hoặc test artifacts.

Script có tùy chọn Auth Admin tạo fixtures, chỉ được dùng khi user chọn riêng; phiên này không dùng và không cần Admin key. Tests local3 PASS bao gồm mocked Admin scope/partial failure và manual-login/temporary-session cleanup/special-symbol round-trip. Xem [account report](supabase-auth-test-accounts.json), [hosted checks](supabase-e2e-checkpoints.json).
