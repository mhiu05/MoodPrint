# Bộ công cụ Codex của MoodPrint

Các skill có thể chia sẻ nằm trong `.agents/skills/`. Codex tải từng skill khi nội dung công việc phù hợp. Danh sách nguồn, phiên bản, plugin, MCP và kết quả kiểm chứng nằm tại [INSTALLATION_MANIFEST.md](INSTALLATION_MANIFEST.md).

## Cài đặt hoặc khôi phục

Trên Windows, từ thư mục gốc dự án, chạy:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .agents/scripts/install-toolkit.ps1
```

Script kiểm tra trước khi cài, bỏ qua skill, plugin, MCP đã có, cài dependency theo lockfile và không sửa `.gitignore`. Yêu cầu Node.js 24+, Python 3.12, `uv` và Codex CLI. Hãy khởi động lại Codex sau khi cài skill/plugin.

## Phạm vi cấu hình

- Skill, dữ liệu hỗ trợ và dependency lock được lưu trong repository.
- Codex plugin cache, marketplace, MCP server và trạng thái đăng nhập nằm trong cấu hình máy tại `~/.codex/`; script thêm cấu hình nếu chưa tồn tại và không thay thế cấu hình cùng tên.
- Hook của Impeccable cần được xem xét và chấp thuận trong giao diện Codex bằng `/hooks`. Không bỏ qua bước tin cậy này.
- Promptfoo và OpenAI Developers có thể yêu cầu đăng nhập khi dùng tính năng kết nối dịch vụ. Không lưu API key trong file được theo dõi.

## Cập nhật và gỡ cài đặt

Xem mục “Update commands” và “Uninstallation” trong manifest. Lệnh cài đặt mặc định chỉ bổ sung thành phần còn thiếu; nó không xóa hay ghi đè skill có sẵn.
