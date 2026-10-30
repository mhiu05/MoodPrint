# Tóm tắt thực thi

Nhánh `fix/reliability-performance-ux` xuất phát từ `origin/main` tại `57b3f7fbf91967f329a80fd344421f24ff6c5e52`. Worktree riêng `E:\MoodPrint-reliability` không đụng thay đổi `.gitignore` đang có ở workspace chính.

Đã làm trong code:

- Pool mặc định của một process API là 5 + 2, có cảnh báo nếu hai process chồng lên nhau không còn headroom trong hạn mức role 20.
- Lỗi kết nối tạm thời trả HTTP 503 `DATABASE_BUSY` hoặc `DATABASE_UNAVAILABLE`. Lỗi lập trình vẫn là HTTP 500, `retryable: false`.
- Mỗi request `/api/` ghi một dòng log không chứa SQL, DSN hay nội dung người dùng.
- Phiên đã xác thực không bị gỡ khỏi màn hình khi kiểm tra lại gặp lỗi tạm thời. Ân hạn 30 giây không bị reset bởi focus. Hết ân hạn thì ẩn nội dung riêng.
- 401, 403 và hết hạn khách vẫn kết thúc quyền truy cập ngay.
- Chỉ `GET /session` được thử lại, tối đa 3 lần trong 20 giây.

Chưa làm trên production:

- `ALTER ROLE moodprint_backend CONNECTION LIMIT 20` chưa chạy. API quản trị đang đăng nhập bằng `supabase_read_only_user`.
- Biến môi trường runtime trên EC2 chưa đổi.
- Chưa merge và chưa deploy.

Ảnh chụp trạng thái kết nối nằm trong [screenshots](screenshots/).
