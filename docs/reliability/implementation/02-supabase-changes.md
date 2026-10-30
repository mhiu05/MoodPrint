# Supabase

## Đã xác minh

| Mục | Giá trị đo được |
|---|---|
| Project | `roznanxbiyqybjpvtilq`, tên `database`, tổ chức `VDaAgent` |
| Gói tổ chức | Free |
| Region | `ap-northeast-1` |
| Trạng thái | `ACTIVE_HEALTHY` |
| PostgreSQL | 17.11 |
| `max_connections` | 60 |
| `superuser_reserved_connections` | 3 |
| Schema ứng dụng | `moodprint` |

Role `moodprint_backend` được đọc lại sau PR #25: `rolconnlimit = 20`. Không chạy lại `ALTER ROLE` vì hạn mức đã là 20.

Số kết nối của role lúc đọc lại: 9 `idle` và 1 `idle in transaction`, `application_name = Supavisor`. Tổng 10/20.

Supavisor qua Management API: host `aws-0-ap-northeast-1.pooler.supabase.com`, cổng mặc định 6543, `pool_mode = transaction`, `default_pool_size` và `max_client_conn` đều `null` (không có override tùy chỉnh). User trong chuỗi kết nối mẫu là `postgres.roznanxbiyqybjpvtilq`, không phải `moodprint_backend`.

## Đã áp dụng

Hạn mức role đã là 20 khi đọc lại catalog. Phiên này không chạy `ALTER ROLE` lần nữa.

Lần đọc trước trong PR ghi nhận 10. Việc nâng lên 20 đã có hiệu lực trên project `roznanxbiyqybjpvtilq` trước lần xác minh này. Không có câu SQL ghi thêm.

## Không cần chạy lại ALTER

Catalog đã trả `rolconnlimit = 20`. Câu lệnh sau chỉ dùng nếu một lần đọc sau này thấy giá trị khác 20:

```sql
ALTER ROLE moodprint_backend CONNECTION LIMIT 20;
```

Rollback, chỉ khi số kết nối đang dùng nhỏ hơn 10:

```sql
ALTER ROLE moodprint_backend CONNECTION LIMIT 10;
```

Hạn mức 20 vẫn nằm dưới `max_connections` 60. Không đổi role khác và không đổi `max_connections`.

## Không đề xuất nâng compute chỉ vì sự cố này

Nano trên Free và Micro trên Pro đều có khoảng 60 kết nối trực tiếp. Sự cố là hạn mức role 10, không phải cạn `max_connections`.

Pro khoảng 25 USD/tháng, gồm 10 USD compute credit cho một instance Micro, và project không bị tạm dừng sau một tuần không dùng. Nâng Pro là quyết định vận hành, không phải điều kiện để hết lỗi `too many connections for role`. Không tự nâng cấp.
