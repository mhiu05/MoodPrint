# Storage riêng tư cho nhật ký V2

Bucket `journal-media` chứa ảnh, âm thanh và video; PostgreSQL chỉ lưu metadata. Backend xác thực chủ tài khoản bằng opaque session trước khi cấp upload/read capability cho đúng object. Không có client Supabase session hay server key trong browser. Bảng nhật ký nằm riêng với mood hằng ngày để giữ nguyên dữ liệu và cam kết ghi chú cũ không gửi AI.

## Cấu hình đã thực hiện theo yêu cầu ngày 29/10/2026

Người dùng yêu cầu tạo bucket trên project đã cấu hình MCP: `roznanxbiyqybjpvtilq` (tên `database`, Tokyo). Công cụ MCP không có trong phiên hiện tại; đã dùng Supabase Management API và Storage API chính thức bằng credential môi trường hiện có.

- Bucket private, tối đa 52.428.800 byte (50 MiB).
- MIME: JPEG/PNG/WebP/GIF, WebM/OGG/MP4/MP3/WAV audio, MP4/WebM/QuickTime video.
- Backend giới hạn theo loại: ảnh10/audio20/video50 MiB và tối đa10tệp/khoảnh khắc.
- `storage.objects` bật RLS; không có object policy nào trên project tại thời điểm xác minh. Đây là default deny cho anon/authenticated, chỉ BFF cấp capability sau owner check.
- Credential local lưu trong `backend/.env` đã được gitignore từ trước; `.gitignore` không đổi. Không ghi credential vào tài liệu, log hoặc frontend.
- Token Management API hiện chỉ cho truy vấn SQL read-only. Lệnh thêm restrictive policy đã bị server từ chối; không có policy/DDL ứng dụng nào được thay đổi. Default deny đã được xác minh và URL public bị chặn.

Nếu sau này thêm object policy cho bucket khác, dùng restrictive fence trong [journal-media.sql](../../deploy/supabase/journal-media.sql) qua quy trình phê duyệt phù hợp, hoặc kiểm chứng chính sách không mở `journal-media`. File SQL là artifact tái tạo cấu hình, chưa được áp dụng trên hosted project. Không coi runtime-only schema RLS là end-user `auth.uid()` RLS: app user ID khác auth subject.

## Tái tạo và vận hành

Script [provision_journal_storage.py](../../scripts/provision_journal_storage.py) chỉ tạo/cấu hình bucket đích, kiểm tra privacy/MIME/giới hạn/RLS. Nó từ chối tự chuyển bucket đã public sang private hoặc bật backend khi có policy chưa được rà soát. Không áp dụng Alembic hay sửa dữ liệu nhật ký:

```powershell
backend/.venv/Scripts/python.exe scripts/provision_journal_storage.py --project-ref YOUR_PROJECT_REF --configure-local-env
```

`SUPABASE_ACCESS_TOKEN` lấy từ môi trường; script dùng existing server credential trong RAM và không in key. `--configure-local-env` chỉ đặt `JOURNAL_STORAGE_KEY` trong `.env` local. Hạ tầng deployment cần cấu hình secret riêng; tác vụ này không deploy.

Object path: `users/{app_user_id}/{entry_id}/{media_type}/{media_id}.{safe_extension}`. Upload không cho upsert. File>6MiB dùng TUS6MiB chunk qua `/storage/v1/upload/resumable/sign` và `x-signature`; URL/TUS fingerprint không persist vào localStorage. Signed read TTL60s; token upload sống2h theo provider.

Entry/media deletion gỡ quyền qua API ngay và queue remote deletion. Worker chờ2h5m từ thời điểm queue để bao phủ upload token đã cấp, xử lý50object/lượt, retry khi lỗi. Reservation pending>24h được queue dọn. Queue không có FK về tài khoản nên account purge không làm mất tác vụ xóa. Không cam kết xóa ngay token đã cấp hoặc backup của provider.

## Kiểm chứng thực tế

[Kết quả smoke](../implementation-plans/diary/evidence/hosted-storage-smoke.json) ghi4tệp tổng hợp: PNG, WAV, WebM và PNG>7MiB qua signed TUS. Đã đối chiếu metadata thật từ info-v2, byte download và public-read denial; xóa đúng4object thử nghiệm và xác nhận không còn. Không đọc hoặc xóa media người dùng.

Owner/cross-owner, stale writes, receipt replay, upload mismatch và cleanup retry được kiểm thử bằng HTTP/database local. Smoke hosted Storage không thay thế kiểm chứng hosted Auth/BFF/application migration. Migration `0019_journal` chưa được áp dụng lên hosted database; không merge/deploy.
