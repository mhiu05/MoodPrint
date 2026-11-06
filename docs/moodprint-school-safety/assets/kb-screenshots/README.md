# Ảnh mẫu cho hướng dẫn nền tảng

Chín ảnh trong thư mục này là **ảnh mẫu**. Chúng chỉ là khung xám, không có logo hay giao diện thật, và không mô tả đúng các bước trên app. Mỗi ảnh ghi việc cần chụp để thay bằng ảnh thật.

| File | Nền tảng | Việc | Cần chụp |
| --- | --- | --- | --- |
| `facebook-report.png` | Facebook | Báo cáo | Menu của bài viết hoặc bình luận, phần báo cáo |
| `facebook-block.png` | Facebook | Chặn | Trang cá nhân của người cần chặn, phần chặn |
| `facebook-evidence.png` | Facebook | Lưu bằng chứng | Bài viết hoặc tin nhắn thấy rõ thời gian và đường dẫn, đã che tên |
| `youtube-report.png` | YouTube | Báo cáo | Menu của video hoặc bình luận, phần báo cáo vi phạm |
| `youtube-block.png` | YouTube | Chặn | Trang kênh, phần chặn người dùng |
| `youtube-evidence.png` | YouTube | Lưu bằng chứng | Video hoặc bình luận thấy rõ thời gian và đường dẫn, đã che tên |
| `tiktok-report.png` | TikTok | Báo cáo | Menu chia sẻ của video, phần báo cáo |
| `tiktok-block.png` | TikTok | Chặn | Trang cá nhân của người cần chặn, phần chặn |
| `tiktok-evidence.png` | TikTok | Lưu bằng chứng | Video hoặc bình luận thấy rõ thời gian, đã che tên |

## Thay bằng ảnh thật

1. Chụp trên app thật, giao diện tiếng Việt, bằng tài khoản thử.
2. Che tên, ảnh đại diện, số điện thoại và nội dung của người khác. Repo công khai, nên ảnh commit vào đây ai cũng xem được.
3. Ghi đè đúng tên file, giữ định dạng PNG.

Không cần sửa `placeholders.json`. File này ghi SHA-256 của ảnh mẫu để `build.py` (WS-05-T16) nhận ra ảnh chưa được thay. Ảnh còn trùng hash sẽ bị bỏ qua, nên ảnh mẫu không bao giờ lên sản phẩm; thẻ vẫn hiện phần chữ.
