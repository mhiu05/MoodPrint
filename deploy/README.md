# Trạng thái triển khai

Repository chưa cung cấp cấu hình triển khai có thể làm theo: `Dockerfile`, `compose.local.yml`, `compose.staging.yml`, `Caddyfile` và `runtime.env.example` đều chưa có nội dung. Chưa có cơ sở coi chúng là một cách deploy được hỗ trợ.

Để chạy trên máy, dùng [hướng dẫn cài đặt](../README.md#cài-đặt-và-chạy-local). [Kiến trúc](../README.md#kiến-trúc-hệ-thống) và [dữ liệu, phân quyền](../README.md#cách-hệ-thống-hoạt-động) mô tả các dependency cần hiểu trước khi chuẩn bị triển khai.

Hiện chưa có quy trình được kiểm chứng riêng cho staging/production, TLS/reverse proxy, secret provisioning, migrations, backup/restore hay vận hành worker. Bộ tài liệu này không thực hiện deployment hoặc thay đổi cloud infrastructure.
