# Dashboard handoff — owner-provided verification

Nguồn: báo cáo ChatGPT Work được owner chuyển trong hội thoại. Agent triển khai nhận báo cáo này; chưa trực tiếp đọc PDF đính kèm.

Evidence link: https://chatgpt.com/library?file_id=libfile_e015254078848191a5c5ca05c9855685

| Hạng mục | Kết quả báo cáo | Evidence |
|---|---|---|
| Identity | `db-school-violence`, ref `xhlshihobyxrgfqrdafh`, organization `VDaAgent`; Healthy | PDF p1 |
| Tài nguyên | Pro, Micro, `ap-northeast-2` | PDF p1 |
| Global file size | **50 MB**, spend cap giữ nguyên. Dashboard nhắc tới 500 GB khi tắt cap; không tắt cap | PDF p2 |
| Bucket | `incident-evidence`: private, không bucket size/MIME limits; không đổi policy | PDF p3 |
| Site URL | Đã đổi `http://localhost:3000` → `http://127.0.0.1:5173` | PDF p4 |
| Redirect URLs | Đã thêm `http://127.0.0.1:5173/**`, `http://127.0.0.1:5178/**`, `http://localhost:5173/**` | PDF p4 |
| Auth flags | Signup/email confirmation bật, anonymous sign-in tắt | PDF p5 |
| Password | Minimum length 6 → 8; leaked password protection tắt → bật | PDF p6 |
| JWT expiry | 3600 giây, giữ nguyên | PDF p7 |
| Signing key | ECC P-256 hiện hành; HS256 cũ vẫn được liệt kê để verify; không rotate | PDF p8 |
| Data API | Chỉ `public`, `graphql_public`. Không expose app/private/SDK schemas. Auto-expose new public tables giữ nguyên | PDF p9 |
| Pooler | `aws-0-ap-northeast-2.pooler.supabase.com`, port 5432, Session mode | PDF p10 |

Đánh giá: F0-11.1 có evidence do owner cung cấp. Global maximum khi giữ spend cap vẫn **PARTIALLY_VERIFIED**, nhưng giới hạn đang có 50 MB đã rõ và được giữ nguyên. AppConfig hạ `max_object_bytes` xuống **50,000,000 bytes** để không vượt giới hạn; không mua tài nguyên, không thay đổi spend cap. Hosted migrations/role/smoke vẫn cần agent thực thi theo AD-19.
