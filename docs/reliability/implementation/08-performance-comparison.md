# So sánh hiệu năng

Không có baseline độ trễ `GET /session` mới đo trên production trong đợt này. Audit cũ ghi pool 5 + 5 và role đầy 10/10. Số mới dưới đây là Postgres 17 loopback, pool 5 + 2, `SELECT 1`, 1.000 request.

| Mức | p50 | p95 | p99 | Lỗi | Thời gian cả đợt |
|---|---|---|---|---|---|
| 1 | 3,64 ms | 5,18 ms | 6,39 ms | 0 | 3,90 s |
| 10 | 11,09 ms | 29,07 ms | 50,58 ms | 0 | 1,41 s |
| 25 | 26,45 ms | 64,01 ms | 89,18 ms | 0 | 1,27 s |
| 50 | 55,44 ms | 127,33 ms | 176,21 ms | 0 | 1,29 s |

p95 dưới 2 giây và p99 dưới 5 giây ở bài toán này. Kết quả không chứng minh `GET /session` production đạt cùng ngưỡng: câu lệnh thật nặng hơn và database đang ở `ap-northeast-1` trong khi EC2 ở `ap-southeast-2`.

Chưa gộp query của session và chưa đổi session pooling sang transaction pooling. Chưa đo RTT liên vùng.
