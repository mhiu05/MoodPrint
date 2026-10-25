# Kiểm soát chi phí AWS staging hiện có

AWS Free Plan và spending limits phải được giữ nguyên. Dùng [AWS Pricing Calculator](https://calculator.aws/) ở chế độ estimate để xem chi phí EC2/EBS/IP theo Region và thời gian chạy; việc xem estimate không tạo tài nguyên. Không nâng plan, bật Advanced Features, hoặc mua dịch vụ mới.

| Đầu vào cần điền | Cách ước lượng cho MoodPrint |
| --- | --- |
| EC2 | Một instance x86_64 chạy 24×số ngày/tháng; chọn loại sau khi đo RAM/CPU với một worker. Không cộng replica thứ hai. |
| EBS + snapshot | Dung lượng OS, Docker images, Caddy TLS và logs; cộng thay đổi snapshot hàng tháng. Supabase DB không nằm trên EBS này. |
| Public IPv4 | Một địa chỉ gắn EC2 × số giờ; tính cả IPv4 chưa gắn nếu giữ lại. [VPC pricing](https://aws.amazon.com/vpc/pricing/). |
| Transfer | Lượt tải trang/asset, SSE, API audio tối đa 3 MB, outbound EC2 tới người dùng và provider; kiểm tra phí giữa AWS và Supabase khác Region. |
| Image registry | Pipeline mới dùng GHCR, không dùng ECR. GitHub ghi nhận Container Registry storage/bandwidth hiện miễn phí; public packages cũng miễn phí. Xem lại billing/policy hiện hành trước khi đổi visibility. Hai ECR repository cũ và lifecycle policies được giữ nguyên; ảnh còn lưu có thể tiếp tục tính AWS storage. [GitHub Packages billing](https://docs.github.com/en/billing/concepts/product-billing/github-packages). |
| CloudWatch | GB log vào, GB giữ theo retention, truy vấn/alarm; bắt đầu với log tối giản và giới hạn. [CloudWatch pricing](https://aws.amazon.com/cloudwatch/pricing/). |
| Parameter Store / KMS | SecureString Standard hiện có, tối đa 4 KB; dùng AWS managed `alias/aws/ssm`. Advanced tier hoặc customer managed KMS key có thể phát sinh phí và không cần cho cấu hình hiện tại. [Parameter tiers](https://docs.aws.amazon.com/systems-manager/latest/userguide/parameter-store-advanced-parameters.html). |
| DNS/domain | Reuse `moodprint.duckdns.org` và Elastic IP hiện có; không mua domain hoặc Route 53 mới. Caddy tự động xin TLS certificate nhưng không loại bỏ phí EC2/IP/transfer. |
| Khác | Kiểm tra Supabase backup/PITR và GitHub Actions usage theo account hiện tại. Không thêm NAT/ALB/ECS. GitHub build artifact giữ một ngày; ECR cũ vẫn được giữ và có thể tạo storage cost. |

**Tách riêng:** OpenAI và Voyage tính theo API usage và chính sách của họ; không nằm trong hóa đơn AWS. Live smoke test dự kiến tối đa 1 request OpenAI nhỏ, 1 embedding Voyage và 1 STT audio ngắn sau khi được duyệt; ghi budget riêng. Staging không được bật AI/STT chỉ vì có key.
