# Dự toán chi phí trước khi tạo tài nguyên

Mở [AWS Pricing Calculator](https://calculator.aws/) → **Create estimate** (không tạo tài nguyên). Chọn cùng Region cho mọi dịch vụ; lưu đường dẫn dự toán và ngày giá. Không dùng một con số cố định vì Region, instance, mức dùng và free tier thay đổi. Công cụ EC2 có mục EBS, data transfer và public IP. [Hướng dẫn EC2 estimate](https://docs.aws.amazon.com/pricing-calculator/latest/userguide/ec2-estimates.html).

| Đầu vào cần điền | Cách ước lượng cho MoodPrint |
| --- | --- |
| EC2 | Một instance x86_64 chạy 24×số ngày/tháng; chọn loại sau khi đo RAM/CPU với một worker. Không cộng replica thứ hai. |
| EBS + snapshot | Dung lượng OS, Docker images, Caddy TLS và logs; cộng thay đổi snapshot hàng tháng. Supabase DB không nằm trên EBS này. |
| Public IPv4 | Một địa chỉ gắn EC2 × số giờ; tính cả IPv4 chưa gắn nếu giữ lại. [VPC pricing](https://aws.amazon.com/vpc/pricing/). |
| Transfer | Lượt tải trang/asset, SSE, API audio tối đa 3 MB, outbound EC2 tới người dùng và provider; kiểm tra phí giữa AWS và Supabase khác Region. |
| ECR | Hai repo, dung lượng nén của mỗi image × số phiên bản còn giữ, push/pull và transfer liên quan. [ECR pricing](https://aws.amazon.com/ecr/pricing/). |
| CloudWatch | GB log vào, GB giữ theo retention, truy vấn/alarm; bắt đầu với log tối giản và giới hạn. [CloudWatch pricing](https://aws.amazon.com/cloudwatch/pricing/). |
| Parameter Store / KMS | Một SecureString; standard tối đa 4 KB, advanced nếu vượt hoặc cần tính năng thêm; customer managed KMS key/request nếu chọn. [Parameter tiers](https://docs.aws.amazon.com/systems-manager/latest/userguide/parameter-store-advanced-parameters.html). |
| DNS/domain | Tên miền đã sở hữu hay mua mới, hosted zone/query nếu dùng Route 53. Caddy certificate tự động không đồng nghĩa domain miễn phí. |
| Khác | Kiểm tra gói Supabase, backup/PITR, phí GitHub Actions/ECR scanning theo cấu hình; không thêm NAT/ALB/ECS khi chưa cần. |

**Tách riêng:** OpenAI và Voyage tính theo API usage và chính sách của họ; không nằm trong hóa đơn AWS. Live smoke test dự kiến tối đa 1 request OpenAI nhỏ, 1 embedding Voyage và 1 STT audio ngắn sau khi được duyệt; ghi budget riêng. Staging không được bật AI/STT chỉ vì có key.
