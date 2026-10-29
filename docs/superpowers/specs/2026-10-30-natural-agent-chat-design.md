# Thiết kế lại màn chat AI MoodPrint

Trạng thái: người dùng đã duyệt ngày 30/10/2026 và yêu cầu triển khai ngay.

## Ý định và lựa chọn đã xác nhận

Người dùng muốn chat gọn, tự nhiên như Grok Bot, dùng Thinking Orbs cho trạng thái làm việc và GSAP cho chuyển động cần thiết. Người dùng đã chọn **đổi toàn bộ diện mạo chat theo Grok**, thay vì chỉ tinh chỉnh giao diện xanh hiện tại.

Đây là thiết kế của MoodPrint lấy cảm hứng từ cách giao diện chat tối giản vận hành. Không khẳng định sao chép chính xác demo Grok: x.ai/bot chặn trình duyệt tự động bằng Cloudflare.

## Approaches

1. **Tinh gọn giao diện hiện tại:** giữ hệ màu xanh và bong bóng có viền, gom thao tác dừng vào nút gửi. Ít thay đổi hơn, nhưng vẫn giữ cảm giác nhiều khung và cách chia vùng hiện tại. Đã trình bày; người dùng không chọn.
2. **Thay diện mạo toàn màn chat:** nền trắng/trung tính, phản hồi agent không có khung bao, tin người dùng có nền xám nhẹ, ô nhập nổi gọn và một nút gửi/pause. Có nhiều thay đổi về bố cục và cần kiểm tra lại trạng thái/điều khiển. **Người dùng đã chọn hướng này.**

## Mục tiêu

- Đọc hội thoại liên tục, giảm khung/viền, khoảng trống và thao tác lặp.
- Một vị trí cố định cho thao tác chính: gửi khi rảnh, yêu cầu dừng khi đang chạy.
- Orb gắn với phản hồi sắp xuất hiện, không thành một thanh công cụ riêng trên ô nhập.
- Giao diện hợp lý trên điện thoại 360–390px, chiều rộng ảnh tham chiếu 666px và desktop.
- Giữ đúng hành vi gửi, hủy, lịch sử, sao chép, thời gian, giọng nói, đề xuất và thông tin cuộc trò chuyện.

## Phạm vi và ràng buộc

Chỉ các route chat AI /assistants/:botId và những component phục vụ chúng. Không thay landing page, chat người thật, backend, API, cơ chế lưu lịch sử hoặc session reliability. Không sửa .gitignore. Giữ toàn bộ thay đổi chưa commit sẵn có, đặc biệt metadata/ngày giờ tin nhắn trong RealApp.tsx, me2we.css và ux-redesign.spec.ts.

Không thêm chức năng pause/resume giả: icon pause biểu diễn thao tác **Dừng phản hồi** đang có, không hứa tiếp tục cùng một phản hồi. Tên truy cập và tooltip dùng đúng hành vi này.

## Hướng thị giác đề xuất

Các giá trị dưới đây do người triển khai đề xuất, chưa phải thông số do người dùng yêu cầu.

- Chế độ: Operate. Trọng tâm là viết và đọc, không thêm trang trí hoặc animation liên tục ngoài orb.
- Nền chat trắng; chữ than đậm, chữ phụ xám trung tính; màu xanh chỉ dùng cho liên kết/ngữ nghĩa cần nhận diện MoodPrint.
- Dùng font hệ thống hiện tại, nội dung 16px, line-height khoảng 1.65; hỗ trợ tiếng Việt và zoom.
- Cột nội dung/ô nhập chung trục và cùng chiều rộng đọc khoảng 720px trên desktop; lề 16–20px trên phone.
- Header nhẹ hơn: avatar khoảng 32–36px, tên + nhãn AI nhỏ, vai trò/lưu trữ là dòng phụ; back/info giữ vùng chạm 44px.
- Bot trả lời trực tiếp trên nền, không bong bóng có viền. Tin người dùng có nền xám nhạt, bo góc mềm, chiều rộng theo nội dung và tối đa khoảng 85% cột đọc.
- Thẻ điều hướng là liên kết gọn có icon mũi tên, không tạo thêm khung lớn quanh một liên kết đơn.
- Metadata/sao chép vẫn hiện qua hover, focus và chạm. Giữ chỗ metadata để không làm tin nhắn nhảy khi hiện.
- Lời giới thiệu và gợi ý mở đầu chỉ chiếm trọng tâm lúc chưa có tin nhắn; khi có hội thoại, ưu tiên transcript. Nội dung hướng dẫn đã có vẫn giữ trong trạng thái khởi đầu và các lối truy cập liên quan.

## Ô nhập và hành vi nút chính

Ô nhập nền xám rất nhẹ, viền mảnh, bo khoảng 24px; focus ring gọn, tương phản rõ. Textarea vẫn nhiều dòng, không làm mất nháp, Enter gửi và Shift+Enter xuống dòng, không gửi khi IME đang compose. Mic nằm cạnh nút chính, không thành nút lớn cạnh tranh.

