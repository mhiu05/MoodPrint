# Thông báo quyền riêng tư MoodPrint — BẢN NHÁP

> **Trạng thái:** bản nháp kỹ thuật (I-08), **chưa được pháp lý duyệt** (cổng phát hành G8).
> Không hiển thị trong ứng dụng cho tới khi chủ sản phẩm và tư vấn pháp lý phê duyệt; liên kết từ
> phần chân trang Cài đặt là một việc riêng sau khi duyệt.
>
> **Danh sách kiểm tra T-DOC-01**
> - [x] Mục đích xử lý theo từng tính năng (§2)
> - [x] Loại dữ liệu (§3)
> - [x] Mọi nhà cung cấp: OpenAI, Voyage AI, Supabase, AWS — kèm mục đích (§4)
> - [x] Mọi dòng của bảng lưu giữ trong 09 §10 (§5)
> - [x] Quyền: xuất dữ liệu, xóa tài khoản, rút đồng ý (§6)
> - [x] Chính sách độ tuổi (§7) và kiểm duyệt (§8)
> - [ ] Thông tin liên hệ và bên kiểm soát dữ liệu — **cần chủ sản phẩm điền**
> - [ ] Rà soát pháp lý (Nghị định 13/2023/NĐ-CP) — **bên ngoài**
> - [ ] Xác minh chính sách lưu giữ/vùng của OpenAI và Voyage cho tài khoản dự án (Q-02)

## 1. Chúng tôi là ai

MoodPrint là ứng dụng ghi nhận cảm xúc, trò chuyện với trợ lý AI và kết nối ẩn danh với người
khác. Bên kiểm soát dữ liệu: _[tên pháp nhân — cần điền]_. Liên hệ về quyền riêng tư:
_[email — cần điền]_.

## 2. Chúng tôi dùng dữ liệu để làm gì

| Tính năng | Mục đích | Cơ sở |
|---|---|---|
| Tài khoản và đăng nhập | Xác thực, bảo vệ phiên, chống lạm dụng | Cần thiết để cung cấp dịch vụ |
| Nhật ký cảm xúc | Lưu và hiển thị cảm xúc, ghi chú của chính bạn | Cần thiết để cung cấp dịch vụ |
| Trợ lý AI | Tạo câu trả lời cho tin nhắn bạn chủ động gửi | Quyền AI được ghi nhận khi gửi lần đầu; có thể rút |
| Ghi nhớ của trợ lý | Lưu những điều bạn duyệt riêng từng mục | Duyệt mục đầu tiên ghi nhận quyền MEM; có thể rút |
| Kết nối (ghép bạn) | Gợi ý từ hồ sơ công khai bạn chọn đăng | Xem trước rồi xuất bản ghi nhận quyền MATCH; có thể rút hoặc ngừng chia sẻ |
| Giọng nói | Chuyển bản ghi âm chủ động thành văn bản | Chọn ghi âm ghi nhận quyền VOICE và xin phép trình duyệt; có thể rút |
| An toàn | Xử lý báo cáo, chặn, hạn chế hoặc tạm khóa tài khoản vi phạm | Lợi ích chính đáng: an toàn cộng đồng |
| Vận hành | Nhật ký kỹ thuật không chứa nội dung để phát hiện sự cố | Lợi ích chính đáng |

Chúng tôi **không** bán dữ liệu, **không** dùng nội dung của bạn để quảng cáo, và **không** dùng
cảm xúc, ghi chú hay cuộc trò chuyện với AI để ghép bạn với người khác.

## 3. Loại dữ liệu

- Tài khoản: email, mật khẩu (do Supabase Auth quản lý), năm sinh tự khai, múi giờ.
- Nội dung riêng tư: cảm xúc, ghi chú, tin nhắn với trợ lý AI, ghi nhớ đã duyệt.
- Hồ sơ kết nối (chỉ khi bạn đăng): bí danh, sở thích, mục tiêu, khung giờ, phong cách trò chuyện.
- Kết nối: lời mời, tin nhắn với người đã kết nối, câu trả lời trong hoạt động chung, dấu đã đọc
  (chỉ bạn thấy).
- An toàn: báo cáo bạn gửi (kèm tối đa hai tin nhắn và hai câu trả lời hoạt động bạn chọn làm bằng
  chứng), quyết định kiểm duyệt liên quan đến bạn.
- Kỹ thuật: thời điểm hoạt động gần nhất, bộ đếm sử dụng AI, nhật ký lỗi không chứa nội dung.

## 4. Nhà cung cấp xử lý dữ liệu

