# Deploy và rollback

Chưa deploy. Merge vào `main` có thể kích hoạt workflow hiện có. Cần approval riêng trước khi merge.

## Trước khi rollout

1. Chạy SQL nâng `moodprint_backend` lên 20 và đọc lại `rolconnlimit`.
2. Trong SSM runtime, đặt `DATABASE_POOL_SIZE=5` và `DATABASE_POOL_OVERFLOW=2`. Giữ một worker.
3. Ghi image API/web đang chạy để rollback. Không ghi secret vào ticket.
4. Xác nhận CI của đúng SHA pull request.

`RELEASE_SHA` được Compose đưa vào container API. Không đọc Docker socket từ ứng dụng.

## Rollback ứng dụng

Dùng cặp image API/web đã ghi trước rollout, qua `deploy/aws/deploy.sh` và file `staging.previous.env` hiện có. Không hạ schema. Revision ứng dụng vẫn phải nằm trong `READY_REVISIONS`.

## Rollback cấu hình

Nếu process mới không khởi động vì pool, trả `DATABASE_POOL_OVERFLOW` về giá trị cũ chỉ khi tổng hai process không vượt role limit đang có. Không trả về 5 + 5 khi role vẫn là 10 và còn client local.

Không tự chạy:

```sql
ALTER ROLE moodprint_backend CONNECTION LIMIT 10;
```

## Dừng rollout nếu

Nội dung riêng hiện lại sau logout, hạn khách bị kéo dài, request ghi khi chưa xác nhận phiên, log có secret, hoặc 5xx phiên tăng sau khi role đã còn chỗ trống.