| Trạng thái | Nút chính | Hành vi |
|---|---|---|
| Rảnh, nháp trống | Icon gửi mờ, disabled | Không có request |
| Rảnh, có nháp hợp lệ | Icon mũi tên lên | Gửi tin, như hiện tại |
| Đang submit, chưa có accepted run | Icon gửi disabled | Không thể hủy run chưa được xác nhận, không gửi lặp |
| Run đang hoạt động, có quyền hủy | Icon pause, enabled | Yêu cầu dừng; type=button, không submit form |
| Đang yêu cầu dừng | Icon pause disabled | Không gửi thêm yêu cầu hủy |
| Đang đối soát/refresh transcript | Nút disabled | Không hủy/gửi khi chưa biết trạng thái |
| Hoàn tất hoặc đã hủy được xác nhận | Trở lại icon gửi | Nháp người dùng đang gõ được giữ nguyên |

Nút pause không phụ thuộc việc nháp có chữ hay không. Nếu composer bị ẩn vì trạng thái read-only trong khi vẫn còn run có thể hủy, vẫn phải có nút icon dừng truy cập được bên cạnh trạng thái hoạt động; không bao giờ hiển thị hai nút dừng.

Nhãn truy cập: Gửi tin cho AI / Dừng phản hồi / Đang yêu cầu dừng. Có tooltip cho nút icon. Dùng cùng DOM button khi đổi trạng thái để tránh mất vị trí focus.

## Trạng thái agent

- AIActivityStatus đặt ở cuối transcript, thẳng hàng với phản hồi bot, trước lỗi/notice cuối luồng khi phù hợp; không còn hàng có viền riêng trên composer.
- Một vùng role=status được mount ổn định, không đặt toàn transcript aria-busy vì có thể trì hoãn việc đọc tin mới. Tránh live announcement trùng lặp giữa log và status bằng ngữ nghĩa ARIA phù hợp.
- Dùng ThinkingOrb working 20px chỉ khi accepted run có đủ identity. Không tự diễn giải thành đang tìm kiếm/đang suy luận nếu server không phát trạng thái đó.
- Có thể rút gọn nhãn accepted thành “Đang trả lời…”; các nhãn gửi, yêu cầu dừng, đối soát vẫn chính xác.
- Khi dừng, chỉ báo đã dừng sau terminal event. Nếu bot hoàn tất trước yêu cầu hủy, vẫn hiện phản hồi hoàn tất.
- Khi run kết thúc, bỏ orb ngay và hiển thị nội dung thực; không chờ animation.
- Giữ fallback icon khi chunk/canvas lỗi, reduced-motion hoặc tab ẩn; không để animation tác động request.
- Giữ một thông báo hủy rõ ràng, tránh lặp cả một hàng trạng thái và một dòng dưới tin cho cùng lượt đã hủy nếu có thể xác định an toàn.

## Chuyển động

Tận dụng GSAP và @gsap/react đã cài sẵn. Dùng một chuyển động xuất hiện nhẹ cho trạng thái làm việc (opacity/translate 2–4px, khoảng 160ms), và phản hồi CSS ngắn cho hover/press của nút. Không animate chiều cao transcript, từng token hoặc auto-scroll bằng timeline. Cleanup khi identity/route thay đổi; prefers-reduced-motion bỏ chuyển động không cần thiết; tab ẩn dừng orb.

## Trạng thái cần giữ dùng được

- Empty, có lịch sử, nhiều tin nhắn, tin dài/markdown, card điều hướng.
- Đang gửi, accepted, hủy, hủy lỗi, phản hồi thắng race với hủy, đối soát, service unavailable.
- Draft đang nhập trong khi agent chạy, mic/voice transcript, nháp nhiều dòng, IME.
- Scroll lên đọc tin cũ và nút về tin mới; không cưỡng ép người dùng xuống cuối khi đang đọc.
- Read-only, guest quota, thử lại lỗi; thông tin cuộc trò chuyện và xác nhận mở mới không mất tác dụng.
- Hover/focus/touch metadata, bàn phím, giảm chuyển động và mất chunk orb.

## Kiểm chứng

- Viết/chỉnh regression browser test cho nút chính đổi gửi/pause, nháp trống khi run hoạt động, không submit khi pause, hủy một lần và đợi server xác nhận.
- Chạy các test hiện có cho AI activity, conversation info, message metadata, voice và motion liên quan; giữ các assertion hành vi của thay đổi sẵn có.
- Frontend unit tests, typecheck và build.
- Chụp và xem UI synthetic data ở desktop, 390px và 666px: empty, có hội thoại, accepted, dừng, dài/nhiều dòng; kiểm tra overflow, vùng chạm tối thiểu 44px và focus.
- Không chạy backend/model thật hay ghi production để kiểm tra UI.

## Những quyết định giao cho người triển khai

Tinh chỉnh sắc độ trung tính, kích thước trong các khoảng trên và thời lượng chuyển động; cách chia component nhỏ nếu giúp kiểm thử; quy trình fixture để xem UI. Không tự thêm model picker, upload, search, regenerate, resume hoặc các tính năng không có trong sản phẩm.

## Nguồn

- https://x.ai/bot
- https://github.com/Jakubantalik/thinking-orbs
- https://github.com/pbakaus/impeccable
- https://github.com/greensock/gsap
