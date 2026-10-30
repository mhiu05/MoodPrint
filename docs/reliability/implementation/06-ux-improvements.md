# UX

## Đã xem trên trình duyệt

Luồng được chạy bằng Playwright, dữ liệu giả:

- Mở trợ lý Mây, gõ bản nháp, rồi làm `GET /session` trả 503.
- Lần vào app đầu tiên khi session lỗi.
- Phiên hết hạn và tài khoản bị khóa.
- Focus, visibility và online cùng lúc.
- Hết ân hạn 30 giây.
- Toàn bộ `guest-expiry.spec.ts`.
- Banner ở bề rộng 390 px không làm trang tràn ngang.

Ảnh:

- Trước gián đoạn: [session-ready-desktop.png](screenshots/session-ready-desktop.png)
- Trong gián đoạn, desktop: [session-degraded-desktop.png](screenshots/session-degraded-desktop.png)
- Trong gián đoạn, 390 px: [session-degraded-mobile.png](screenshots/session-degraded-mobile.png)

Cuộc trò chuyện và ô nhập còn trên màn hình. Banner nằm phía trên, không che ô soạn tin. Nút gửi bị khóa khi `paused`. Hết 30 giây, chữ “câu chưa gửi” và tên trợ lý không còn.

## Chữ hiển thị

| Tình huống | Chữ |
|---|---|
| Đang thử lại | Kết nối đang gián đoạn. MoodPrint đang thử kết nối lại… |
| Đã xong | Đã kết nối lại. Bạn có thể tiếp tục. |
| Hết ân hạn | MoodPrint chưa thể kết nối. Bạn có thể thử lại sau ít phút. |
| Database đông | MoodPrint đang hơi đông. Bạn hãy thử lại sau ít giây. |
| Nhật ký chưa lưu | Phần đang viết vẫn ở trên màn hình và chưa được lưu. |

Mất mạng theo `navigator.onLine` vẫn dùng banner cũ “Bạn đang mất kết nối mạng”, không chồng thêm banner máy chủ.

Chưa rà lại từng màn hình đăng nhập, tìm bạn, hồ sơ và voice trong trình duyệt ở đợt này. Không đổi ngôn ngữ thương hiệu của landing.
