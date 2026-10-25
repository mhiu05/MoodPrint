# Cài poller staging trên EC2 hiện có

Tài liệu này dùng lại hạ tầng MoodPrint đã tồn tại. Không tạo EC2, Elastic IP, ECR repository, NAT, load balancer hoặc dịch vụ DNS mới. Giữ AWS Free Plan và spending limits. Ứng dụng chưa được triển khai; cần kiểm tra thực tế sau lần phát hành đầu.

## Trước khi cài

1. Xác minh đúng AWS account/Region, instance `moodprint-staging` đang chạy, status checks 3/3 và SSM Managed node Online. Giữ Security Group mở đúng HTTP/HTTPS; không mở SSH hoặc API port.
2. Giữ IAM role `MoodPrint-Staging-EC2-Role` với `AmazonSSMManagedInstanceCore`. Review `deploy/aws/instance-policy.json` và chỉ cấp thêm `ssm:GetParameter` cho ARN chính xác của `/moodprint/staging/runtime`. Nếu SecureString dùng AWS managed key `alias/aws/ssm`, không thêm placeholder customer-managed KMS grant.
3. Xác minh parameter `/moodprint/staging/runtime` vẫn là Standard SecureString. Không in plaintext. Standard Parameter Store giới hạn 4 KB.
4. Kiểm tra DNS A record của `moodprint.duckdns.org` trỏ tới Elastic IP hiện có. Không đổi IP hoặc mua domain mới.
5. GHCR packages bắt đầu private. Sau khi image đầu tiên qua secret checks và được review, có thể chọn public để EC2 pull ẩn danh; chuyển package sang public là lựa chọn không thể hoàn tác. Nếu giữ private, dùng token chỉ có `read:packages` trong SecureString riêng và cấp quyền đọc đúng token parameter cho EC2 role.

## Cài đặt

Tải repository tại commit `main` đã được review, rồi chạy qua Session Manager:

```bash
sudo bash deploy/aws/install-release-poller.sh
```

Installer cài poller, `deploy.sh`, Compose/Caddy files, systemd service/timer và GitHub CLI tối thiểu 2.102.0 từ nguồn chính thức của GitHub nếu phiên bản có sẵn quá cũ. Installer không tạo AWS resource. Giữ thư mục và scripts do root sở hữu; user ứng dụng không được sửa chúng.

Review `/opt/moodprint/deployment.conf` với owner root và mode `0600`. File này chứa cấu hình không bí mật như Region, `GITHUB_REPOSITORY=mhiu05/MoodPrint`, tên GHCR images, `APP_DOMAIN=moodprint.duckdns.org`, và tên parameter runtime. Không đưa secret values hoặc GHCR token vào file. Nếu dùng package private, đặt tên token parameter và GHCR username; cấp IAM chỉ cho đúng parameter token đó.

Kiểm tra timer và log mà không đọc env file:

```bash
sudo systemctl status moodprint-release-poll.timer
sudo systemctl start moodprint-release-poll.service
sudo journalctl -u moodprint-release-poll.service --since today --no-pager
```

SSM document `MoodPrint-Staging-Deploy` chỉ dành cho recovery do operator thực hiện; routine deployment không gọi SSM Run Command. Giữ nguyên hai ECR repository cũ cùng immutable tag settings và lifecycle policies. Pipeline mới sử dụng GHCR.

## Phát hành và kiểm tra

Sau khi code được merge vào `main`, CI phải thành công trên đúng SHA. Release workflow tự build, kiểm image, xuất digest và attestations. EC2 timer kiểm tra mỗi năm phút, xác minh release của SHA `main` mới nhất, rồi triển khai digest pair. CI thất bại thì không có release mới để cài.

Xác nhận hai container healthy và `https://moodprint.duckdns.org/api/v1/health/ready` thành công. Kiểm tra Caddy certificate, redirect HTTP sang HTTPS, refresh các SPA routes và Supabase Auth Site URL/redirect allow-list riêng. Image deployment không chạy migration database. Nếu health check thất bại, `deploy.sh` thử khôi phục image pair trước; chỉ báo rollback thành công sau khi xác nhận readiness.

Auth, mood, matching, messaging, privacy, SSE và mobile cần synthetic smoke tests riêng. AI, memory, Voyage và STT chỉ được bật sau khi review secrets, consent, ngân sách và provider smoke tests. Readiness thành công không thay thế các bài kiểm tra tính năng.
