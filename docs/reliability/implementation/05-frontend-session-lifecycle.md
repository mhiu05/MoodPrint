# Vòng đời phiên

`SessionRoot` là nơi duy nhất gọi lại `GET /session` cho focus, visibility, online và hook khách. Hook khách không tự mở request thứ hai.

| Tình huống | Hành vi |
|---|---|
| Lần mở đầu lỗi | Màn hình “Chưa thể mở MoodPrint”. Không có nội dung riêng. |
| Đã vào app, lỗi tạm thời | Giữ cây giao diện. Banner kết nối. Khóa ghi và request riêng mới. |
| Ân hạn | 30 giây tính từ lỗi đầu. Focus, online và bấm thử lại không gia hạn. |
| Hết ân hạn | Ẩn nội dung riêng. Không giữ bản nháp trên màn hình. |
| 401 hoặc hết hạn khách | Xóa phiên ngay, kể cả tab khác qua BroadcastChannel. |
| 403, ví dụ tài khoản bị khóa | Không coi là sự cố mạng. Không hiện banner kết nối. |
| Thành công sau gián đoạn | “Đã kết nối lại. Bạn có thể tiếp tục.” rồi ẩn sau 4 giây. |

Retry chỉ áp cho lần đọc phiên: tối đa 3 lần, ngân sách 20 giây, mỗi lần không quá 8 giây, jitter tối đa 500 ms rồi 1 giây. `Retry-After` dài hơn phần thời gian còn lại thì dừng. Login, gửi tin, nhật ký và upload không tự gửi lại.

`ApiClient.setPrivateHold` chặn mọi request trừ `GET /session` trong lúc ân hạn. Timeout của chính request thành `REQUEST_TIMEOUT`. Abort do caller hoặc `reset()` không bị biến thành timeout.

Epoch của `api.reset()` vẫn chặn response muộn sau logout hoặc hết hạn.