| Nhà cung cấp | Dữ liệu | Mục đích | Ghi chú |
|---|---|---|---|
| OpenAI | Tin nhắn với trợ lý AI (khi bạn đồng ý AI), thống kê cảm xúc tóm tắt cho lượt trả lời, âm thanh giọng nói (khi bật) | Tạo câu trả lời, chuyển giọng nói | Gửi với `store:false`, tắt tracing; chính sách lưu giữ/vùng cấp tài khoản **chưa xác minh (Q-02)** |
| Voyage AI | Ghi nhớ đã duyệt (khi tính năng bật và bạn đồng ý MEM) | Tạo vector để tìm ghi nhớ liên quan | Mặc định tắt trong beta; **chưa xác minh (Q-02)** |
| Supabase | Toàn bộ dữ liệu ứng dụng | Cơ sở dữ liệu và xác thực | Vùng ap-northeast-1 (Tokyo); sao lưu theo gói **chưa xác minh (Q-04)** |
| AWS | Nhật ký kỹ thuật không chứa nội dung | Giám sát, cảnh báo sự cố | Lưu 30 ngày |

Dữ liệu có thể được xử lý ngoài Việt Nam (Nhật Bản, Hoa Kỳ). _[Hồ sơ chuyển dữ liệu ra nước ngoài —
cần pháp lý xác nhận.]_

## 5. Thời gian lưu giữ

| Dữ liệu | Lưu giữ |
|---|---|
| Cảm xúc và ghi chú | 90 ngày |
| Tin nhắn giữa người với người | 90 ngày |
| Câu trả lời hoạt động chung / phiên đã kết thúc | 90 ngày |
| Dấu đã đọc | Đến khi kết nối kết thúc + 90 ngày, hoặc khi xóa tài khoản |
| Tham chiếu gợi ý kết nối | Hiệu lực 15 phút, xóa sau 24 giờ |
| Thống kê ghép bạn theo ngày (không định danh) | 1 năm |
| Báo cáo và quyết định kiểm duyệt | 1 năm |
| Cuộc trò chuyện AI mới được chọn lưu | Tối đa 30 ngày; hồ sơ cũ giữ hạn đã ghi khi tạo |
| Hàng đợi sự kiện nội bộ (outbox) | Xóa toàn bộ (không còn dùng) |
| Nhật ký kỹ thuật | 30 ngày |

Bản sao lưu được mã hóa và giữ tối đa 8 tuần; dữ liệu đã xóa có thể còn trong bản sao lưu tới khi
bản đó hết hạn và không được khôi phục cho tài khoản đã xóa.

## 6. Quyền của bạn

- **Xuất dữ liệu:** Cài đặt → Xuất dữ liệu (cần đăng nhập lại), gồm cảm xúc, hồ sơ, kết nối, hoạt
  động, dấu đã đọc và ghi nhớ.
- **Xóa tài khoản:** Cài đặt → Xóa tài khoản. Chúng tôi xóa dữ liệu riêng của bạn, kết thúc các
  hoạt động đang diễn ra và ẩn danh hóa tin nhắn của bạn trong các cuộc trò chuyện. Hồ sơ kiểm duyệt
  liên quan đến bạn được giữ 1 năm vì lý do an toàn.
- **Rút đồng ý:** tắt AI, MEM, MATCH hoặc VOICE bất cứ lúc nào trong Cài đặt; tắt MATCH sẽ gỡ hồ sơ
  khỏi gợi ý.
- **Chặn và báo cáo** người khác ngay trong cuộc trò chuyện.
- Các yêu cầu khác (chỉnh sửa, phản đối xử lý): _[email liên hệ — cần điền]_.

## 7. Độ tuổi

Tính năng kết nối chỉ dành cho người từ 18 tuổi (năm sinh tự khai và xác nhận đủ 18 tuổi trong năm
giáp ranh). Nếu bạn nghi ngờ ai đó chưa đủ tuổi, hãy báo cáo với lý do "Có thể chưa đủ 18 tuổi".

## 8. Kiểm duyệt

Nhân viên kiểm duyệt chỉ xem phần bằng chứng người báo cáo đã chọn, không thấy email hay mã người
dùng. Quyết định có thể là bỏ qua, cảnh báo, hạn chế kết nối hoặc tạm khóa tài khoản; mọi quyết định
đều được ghi lại. Mục tiêu xử lý báo cáo: trong 48 giờ.

## 9. Thay đổi thông báo này

Chúng tôi sẽ thông báo trong ứng dụng trước khi thay đổi cách dùng dữ liệu. Phiên bản: _nháp
2026-10-25_.
