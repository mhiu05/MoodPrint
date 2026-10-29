# Ngân sách kết nối

Một process API dùng `pool_size` 5 và `max_overflow` 2, tức tối đa 7 kết nối. Hai process trong lúc deploy dùng 14. Với hạn mức role 20 còn 6 chỗ cho Supavisor, truy vấn vận hành và một client khác.

| Cấu hình | Hai process | So với role 10 | So với role 20 |
|---|---|---|---|
| 8 + 4 (default cũ trong code) | 24 | Vượt | Vượt |
| 5 + 5 (ví dụ runtime cũ) | 20 | Vượt | Hết sạch, không headroom |
| 5 + 2 (default mới) | 14 | Vẫn vượt nếu role còn 10 | Còn 6 |

Code mặc định và file mẫu `backend/.env.example`, `deploy/runtime.env.example` đã chuyển sang 5 + 2. Process khởi động sẽ log `database_pool_exceeds_headroom` nếu 5 + 2 không còn đủ chỗ khi tính hai process.

Runtime trên EC2 `i-0664d6ea5930452db`, đọc ngày 2026-10-30, vẫn là `DATABASE_POOL_SIZE=5` và `DATABASE_POOL_OVERFLOW=5`. SHA đang chạy là `57b3f7fbf91967f329a80fd344421f24ff6c5e52`. Chi tiết ở [11-aws-runtime.md](11-aws-runtime.md). File mẫu trong Git đã là 5+2 nhưng chưa được ghi vào runtime đang chạy.

Không tăng số worker Uvicorn.

Đo local chỉ dùng Postgres loopback, pool 5 + 2, câu `SELECT 1`, 1.000 request mỗi mức:

| Người dùng ảo | p50 | p95 | p99 | Lỗi |
|---|---|---|---|---|
| 1 | 3,64 ms | 5,18 ms | 6,39 ms | 0 |
| 10 | 11,09 ms | 29,07 ms | 50,58 ms | 0 |
| 25 | 26,45 ms | 64,01 ms | 89,18 ms | 0 |
| 50 | 55,44 ms | 127,33 ms | 176,21 ms | 0 |

Đây không phải độ trễ của `GET /session` trên Supabase và không tính RTT `ap-southeast-2` tới `ap-northeast-1`. Không chạy bão kết nối lên production.
