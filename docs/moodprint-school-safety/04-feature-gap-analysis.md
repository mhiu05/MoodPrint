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
| Tài khoản mẫu, reset, xoay mật khẩu | Script 2 tài khoản test | `scripts/seed_school_samples.py` | WS-02 |
| Khách đủ tính năng, tự xóa sau 2 giờ | Chỉ chat | Purge bảng mới, giá giọng nói, giảm mức giữ ngân sách | WS-02, WS-04 |
| Tình huống mẫu cho khách | Không có | Trang `/vi-du`, hồ sơ mẫu | WS-09 |
| Eval an toàn ≥ 300 mẫu | Không có | Dataset + runner | WS-03, WS-10 |
| Eval truy xuất ≥ 100 câu | Có khung journal | Dataset + runner | WS-05 |
| Ba kịch bản E2E | Không có | Spec Playwright | WS-10 |
| Accessibility 2 nhóm tuổi | Có axe | Copy, checklist | WS-09 |
| Ledger STT/TTS | Không có | `speech_usage` | WS-08 |
| Không log nội dung | Đã tốt | Giữ, thêm test | WS-03 |
| Release staging | Pipeline có | SQL review, SSM, seed | WS-10 |

## Ngoài phạm vi MVP

| Hạng mục | Lý do |
| --- | --- |
| Console tổ tư vấn | Giai đoạn sau; `case_shares` chừa chỗ |
| Hỏi thăm sau khi kể | Hoãn; `proactive` sẵn nền |
| Realtime speech | Hoãn |
| Chia sẻ có link | Hoãn; MVP xuất PDF |
| Đồng ý của người đại diện, Luật BVDLCN | Cổng trước thí điểm |
| Reranker | Chỉ khi eval chứng minh cần |
| Đọc nội dung ảnh bằng model | Rủi ro pháp lý và an toàn |
| Audio làm bằng chứng | Hồ sơ nhận ảnh và video; audio để sau |

## Cổng bắt buộc trước khi mở cho học sinh thật

Không thuộc đợt release này, xem [OD-15](12-open-decisions.md#od-15--ai-được-dùng-bản-release-này). Pass G0–G5 **không** mở cổng này.

1. Tuân thủ Luật Bảo vệ dữ liệu cá nhân 2025, đồng ý của người đại diện.
2. Bật zero data retention với OpenAI trước khi xử lý dữ liệu cá nhân trẻ dưới 13 tuổi hoặc dưới tuổi đồng ý số, theo [Under-18 guidance](https://developers.openai.com/api/docs/guides/safety-checks/under-18-api-guidance).
3. Rà điều khoản của OpenAI, Voyage, nhà cung cấp STT/TTS về người dùng vị thành niên.
4. Tách database và Storage khỏi dữ liệu hiện có.
5. Xác minh tuổi phù hợp, đường leo thang cho tương tác rủi ro cao, cơ chế giám sát.
6. Đánh giá độc lập bởi chuyên gia tâm lý học đường và pháp lý.
7. Người lớn thật phụ trách phản hồi sự cố.
8. Backup, restore, xóa dữ liệu đã diễn tập.
9. Xem lại quyết định nhận mọi ảnh, video ([OD-03](12-open-decisions.md#od-03--upload-ảnh-video)).
10. Quyết định lại việc khách không cần xác minh và đăng ký đang đóng.
