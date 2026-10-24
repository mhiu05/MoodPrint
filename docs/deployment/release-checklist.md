# Checklist phát hành staging

| Gate | Bằng chứng cần có | Hiện tại |
| --- | --- | --- |
| Snapshot | Commit SHA trên `main` gồm **mọi** file cần thiết, review và chủ dự án duyệt | BLOCKED: working tree có nhiều tracked/untracked changes |
| CI | `verify.yml` push run xanh trên **đúng SHA**, Docker/Compose/Caddy và test synthetic | PARTIAL: chỉ local checks; chưa có commit/run mới |
| DB | Supabase target, backup/restore drill, 0010 + Auth helper + grants được review và áp dụng riêng | PARTIAL: probe read-only thấy 0010 và helper executable; backup/restore, SQL/privilege review vẫn thiếu; không chạy DDL |
| IAM/infra | Dự toán duyệt; ECR immutable; SSM document/agent; EC2 x86_64, SG, domain, IAM; GitHub reviewer gate | BLOCKED: chưa tạo AWS/GitHub environment |
| Secrets | SecureString/KMS, role chỉ đọc đúng parameter, production config startup pass, không có secret trong image | PARTIAL: template + local image inspection; chưa có cloud secret |
| Trải nghiệm | HTTPS, SPA refresh, API Auth cookie/CSRF, SSE, upload, email redirect, 2 account isolation, restart | PARTIAL: local HTTP proxy/unauth; domain thật chưa có |
| AI/STT | Consent, provider data processing, model hợp lệ, budget và live smoke riêng | BLOCKED: chưa duyệt/không chạy paid calls |
| Vận hành | CloudWatch/alerts, disk/CPU/memory, log redaction, image rollback, DB restore procedure | PARTIAL: thủ tục đã chuẩn bị; chưa chứng minh trên EC2 |

Khi mọi gate có bằng chứng, chủ dự án chọn SHA và bấm thủ công **Actions → Deploy approved staging snapshot → Run workflow**, nhập SHA và `DEPLOY STAGING <SHA>`. Reviewer của environment `staging` duyệt job sau khi xem CI, migration và budget. Không bật tính năng phụ thuộc migration còn thiếu. Không coi khoảng 50 users là cam kết sức tải trước khi đo tải synthetic và xác minh CPU/RAM/DB pool/provider quota.
