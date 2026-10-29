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

Role `moodprint_backend` tại thời điểm đọc: `rolconnlimit = 10`.

Số kết nối của role đó: 9 `idle` và 1 `idle in transaction`, `application_name = Supavisor`. Tổng 10/10. Không phân biệt được EC2 và máy local vì Supavisor thay tên ứng dụng của client.

Supavisor qua Management API: host `aws-0-ap-northeast-1.pooler.supabase.com`, cổng mặc định 6543, `pool_mode = transaction`, `default_pool_size` và `max_client_conn` đều `null` (không có override tùy chỉnh). User trong chuỗi kết nối mẫu là `postgres.roznanxbiyqybjpvtilq`, không phải `moodprint_backend`.

## Đã áp dụng

Không có thay đổi SQL nào được ghi vào database.

`ALTER ROLE moodprint_backend CONNECTION LIMIT 20` trả HTTP 400. Phiên SQL của Management API là `supabase_read_only_user`.

## Chưa áp dụng, cần chạy trong SQL Editor bằng role có quyền

```sql
ALTER ROLE moodprint_backend CONNECTION LIMIT 20;
```

Xác minh:

```sql
SELECT rolname, rolconnlimit
FROM pg_roles
WHERE rolname = 'moodprint_backend';
```

Rollback, chỉ khi còn ít kết nối hơn hạn mức cũ:

```sql
ALTER ROLE moodprint_backend CONNECTION LIMIT 10;
```

Hạn mức 20 vẫn nằm dưới `max_connections` 60. Không đổi role khác và không đổi `max_connections`.

## Không đề xuất nâng compute chỉ vì sự cố này

Nano trên Free và Micro trên Pro đều có khoảng 60 kết nối trực tiếp. Sự cố là hạn mức role 10, không phải cạn `max_connections`.

Pro khoảng 25 USD/tháng, gồm 10 USD compute credit cho một instance Micro, và project không bị tạm dừng sau một tuần không dùng. Nâng Pro là quyết định vận hành, không phải điều kiện để hết lỗi `too many connections for role`. Không tự nâng cấp.
