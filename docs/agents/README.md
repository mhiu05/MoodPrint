# Trợ lý AI

Ba trợ lý hiện hành dùng chung backend runtime và OpenAI Agents SDK Python. Danh tính public nằm trong [registry.py](../../backend/app/ai/registry.py); instruction/prompt selection trong [prompts.py](../../backend/app/ai/prompts.py). Frontend chỉ trình bày danh tính và thao tác được API cho phép.

| Agent | Vai trò | Công cụ có thể được cấp |
| --- | --- | --- |
| `dieuphoi` — Điều phối | Lắng nghe, sắp xếp và phối hợp | Đề xuất ghi nhớ; consult/handoff dưới policy; search khi khả dụng |
| `nhatky` — Nhật ký | Nhìn lại trang đã lưu và cảm xúc | `search_journal_entries`, mood summary theo scope, đề xuất ghi nhớ; search khi khả dụng |
| `hoatdong` — Hoạt động | Hoạt động một người, học và chơi | Search khi khả dụng; không đọc nhật ký/mood riêng |

Skill chọn thủ công theo lượt, không mở thêm quyền dữ liệu. Registry hiện có
`hangout` v2 và `learn-new-thing` v1; hangout gợi ý hoạt động một người, không tạo
lời mời hay phòng chat. Persona V3 và instruction năm bot cũ được giữ nguyên byte.

Danh tính cũ được giữ cho tương thích và đọc lịch sử, không ghép lịch sử giữa bot:

| Bot ID | Tên | Vai trò | Tool có thể được cấp |
| --- | --- | --- | --- |
| `may` | Mây | Lắng nghe và tâm sự | `propose_memory` |
| `guong` | Gương | Khám phá bản thân | `propose_memory` |
| `nhip` | Nhịp | Cảm xúc và thói quen | `propose_memory`; `read_mood_summary` khi có scope |
| `rure` | Rủ Rê | Học hỏi và cùng chơi | Không có tool trong runtime hiện tại |
| `caunoi` | Cầu Nối | Trợ lý cũ | Không có tool trong runtime hiện tại |

Đây là danh sách tối đa; actual tools còn phụ thuộc quyền và lựa chọn context. Card discovery của V3 bị lọc trước publish; frontend bỏ card discovery trong lịch sử. Không có lời mời tới giao diện social đã gỡ.

Đọc tiếp:

- [Runtime, tool policy và SSE](runtime.md): admission, provider, timeout, cancel, restart.
- [Context, memory và privacy](context-memory.md): lưu lịch sử, scope của mood, memory proposal, embedding.
- [Evaluation](evaluation.md): các lớp test, offline contract checker và live gate.

Điểm vào API thật là [chat_routes.py](../../backend/app/ai/chat_routes.py), được include bởi [main.py](../../backend/app/main.py). Khi sửa agent, đọc cả backend authorization test; prompt không thay thế quyền truy cập.
