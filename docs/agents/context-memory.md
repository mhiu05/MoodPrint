# Context, lịch sử và ghi nhớ

## Bốn lớp dữ liệu

| Lớp | Nơi lưu | Điều kiện sử dụng |
| --- | --- | --- |
| Temporary transcript | RAM `ConversationStore` | Owner/session, AI consent, TTL |
| Persistent transcript | `ai_conversations`, `ai_messages` | Global history capability và preference người dùng |
| Approved memory | `memories`; embedding/index tùy chọn | Confirm của người dùng; MEM và AI gates |
| Public profile | `published_profiles` | Preview/publish rõ ràng, MATCH và adult gates |

Không lấy public profile từ memory tự động. Không coi việc nhìn thấy transcript cũ là cho phép gửi toàn bộ transcript đó vào model. Không dùng semantic memory để mở quyền đọc mood hoặc dữ liệu peer.

Saved conversation được giữ tối đa 30 ngày trong implementation hiện tại: `preference_view` và conversation creation clamp `CHAT_RETENTION_DAYS` bằng 30, dù validator cho phép cấu hình đến 90. Dùng response `retentionDays` và `expiresAt` làm thông tin hiển thị thực tế.

## Context projection

[context.py](../../backend/app/ai/context.py) giới hạn history **24 messages / 24.000 byte UTF-8**. Ưu tiên message mới, lấy contiguous suffix theo thứ tự thời gian; message không vừa budget làm dừng việc lấy phần cũ. Approved memories được thêm dưới dạng data JSON, tối đa 10 trong bước build, còn phải vừa byte budget.

Mỗi lượt có content-free stamp: `data_version` và policy `text-v1` hoặc `mood-turn-v1`. `model_messages()` đi ngược từ cuối và dừng khi stamp thiếu/không nhận diện, data version không khớp, hoặc message mood thuộc run khác. Cả user và bot text phụ thuộc nguồn cũ đều bị cắt khỏi context. Transcript UI không bị viết lại bởi projection này.

Thay đổi preference/quyền/dữ liệu làm tăng `User.data_version`, hủy active run liên quan và invalidate RAM. Legacy record thiếu policy không được mặc định là an toàn. Migration [0015](../../backend/alembic/versions/0015_context_privacy_context_privacy.py) hỗ trợ boundary này.

## Mood scope và bằng chứng

`MoodReadScope` nhận `fromDate`/`toDate`, tối đa 90 ngày liên tiếp; service còn kiểm tra cửa sổ lưu trữ theo ngày local. Chỉ lựa chọn của lượt hiện tại cho phép đọc, và chỉ Nhịp được tool tương ứng. Lựa chọn lại cùng khoảng ngày ở lượt mới không làm bằng chứng của lượt cũ tự hợp lệ.

Source diagnostics tách `authorization` với `evidence`: được cấp quyền chưa có nghĩa tool đã đọc thành công. Truy vấn thành công không có bản ghi là `retrieved` với count 0; không được suy ra ngày thiếu là điểm 0. Mood evidence được backend tạo, ràng buộc owner/run/data version/time và dùng để render thống kê có căn cứ. [evidence.py](../../backend/app/ai/evidence.py) và [mood service](../../backend/app/modules/mood/service.py) là nguồn quy tắc.

## Proposal và memory lifecycle

1. Tool tạo proposal cho ghi nhớ AI; proposal chưa là dữ liệu đã duyệt.
2. UI đọc `/proposals`, hiển thị nội dung, có thể sửa trước confirm hoặc reject.
3. `/proposals/{id}/confirm` kiểm tra owner, session/authorization, expiry, expected version và data version; lưu target cùng receipt trong transaction.
4. `/memories/{id}` cho phép sửa/xóa theo version. Thay đổi invalidate context/index có liên quan.
5. Rút quyền, xóa dữ liệu và retention xử lý proposal/memory/index theo trạng thái. Không dùng proposal pending như approved memory.

Nguồn: [memory.py](../../backend/app/ai/memory.py), [memory_models.py](../../backend/app/ai/memory_models.py), [lifecycle](../backend/data-lifecycle.md).

## Semantic retrieval tùy chọn

Capability `SEMANTIC_MEMORY_ENABLED`, Voyage key và preference `semanticMemoryEnabled` là các gate riêng. Bật preference còn yêu cầu MEM. Embedding jobs chỉ xử lý memory được phép; không index transcript hay public candidate data như một lối tắt.

[embeddings.py](../../backend/app/ai/embeddings.py) dùng jobs có lease/attempt, kiểm tra lại authorization/version trước commit. Tắt preference loại bỏ index user qua `discard_user_index`; sửa/xóa memory làm dữ liệu vector cũ không còn là nguồn hợp lệ. Provider lỗi không được biến thành kết quả từ nguồn cấm.

Mặc định embedding model `voyage-4-lite`, dimensions 1024; các giá trị cấu hình khác ở [configuration](../backend/configuration.md). Dữ liệu gửi đến provider là xử lý ngoài hệ thống; tắt tracing hoặc `store=False` không chứng minh đã xóa dữ liệu khỏi provider/backup.

## Lời hỏi thăm trong context

Tin chủ động có stamp riêng: `proactive-text-v1` vào context như câu trả lời thường; `proactive-journal-v1` (Nhịp dùng khoảnh khắc hôm qua) chỉ vào context của lượt kế tiếp nếu trong 36 h **và** `revalidate_sources` dưới owner lock xác nhận: consent vẫn bật đúng `journal_context_version` (ghi trong `ai_message_sources.policy`), mỗi entry nguồn vẫn `saved`, đúng revision, trong 90 ngày. Khi đó lượt hiện tại được stamp `journal-turn-v1` **trước** khi prose tới model, nên các lượt sau tự cắt nó. Sửa/xóa entry, tắt (kể cả tắt rồi bật lại) consent hoặc `data_version` đổi đều làm tin đó và mọi tin cũ hơn bị cắt (fail closed). Payload lời hỏi thăm chỉ chứa tối đa 3 entry `saved` của hôm qua theo múi giờ lịch, của chính chủ, ngoài nháp/media/mood note cũ; không có approved memory.

## Kiểm thử bảo vệ boundary

`test_context_selection.py`, `test_context_privacy_migration.py`, `test_privacy_lifecycle.py`, `test_memory.py`, `test_embeddings.py`, `test_scoped_mood_tool.py` và `test_mood_evidence_runtime.py` kiểm tra projection, revoke, ownership, jobs, nguồn và evidence. Kiểm thử fake provider xác minh logic ứng dụng; live provider cần gate riêng trong [evaluation](evaluation.md).
