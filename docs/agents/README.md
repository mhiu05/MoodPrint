# Trợ lý AI

Năm trợ lý dùng chung backend runtime và OpenAI Agents SDK Python. Danh tính public nằm trong [registry.py](../../backend/app/ai/registry.py); instruction/prompt selection trong [prompts.py](../../backend/app/ai/prompts.py). Frontend chỉ trình bày danh tính và thao tác được API cho phép.

| Bot ID | Tên | Vai trò | Tool có thể được cấp |
| --- | --- | --- | --- |
| `may` | Mây | Lắng nghe và tâm sự | `propose_memory` |
| `guong` | Gương | Khám phá bản thân | `propose_memory`, `propose_private_item` |
| `nhip` | Nhịp | Cảm xúc và thói quen | `propose_memory`; `read_mood_summary` khi có scope |
| `rure` | Rủ Rê | Học hỏi và cùng chơi | Không có tool trong runtime hiện tại |
| `caunoi` | Cầu Nối | Hướng dẫn tìm bạn | Không có tool trong runtime hiện tại |

Đây là danh sách tối đa; actual tools còn phụ thuộc quyền và lựa chọn context. Cầu Nối có thể trả navigation card nhưng không tự tìm dữ liệu riêng của peer, publish profile hoặc gửi kết nối.

Đọc tiếp:

- [Runtime, tool policy và SSE](runtime.md): admission, provider, timeout, cancel, restart.
- [Context, memory và privacy](context-memory.md): lưu lịch sử, scope của mood, memory proposal, embedding.
- [Evaluation](evaluation.md): các lớp test, offline contract checker và live gate.

Điểm vào API thật là [chat_routes.py](../../backend/app/ai/chat_routes.py), được include bởi [main.py](../../backend/app/main.py). Khi sửa agent, đọc cả backend authorization test; prompt không thay thế quyền truy cập.
