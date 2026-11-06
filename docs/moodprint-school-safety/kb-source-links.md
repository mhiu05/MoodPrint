# Link nguồn cho thẻ KB

Ngày tra: **06/11/2026**. Danh sách gợi ý theo [OD-02](12-open-decisions.md#od-02--duyệt-nội-dung). Grok đưa vào `kb/sources/registry.yaml` theo [07](07-knowledge-base-design.md).

| Ký hiệu | Nghĩa |
| --- | --- |
| Đọc được | Đã mở tự động, thấy đúng tiêu đề và nội dung |
| Tìm thấy | Có trong kết quả tìm kiếm trên domain chính thức, chưa mở toàn văn |
| Mở tay | Công cụ tự động bị chặn hoặc timeout; link cần mở bằng trình duyệt, chưa xác nhận còn sống |

Khi soạn thẻ, trích từ văn bản gốc. Viết lại bằng lời cho học sinh, không chép nguyên trang.

## Pháp luật Việt Nam

| `source_id` | Văn bản | Link | Trạng thái | Dùng cho |
| --- | --- | --- | --- | --- |
| `vn-luat-tre-em-vbhn` | Luật Trẻ em, **bản hợp nhất** VBHN 108 (2025) | [PDF](https://datafiles.chinhphu.vn/cpp/files/vbpq/2025/9/108-vbhn-vpqh.pdf) | Tìm thấy | Quyền trẻ em, trách nhiệm bảo vệ. Ưu tiên bản này |
| `vn-luat-tre-em-2016` | Luật 102/2016/QH13, bản gốc | [Cổng Chính phủ](https://vanban.chinhphu.vn/default.aspx?pageid=27160&docid=184566), [VietLaw](https://vietlaw.quochoi.vn/Pages/vbpq-toan-van.aspx?ItemID=27998) | Tìm thấy | Đối chiếu. VBPL ghi hết hiệu lực một phần |
| `vn-nd-80-2017` | Nghị định 80/2017/NĐ-CP, hiệu lực 05/09/2017 | [Cổng Chính phủ](https://vanban.chinhphu.vn/default.aspx?pageid=27160&docid=190430), [Công báo](https://congbao.chinhphu.vn/van-ban/nghi-dinh-so-80-2017-nd-cp-24286.htm) | Tìm thấy | Định nghĩa bạo lực học đường, trách nhiệm nhà trường |
| `vn-tt-18-2025` | Thông tư 18/2025/TT-BGDĐT, hiệu lực 31/10/2025 | [Cổng Chính phủ](https://vanban.chinhphu.vn/?pageid=27160&docid=215348), [PDF Công báo](https://congbao.chinhphu.vn/tai-ve-van-ban-so-18-2025-tt-bgddt-46274-59086?format=pdf), [VBPL](https://vbpl.vn/TW/Pages/vbpq-thuoctinh.aspx?ItemID=183284) | Tìm thấy; VBPL ghi còn hiệu lực | Tư vấn học đường, bảo mật, tự nguyện |
| `vn-tt-19-2025` | Thông tư 19/2025/TT-BGDĐT, hiệu lực 31/10/2025 | [Cổng Chính phủ](https://vanban.chinhphu.vn/?pageid=27160&docid=215387), [Toàn văn](https://xaydungchinhsach.chinhphu.vn/toan-van-thong-tu-19-2025-tt-bgddt-quy-dinh-ve-khen-thuong-va-ky-luat-hoc-sinh-11925091809025953.htm) | Tìm thấy | Kỷ luật học sinh, phục vụ tình huống SC-05 |
| `vn-moet-nd80` | Bài giới thiệu Nghị định 80 của Bộ GD-ĐT | [Bộ GD-ĐT](https://moet.gov.vn/giaoducquocdan/cong-tac-hoc-sinh-sinh-vien/Pages/Default.aspx?ItemID=4937) | Tìm thấy | Tóm lược dễ hiểu, chỉ để đối chiếu |

**Điểm cần cẩn thận khi soạn thẻ**:

- Luật Trẻ em định nghĩa trẻ em là người **dưới 16 tuổi**. Thẻ cho nhóm 15–17 không được khẳng định chung rằng em thuộc phạm vi luật này.
- Bộ GD-ĐT cho biết đang nghiên cứu sửa Nghị định 80. Kiểm tra lại hiệu lực trước khi duyệt, đặt `next_review_at` ngắn.
- Thông tư 19 thay Thông tư 08/TT năm 1988. Nguồn cũ nói về đình chỉ học đã lỗi thời.
- Luật Giáo dục sửa đổi 123/2025/QH15 chỉ tìm thấy ở nguồn thứ cấp. Chỉ dùng khi tìm được bản trên cổng chính thức.

## Tổng đài 111

| `source_id` | Nội dung | Link | Trạng thái |
| --- | --- | --- | --- |
| `vn-tongdai111-site` | Tổng đài Điện thoại quốc gia Bảo vệ Trẻ em, Cục Bà mẹ và Trẻ em, 24/24, miễn phí | [tongdai111.vn](https://tongdai111.vn/) | Đọc được |
| `vn-tongdai111-report-2025` | Báo cáo năm 2025 | [PDF](https://tongdai111.vn/uploads/files/B%C3%A1o%20c%C3%A1o%20T%E1%BB%95ng%20%C4%91%C3%A0i%20BVTE%20111%20%20n%C4%83m%202025.pdf) | Tìm thấy |

## Nền tảng

Trang chính thức dùng làm `source_url`. Bước bấm cụ thể lấy từ ảnh chụp app thật của mhiu05, vì giao diện đổi theo phiên bản.

| `source_id` | Trang | Link | Trạng thái |
| --- | --- | --- | --- |
| `platform-tiktok` | Ngăn chặn hành vi bắt nạt | [TikTok Safety](https://www.tiktok.com/safety/vi-vn/bullying-prevention/) | Đọc được, tiếng Việt |
| `platform-tiktok` | Nguyên tắc Cộng đồng, hiệu lực 24/09/2026 | [TikTok](https://www.tiktok.com/community-guidelines/vi-vn/) | Đọc được, tiếng Việt |
| `platform-tiktok` | Báo cáo vấn đề | [TikTok Support](https://www.tiktok.com/support/faq_detail?id=7581820702655978040) | Đích chuyển hướng, chưa đọc nội dung |
| `platform-tiktok` | Chặn người dùng | [TikTok Support](https://www.tiktok.com/support/faq_detail?id=7543897460691851781) | Đích chuyển hướng, chưa đọc nội dung |
| `platform-youtube` | Báo cáo video, kênh, nội dung không phù hợp | [YouTube Help](https://support.google.com/youtube/answer/2802027?hl=vi) | Đọc được, tiếng Việt |
| `platform-youtube` | Chính sách quấy rối và bắt nạt qua mạng | [YouTube Help](https://support.google.com/youtube/answer/2802268?hl=vi) | Đọc được, tiếng Việt |
| `platform-youtube` | Các lựa chọn khác để báo vi phạm | [YouTube Help](https://support.google.com/youtube/answer/2802057?hl=vi) | Đọc được, tiếng Việt |
| `platform-facebook` | Báo cáo trên Facebook | [Facebook Help](https://www.facebook.com/help/263149623790594) | Đọc được, tiếng Việt |
| `platform-facebook` | Chặn trang cá nhân, Trang | [Facebook Help](https://www.facebook.com/help/168009843260943) | Đọc được, tiếng Việt |
| `platform-facebook` | Tiêu chuẩn về bắt nạt và quấy rối | [Meta Transparency](https://transparency.meta.com/policies/community-standards/bullying-harassment/) | Mở được, chưa đọc phần nội dung; tiếng Anh |

## Kỹ năng ứng phó

| `source_id` | Nội dung | Link | Trạng thái | `jurisdiction` |
| --- | --- | --- | --- | --- |
| `unicef-vn-safe-online` | Những điều cần biết để an toàn trong không gian mạng | [UNICEF Việt Nam](https://unicef.org/vietnam/vi/nh%E1%BB%AFng-c%C3%A2u-chuy%E1%BB%87n/nh%E1%BB%AFng-%C4%91i%E1%BB%81u-c%E1%BA%A7n-bi%E1%BA%BFt-%C4%91%E1%BB%83-to%C3%A0n-trong-kh%C3%B4ng-gian-m%E1%BA%A1ng) | Tìm thấy | `vn` |
| `unicef-vn-violence` | Bạo lực với trẻ em | [UNICEF Việt Nam](https://www.unicef.org/vietnam/vi/topics/b%E1%BA%A1o-l%E1%BB%B1c-v%E1%BB%9Bi-tr%E1%BA%BB-em) | Tìm thấy | `vn` |
| `unicef-vn-protection` | Bảo vệ trẻ em | [UNICEF Việt Nam](https://www.unicef.org/vietnam/vi/ch%E1%BB%A7-%C4%91%E1%BB%81/b%E1%BA%A3o-v%E1%BB%87-tr%E1%BA%BB-em) | Tìm thấy | `vn` |
| `unicef-cyberbullying` | Cách ngăn bắt nạt trên mạng | [UNICEF](https://www.unicef.org/end-violence/how-to-stop-cyberbullying) | Mở tay | `global` |
| `foreign-stopbullying-what` | Bắt nạt trên mạng là gì | [StopBullying.gov](https://www.stopbullying.gov/cyberbullying/what-is-it) | Mở tay | `foreign` |
| `foreign-stopbullying-kids` | Việc em có thể làm | [StopBullying.gov](https://www.stopbullying.gov/kids/what-you-can-do) | Mở tay | `foreign` |
| `foreign-esafety-young` | Cyberbullying cho người trẻ | [eSafety](https://www.esafety.gov.au/young-people/cyberbullying) | Mở tay | `foreign` |
| `foreign-esafety-image` | Lạm dụng hình ảnh | [eSafety](https://www.esafety.gov.au/young-people/image-based-abuse) | Mở tay | `foreign` |

Nguồn `foreign` chỉ dùng cho kỹ năng ứng phó, không dùng cho quyền lợi hay quy trình tại Việt Nam. Trang nào thuộc nhóm Mở tay mà link không còn, bỏ nguồn đó, không đoán nội dung.

## Ánh xạ nhóm thẻ

| `action` | Số thẻ | Nguồn chính |
| --- | --- | --- |
| `understand` | 8 | `vn-nd-80-2017`, `unicef-vn-safe-online`, `foreign-stopbullying-what` |
| `safety` | 8 | `foreign-esafety-young`, `unicef-vn-safe-online` |
| `evidence` | 5 | `foreign-esafety-young`, trang nền tảng |
| `report` | 9 | `platform-facebook`, `platform-youtube`, `platform-tiktok` × báo cáo, chặn, lưu bằng chứng |
| `rights` | 8 | `vn-luat-tre-em-vbhn`, `vn-nd-80-2017`, `vn-tt-18-2025`, `vn-tt-19-2025` |
| `support` | 9 | `vn-tongdai111-site`, `vn-tt-18-2025`, `foreign-stopbullying-kids` |

Tổng 47 thẻ.
