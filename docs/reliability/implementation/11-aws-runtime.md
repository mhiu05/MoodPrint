# AWS runtime, đọc lúc 2026-10-30

Profile `moodprint` đã có credential. `aws sts get-caller-identity --profile moodprint --region ap-southeast-2` trả account `231266553536`, role `AccountFullAccessRole`. Không chạy `aws login` mới vì phiên hiện tại còn hiệu lực.

Instance duy nhất ở `ap-southeast-2`: `i-0664d6ea5930452db`, tên `moodprint-staging`, `t3.small`, AZ `ap-southeast-2b`, trạng thái `running`. SSM agent online.

Container, đọc qua SSM, không in secret:

| Container | Image digest | Trạng thái |
|---|---|---|
| `moodprint-staging-api-1` | `ghcr.io/mhiu05/moodprint-api@sha256:52d74edef5a3ecbcc43f03694973bf0cbffaf7784b9bb3bcd9ad5406c09e83d7` | Up 8 giờ, healthy |
| `moodprint-staging-web-1` | `ghcr.io/mhiu05/moodprint-web@sha256:f6b1916820d9dd1c6e78a6aa2a5cd0eeca27a6b9bf69546646c76c6bb6d17949` | Up 8 giờ, healthy |

`RELEASE_SHA=57b3f7fbf91967f329a80fd344421f24ff6c5e52`. Đây là `origin/main`, không phải PR #25.

Runtime thật:

| Biến | Giá trị đang chạy | Giá trị đề xuất |
|---|---|---|
| `APP_ENV` | `production` | giữ nguyên |
| `DATABASE_POOL_SIZE` | `5` | `5` |
| `DATABASE_POOL_OVERFLOW` | `5` | `2` |
| `DATABASE_POOL_TIMEOUT` | `10` | `10` |

Hai process 5+5 dùng hết 20 kết nối của role, không còn headroom. Chưa sửa file runtime trên EC2.

`https://moodprint.duckdns.org/api/v1/health/ready` trả 200 `{"status":"ready"}`. Cổng 8001 không mở trên host; API chỉ trong mạng Docker.

Log API 12 giờ gần nhất: 106 dòng `error_type=OperationalError`, 0 dòng chứa cụm `too many connections`. Log không có SQLSTATE của bản PR nên không kết luận 106 lỗi đó là hết chỗ kết nối. CPU lúc đọc khoảng 0,8% API và 4% web. RAM API khoảng 149 MiB / 768 MiB.

Không deploy và không đổi SSM parameter.
