# Publication, candidate reference và social lifecycle

## Public profile

Private items không tự thành hồ sơ tìm bạn. Người dùng chọn taxonomy tags trong matching draft (`GET/PUT /profiles/matching-draft`). `POST .../preview` tạo digest ngẫu nhiên, có hạn **15 phút**, gắn draft version. Publish nhận `draftVersion`, `previewDigest`, `expectedPublishedVersion`, kiểm tra lại content/version/expiry rồi commit published snapshot.

Publish là hành động người dùng cho phép hiển thị hồ sơ; consent/version được cập nhật theo route. Không thay bằng việc AI nói “đã tạo hồ sơ”. Response `PublishedView.state` có `live`, `needs_republish`, `stale`. Sau rút MATCH rồi bật lại không tự live; sau 180 ngày cần xác nhận lại.

Withdraw profile loại khỏi discovery. Quyền dùng **room đã mở** được kiểm tra bằng consent/adult/block/status và pair policy riêng; không buộc profile tiếp tục public chỉ để đọc room đang hợp lệ. Xem `room_permitted` và `current_profile` trong [service.py](../../backend/app/modules/social/service.py).

## Candidate ref

`GET /matching/candidates` trả tối đa 5 card: alias/avatar seed theo pair, public profile, tối đa 3 reasons, qualitative match label, scoring/profile versions và opaque `candidateRef`. Ref snapshot cả hai profile/consent versions, owner viewer, peer, scorer/rank; expiry 15 phút.

Ref không phải bearer quyền truy cập bất kỳ peer nào: server kiểm tra owner và live pair policy trước skip/request/block. Thay đổi consent/profile/block sau khi card render vẫn có thể làm thao tác bị từ chối. Client cần tải lại gợi ý thay vì sửa ref/version.

## Requests và connections

| Hành động | Điều kiện / kết quả |
| --- | --- |
| Skip candidate | Resolve ref, canonical pair transaction, cooldown 30 ngày |
| Gửi request | Live current ref/pair, limit, không room/request xung đột; expiry 7 ngày |
| Accept | Recipient, pending/version/expiry/live policy; tạo open connection |
| Decline/cancel | Đúng vai trò và state; cooldown theo route |
| Gửi message | Room membership và live policy; clientMessageId dedup, sequence commit cùng message |
| End room | Kết thúc quyền chat, cooldown, abort hoạt động liên quan |
| Block | Ghi block, vô hiệu pair access/room và abort activity; không có unblock UI trong flow hiện tại |

Pending request card chỉ trả peer public card khi request và pair còn đủ quyền. Không phục hồi private identity từ alias. Pair alias phục vụ ẩn danh giữa hai người; reveal grant là flow riêng.

## Message và notification

Human messages có seq dạng chuỗi, client message ID, sender `self/peer`, accepted timestamp. Read watermark chỉ thuộc viewer. Notification SSE cho biết room watermark/activity thay đổi; GET projection/message vẫn chạy authorization. UI dùng polling/reconnect khi cần, không tự coi socket còn mở là quyền vĩnh viễn.

Message reads bị giới hạn retention 90 ngày. Connection summary có last message preview/unread và active activity theo DTO; không thêm raw private profile/memory vào inbox để “cá nhân hóa”.

## Race và privacy checks

User rows được khóa theo canonical UUID order trước pair/resource. Các transaction reciprocal phải giữ cùng order. Discovery lấy shared gates và recheck eligibility trong batch, tránh cấp ref cho snapshot đã mất quyền.

Regression coverage cần có: cross-user ref, expired ref, profile republish, consent revoke giữa read/write, block hai chiều, reciprocal accepts, dedup message, room end/abort, moderation restriction và deletion. Nguồn test trong `test_matching_lifecycle.py`, `test_social_lifecycle.py`, `test_pair_alias.py`, `test_unread.py` và fullstack specs.
