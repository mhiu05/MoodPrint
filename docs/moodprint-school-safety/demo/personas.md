# Nhân vật trong kịch bản

**Toàn bộ là hư cấu.** Không phải người thật, trường thật. Tên trường dùng dạng chung. Không dùng dữ liệu của trẻ em thật trong fixture, eval hay ảnh chụp màn hình.

Chỉ dùng trong test local và eval, không tạo trên hosted. Fixture ở `frontend/tests/fullstack/fixtures/school-personas.json` (WS-02-T08).

| Khóa | Tên | Tuổi | Lớp | Nhóm tuổi | Vai trò | Ca dùng |
| --- | --- | --- | --- | --- | --- | --- |
| `kb-a` | Minh An | 12 | 7 | 11-14 | Bị bắt nạt trên mạng | KB-A, SC-06, SC-07, SC-08, SC-09, SC-10 |
| `kb-b` | Tuấn Khang | 15 | 10 | 15-17 | Bị chặn đường, đòi tiền | KB-B, SC-02, SC-05 |
| `kb-c` | Hà Linh | 13 | 8 | 11-14 | Người chứng kiến | KB-C, SC-01 |
| `sc-d` | Thu Trang | 14 | 9 | 11-14 | Bị đe dọa bằng ảnh riêng tư | SC-03 |
| `sc-e` | Bảo Nam | 16 | 11 | 15-17 | Người gây hại là người lớn | SC-04 |

## Minh An (`kb-a`)

Học lớp 7, sống với bố mẹ, thân với một bạn cùng lớp. Một nhóm bạn lập nhóm chat nói xấu và chế ảnh An. Tin cô chủ nhiệm, ngại nói với bố mẹ. Dùng Facebook và TikTok trên điện thoại của mẹ. Giọng viết ngắn, có teencode nhẹ, không dấu khi vội.

## Tuấn Khang (`kb-b`)

Học lớp 10, đi học bằng xe đạp. Một nhóm học sinh trường khác chặn đường sau giờ học, đòi tiền. Tin anh họ và thầy giám thị. Sợ bị trả thù nếu báo. Giọng viết dè dặt, nói giảm.

## Hà Linh (`kb-c`)

Học lớp 8. Thấy một bạn bị đánh ở sân sau và bị quay clip; clip lan trong nhóm lớp. Muốn giúp nhưng sợ bị lộ. Tin cô tư vấn của trường.

## Thu Trang (`sc-d`)

Học lớp 9. Bị một người quen trên mạng đe dọa tung ảnh riêng tư. Ca này không có ảnh nào, chỉ có lời kể ở mức không mô tả.

## Bảo Nam (`sc-e`)

Học lớp 11. Bị một giáo viên quát mắng, đe dọa khi gọi ở lại riêng. Tin mẹ và cô tư vấn.

## Dữ liệu fixture cho hồ sơ

Ảnh mẫu là ảnh tổng hợp do nhóm tạo, không có khuôn mặt người thật, không có tên thật.

| Persona | Hồ sơ mẫu | Sự việc | Ảnh | Người lớn tin cậy |
| --- | --- | --- | --- | --- |
| `kb-a` | "Nhóm chat lớp" | 3, trong 2 tuần | 1 ảnh giả lập tin nhắn, tên bí danh | Cô chủ nhiệm |
| `kb-b` | Trống | 0 | 0 | Anh họ, Thầy giám thị |
| `kb-c` | Trống | 0 | 0 | Cô tư vấn |
| `sc-d` | "Tin nhắn đe dọa" | 1 | 0 | Mẹ |
| `sc-e` | Trống | 0 | 0 | Thầy chủ nhiệm, Mẹ, Cô tư vấn |

## Tài khoản khách

Khách có đủ tính năng, dữ liệu tự xóa sau 2 giờ. Xem [OD-05](../12-open-decisions.md#od-05--chế-độ-khách).
