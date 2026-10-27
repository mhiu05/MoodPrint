# Tài liệu kỹ thuật MoodPrint

Bộ tài liệu này mô tả mã nguồn tại ngày **28/10/2026**. Đây là bản đồ triển khai cho người phát triển và vận hành; trạng thái của dịch vụ hosted phải được kiểm tra riêng. Phiên bản cài đặt lấy từ `backend/uv.lock` và `frontend/package-lock.json`.

Đọc [kiến trúc tổng thể](../ARCHITECTURE.md) trước, sau đó [chạy local và kiểm thử](development.md). Các lệnh trong tài liệu dùng PowerShell, trừ khi có ghi khác. Đường dẫn lệnh tính từ repository root hoặc thư mục được chỉ rõ.

## Các nhóm tài liệu

| Nhóm | Nội dung | Điểm vào mã nguồn |
| --- | --- | --- |
| [Agents](agents/README.md) | Năm trợ lý, tool policy, run/SSE, context, memory, evaluation | `backend/app/ai/` |
| [Frontend](frontend/README.md) | Route, state, API client, CSS, accessibility, browser test | `frontend/src/` |
| [Backend](backend/README.md) | Modular monolith, API, transaction, jobs, cấu hình | `backend/app/` |
| [Supabase](supabase/README.md) | PostgreSQL, Auth, schema riêng, runtime role, migration | `backend/alembic/`, `deploy/supabase/` |
| [Matching](matching/README.md) | Profile publication, retrieval, scorer, ranking, kết nối | `backend/app/modules/matching/`, `social/` |

## Tìm theo công việc

| Công việc | Đọc |
| --- | --- |
| Onboard, chạy app, kiểm tra lỗi môi trường | [Development](development.md) |
| Thêm/sửa endpoint và sinh TypeScript | [API và transaction](backend/api.md), [frontend transport](frontend/data-flow.md) |
| Sửa prompt/tool hoặc nguồn đưa vào model | [Agent runtime](agents/runtime.md), [context và memory](agents/context-memory.md) |
| Sửa matching và đánh giá chất lượng | [Thuật toán](matching/algorithm.md), [evaluation](matching/evaluation.md) |
| Thay đổi schema hoặc chuẩn bị hosted migration | [Schema](supabase/schema.md), [migration runbook](supabase/migrations.md) |
| Điều tra session hết hạn hoặc quyền bị rút | [Auth](supabase/auth.md), [data lifecycle](backend/data-lifecycle.md) |
| Xem kết quả kiểm thử của lần cập nhật này | [Verification](verification.md) |

## Quy ước và nguồn sự thật

- Pydantic DTO là nguồn hợp đồng; `backend/openapi.json` và `frontend/src/api/generated/schema.d.ts` là đầu ra sinh tự động.
- ORM cùng migration là nguồn schema. Tài liệu không cấp quyền chạy DDL hosted.
- `Settings` và `EmbeddingSettings` là nguồn giá trị mặc định. File `.env.example` là ví dụ triển khai, có thể bật flag khác mặc định.
- Transcript hiển thị, context model, memory được duyệt và public matching profile là bốn loại dữ liệu khác nhau.
- Test tổng hợp, test có HTTP fixture và test live có phạm vi bằng chứng khác nhau; xem [ma trận kiểm thử](frontend/testing.md).
- Khi thay đổi endpoint, flag, migration, quyền hoặc retention, cập nhật trang sở hữu hành vi đó và chạy lại kiểm tra liên quan.

Hướng dẫn đóng gói hiện có: [deploy](../deploy/README.md), [AWS staging](../deploy/aws/README.md). Không suy ra đã deploy hoặc đã đạt health check từ việc có file cấu hình.
