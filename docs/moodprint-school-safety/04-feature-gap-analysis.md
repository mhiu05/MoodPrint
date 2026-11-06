# 04 — Phân tích khoảng trống tính năng

Mỗi dòng ánh xạ yêu cầu sang hiện trạng và workstream. Trạng thái dựa trên [audit](01-codebase-audit.md).

| Yêu cầu | Hiện trạng | Khoảng trống | WS |
| --- | --- | --- | --- |
| Một Trợ lý duy nhất | Ba agent V3, năm bot cũ | Persona, bot id, UI | WS-04, WS-09 |
| Hiểu tình huống | Không có | WF-01, phân loại hành vi | WS-04 |
| Hồ sơ nhiều sự việc | Journal theo ngày | Toàn bộ schema, API, UI | WS-06 |
| SHA-256 + thời điểm server | Không có | Tải về để băm, bất biến | WS-06 |
| Sửa không phá hủy | Ghi đè | Bản phiên bản | WS-06 |
| Xuất PDF | Không có thư viện | `reportlab`, font tiếng Việt | WS-06 |
| Kế hoạch an toàn | Không có | Template + WF-03 | WS-07 |
| Người lớn tin cậy | Không có | Bảng, UI, WF-04 | WS-07 |
| Soạn tin nhắn, thẻ 111 | Không có | Tool + UI | WS-07 |
| Hướng dẫn báo cáo nền tảng | Không có | Thẻ KB `manual_capture` | WS-05 |
| Luyện nói | Chỉ STT | TTS, phiên, role-play, tổng kết | WS-08 |
| Push-to-talk | Bấm bắt đầu/dừng | Giữ để nói, sóng âm | WS-08 |
| Tìm hỗ trợ không cần đăng nhập | Không có | Route public | WS-02, WS-09 |
| Nút khẩn cấp | Không có | Component toàn cục | WS-09 |
| Thoát nhanh | Không có | Component + xóa state | WS-09 |
| Khóa PIN | Không có | Server + UI | WS-06, WS-09 |
| Tên trung tính | Không có | Tùy chọn hiển thị | WS-09 |
| Chế độ người chứng kiến | Không có | WF-05, thẻ KB | WS-04, WS-05 |
| Safety nhiều tầng | Regex tự hại | Toàn bộ | WS-03 |
| KB có căn cứ | Không có | Pipeline, thẻ, index, verifier | WS-05 |
| Nhãn tham khảo do backend gắn | Có `source_backed` | Dùng đúng nghĩa | WS-04 |
| Tuổi 11–14, 15–17 | Chỉ 18+ | `school_profiles` | WS-02 |
| Điều khoản ngắn | Disclosure guest | Màn hình + `terms_version` | WS-02 |
| Đóng đăng ký | Mở | Cổng `/auth/signup` | WS-02 |
| Trang quyền riêng tư ngắn | Không có | `/quyen-rieng-tu`, dẫn chiếu Turnstile Addendum | WS-09 |
| Khách đủ tính năng, tự xóa sau 2 giờ | Chỉ chat | Purge bảng mới, giá giọng nói, giảm mức giữ ngân sách | WS-02, WS-04 |
| Eval an toàn ≥ 300 mẫu | Không có | Dataset + runner | WS-03, WS-10 |
| Eval truy xuất ≥ 100 câu | Có khung journal | Dataset + runner | WS-05 |
| Ba kịch bản E2E | Không có | Spec Playwright | WS-10 |
| Accessibility 2 nhóm tuổi | Có axe | Copy, checklist | WS-09 |
| Ledger STT/TTS | Không có | `speech_usage` | WS-08 |
| Không log nội dung | Đã tốt | Giữ, thêm test | WS-03 |
| Release staging | Pipeline có | SQL review, SSM, cổng mở | WS-10 |

## Ngoài phạm vi MVP

| Hạng mục | Lý do |
| --- | --- |
| Console tổ tư vấn | Giai đoạn sau; `case_shares` chừa chỗ |
| Hỏi thăm sau khi kể | Hoãn; `proactive` sẵn nền |
| Realtime speech | Hoãn |
| Chia sẻ có link | Hoãn; MVP xuất PDF |
| Luồng đồng ý của người đại diện, Luật BVDLCN, ZDR | Chỉ cần khi có học sinh thật |
| Reranker | Chỉ khi eval chứng minh cần |
| Đọc nội dung ảnh bằng model | Rủi ro pháp lý và an toàn |
| Audio làm bằng chứng | Hồ sơ nhận ảnh và video; audio để sau |

## Cổng bắt buộc trước khi mở cho học sinh thật

Không thuộc đợt này ([OD-15](12-open-decisions.md#od-15--ai-dùng-sản-phẩm)). Danh sách ở [cổng G6](10-evaluation-and-quality-gates.md#cổng-g6-khi-có-học-sinh-thật), để dùng khi có học sinh thật.

