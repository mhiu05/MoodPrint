# SafeVoice agent runtime

`safevoice_agent` dùng official OpenAI Agents SDK `openai-agents[sqlalchemy]==0.24.*`,
chạy trong cùng tiến trình FastAPI. Bắt đầu từ [kiến trúc hệ thống](../README.md#kiến-trúc-hệ-thống)
và [hướng dẫn chạy](../README.md#cài-đặt-và-chạy-local); gói này không có HTTP server riêng.

## Runtime và công cụ

[CompanionRuntime](src/safevoice_agent/runtime.py) nhận `AsyncOpenAI` từ backend,
dùng `Runner.run_streamed` và prompt [companion_v5](src/safevoice_agent/prompts/companion_v5.md).
[Factory](src/safevoice_agent/tools/factory.py) đăng ký các nhóm knowledge, incident,
evidence, plan, memory và support. `get_server_time` chỉ nằm trong registry chẩn đoán
dùng khi runtime không được truyền registry; backend thật truyền đầy đủ registry.

Mô hình mặc định lấy từ `safevoice_shared.config.OPENAI_MODEL` (`gpt-6-luna`).
Request dùng `store=False`, tracing tắt và không đưa dữ liệu nhạy cảm vào trace.
Chỉ hợp đồng sự kiện public có phiên bản đi qua SSE; tham số/kết quả tool thô và
reasoning event của SDK không được phát trực tiếp. Dữ liệu ứng dụng và SDK session
vẫn được SafeVoice lưu trong DB riêng.

Backend sở hữu xác thực, quyền conversation, persistence và producer tiếp tục chạy
khi client ngắt SSE. Trước `resume_after_approval`, backend kiểm tra owner, hạn dùng
và quyết định một lần. Checkpoint chỉ lấy từ server, không nhận state từ client.
Checkpoint bỏ context; resume dựng context xác thực mới, khôi phục budget, scratch,
urgency và thứ tự sự kiện. Các `save_*` tool chỉ áp dụng proposal bất biến đã duyệt,
với preview được đọc lại từ server.

Roleplay dùng cùng runtime nhưng partner không có tool. Evidence reader và roleplay
coach là lời gọi Responses có cấu trúc riêng, không phải một mạng agent tự handoff.
Lớp urgency xác định luôn chạy; model-assisted safety chỉ bật khi backend được cấu
hình `SAFEVOICE_MODEL_ASSISTED_SAFETY=1`.

## Session, memory và knowledge

`make_session` chỉ được gọi sau khi ConversationService kiểm tra owner; SDK tables
nằm trong `agent_store`, giữ Unicode, không tự tạo bảng và giới hạn lịch sử nạp vào.
Khi có OpenAI client, backend bọc session bằng compaction ở chế độ `input` với policy
ước lượng token. Policy mặc định tắt trong factory phục vụ caller không truyền policy;
đường backend thật truyền [token_compaction_policy](src/safevoice_agent/memory/compaction.py).

Ký ức được duyệt vào instructions động, không sao chép vào replay history. Memory
retrieval dùng lexical trong DB; ứng viên mới phải qua validation và người dùng duyệt
ở luồng riêng. Kho tri thức công cộng dùng retriever qua shared Protocol; mặc định
pgvector/Voyage, fixture phải chọn rõ ràng và bị chặn trong production.

Xem [ingestion](ingestion/README.md), [evals](evals/README.md) và
[dữ liệu, bảo mật](../README.md#cách-hệ-thống-hoạt-động) để hiểu các ranh giới này.

## Kiểm tra khi phát triển

Chạy từ gốc repo sau khi cài workspace:

```powershell
uv run python -m pytest agent/tests -q
uv run python -m pyright agent/src
```

Lệnh pytest mặc định loại `integration` và `live_agent`; không cần khóa hay gọi mô hình.
Integration dùng dữ liệu tổng hợp và DB loopback, cấu hình từ tiến trình hoặc file
`test.env` của stack local, không dùng credential production. Chạy riêng khi stack đã sẵn sàng:

```powershell
uv run python -m pytest agent/tests/integration -m integration -q
```

Xem [hướng dẫn kiểm thử](../README.md#kiểm-thử) để dựng stack, chạy full-stack E2E
và phân biệt scripted model với live model. Kết quả offline không tự chứng minh chất
lượng trả lời hay mức sẵn sàng dùng dữ liệu học sinh thật.

Đọc [trạng thái và giới hạn](../README.md#trạng-thái-và-giới-hạn) trước khi diễn giải kết quả đánh giá hoặc thử với provider thật.
