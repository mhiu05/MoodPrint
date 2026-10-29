# Rủi ro còn lại

- Role production vẫn là 10 cho đến khi SQL Editor chạy `ALTER ROLE`. Lúc đọc catalog, role đã dùng 10/10, trong đó 1 kết nối `idle in transaction`.
- Chưa biết 10 kết nối Supavisor thuộc EC2, máy local, hay cả hai. Máy dev không nên dùng `DATABASE_URL` của role production.
- Runtime EC2 chưa đổi pool. Default trong Git chỉ có tác dụng khi biến môi trường không ghi đè.
- Chưa đo `GET /session` với 50 người dùng trên staging. Số `SELECT 1` local không thay cho độ trễ liên vùng.
- AWS CLI không có credential trong phiên này. Chưa đọc log EC2, health container hay digest image đang chạy.
- Supabase MCP không xuất hiện trong phiên. Management API chỉ đọc được SQL.
- Chưa rà trình duyệt toàn bộ đăng nhập, nhật ký, tìm bạn, voice và hồ sơ. Nhật ký có dòng trạng thái khi bị khóa lưu, chưa có bài browser test riêng cho nút lưu.
- Một kết nối `idle in transaction` chưa được giải phóng. Không terminate session production.
