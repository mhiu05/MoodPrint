# Preflight cho AWS staging hiện có

Hạ tầng MoodPrint đã tồn tại ở `ap-southeast-2`. Giữ AWS Free Plan và spending limits; không bật Advanced Features, nâng account, mua dịch vụ mới, hoặc tạo lại tài nguyên đã có. Application chưa được xác nhận live.

| Hạng mục | Trạng thái/kiểm tra trước release |
| --- | --- |
| Billing và plan | Xác minh Free Plan, spending limits, và chi phí hiện tại trong Billing. Không đổi plan hoặc bỏ giới hạn chi tiêu. |
| EC2 và mạng | Reuse instance `moodprint-staging`, Elastic IP hiện có, và security group. Xác minh instance Running, status checks 3/3, SSM Online; inbound chỉ HTTP/HTTPS cần thiết, không mở SSH hoặc API port. |
| Session Manager | Reuse instance role `MoodPrint-Staging-EC2-Role` với `AmazonSSMManagedInstanceCore`. Session Manager là đường quản trị; routine deploy dùng systemd poller, không SSH hay SSM Run Command. |
| Runtime parameter | SecureString Standard `/moodprint/staging/runtime` đã có. Xác minh tồn tại mà không in plaintext. Standard giới hạn 4 KB. |
| Runtime IAM | Review `deploy/aws/instance-policy.json` và chỉ thêm `ssm:GetParameter` cho ARN parameter runtime exact. Nếu dùng AWS managed `alias/aws/ssm`, không thêm placeholder customer-managed KMS grant. |
| Registry | Hai ECR repository đã có; giữ nguyên repositories, cài đặt immutable tag và lifecycle policies. Workflow mới sử dụng GHCR; không tạo ECR/OIDC resource mới. |
| GHCR access | Packages bắt đầu private. Chọn giữ private với token chỉ `read:packages` trong SecureString riêng, hoặc đổi public sau khi đã xem image và kiểm secret checks. Public visibility không thể chuyển lại private. |
| DNS và TLS | Reuse `moodprint.duckdns.org` và Elastic IP. Verify DNS A record trước khi kiểm tra Caddy certificate/HTTPS; không đổi IP hoặc mua Route 53. |
| SSM recovery | SSM document `MoodPrint-Staging-Deploy` đã tồn tại. Automatic poller không cần document này; chỉ review/update khi cần emergency recovery. |
| Monitoring | `cloudwatch-agent.json` là template tùy chọn. Poller policy không grant CloudWatch permissions; không bật agent hoặc tạo log groups/alarms nếu chưa review quyền và chi phí. |

## Release sequence

1. Từ commit đã review trên `main`, cài `deploy/aws/install-release-poller.sh` qua Session Manager; không tạo AWS resources.
2. Verify `/opt/moodprint/deployment.conf` là root-owned, mode `0600`, với domain và repository đã biết. Không đưa giá trị bí mật vào file này.
3. Xác minh EC2 có thể pull image GHCR. Nếu packages private, cấp role quyền đọc đúng token parameter; nếu chọn public, chỉ đổi visibility sau khi review image và secret checks.
4. Verify systemd timer runs, then wait for a successful `Verify local application` push run and current-main release.
5. Confirm both containers healthy and `https://moodprint.duckdns.org/api/v1/health/ready` responds. Check HTTPS certificate, SPA refresh, auth, and application workflows separately.
6. Migrations and Supabase DDL are not part of image deployment. Keep the existing schema and data; do not run destructive migrations.

ECR storage hiện có, EC2/EBS và public IPv4 có thể tính phí. Xem estimate của account mà không đổi plan hoặc spending controls. See [cost guidance](aws-costs.md), [staging install](staging-setup.md), and [release checklist](release-checklist.md).
