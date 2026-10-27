# UI, responsive và accessibility

## CSS và component ownership

`main.tsx` nạp [tokens.css](../../frontend/src/styles/tokens.css), [global.css](../../frontend/src/styles/global.css), [me2we.css](../../frontend/src/styles/me2we.css); `RealApp` nạp [real.css](../../frontend/src/features/real/real.css). Social/activity có stylesheet riêng. Các biến color/type/spacing/radius/control/motion nên lấy từ tokens khi thay đổi thành phần dùng chung.

[UI.tsx](../../frontend/src/components/UI.tsx) là nơi duy trì Button, Dialog, StatePanel và primitives đang dùng. Production guard phát hiện export dư và import code giả lập cũ; thêm primitive cần có nơi sử dụng thực tế.

## Responsive

Shell có navigation và vùng nội dung; conversation pane chứa log và composer. Activity dock là side panel trên desktop, sheet ở phía trên composer trên phone. Đổi dock không được làm mất draft hoặc che send controls. Composer dùng flex-wrap để voice controls và textarea còn dùng được ở chiều rộng hẹp; textarea có `min-width: 0`.

Khi sửa layout, kiểm tra ít nhất desktop, phone 390px và phóng đại text 200% trong các flow có test tương ứng. Đo overflow sau khi resource/transition ổn định. Screenshot đẹp ở một viewport không đủ để khẳng định responsive.

## Keyboard và trợ năng

- Control có label cụ thể; icon trang trí `aria-hidden`. Nút micro hiện tại có accessible name `Ghi âm`.
- Focus ring luôn nhìn thấy. Dialog cần quản lý initial focus, tab containment, Escape và trả focus về trigger khi đóng.
- [useRouteFocus](../../frontend/src/features/real/useRouteFocus.ts) cùng [focusHeading](../../frontend/src/components/focusHeading.ts) hỗ trợ focus khi đổi màn hình; route transition không được đặt focus vào vùng đang ẩn.
- Trạng thái chờ/lỗi dùng semantics phù hợp (`role=status`, error notice); không liên tục đọc lại toàn bộ chat khi nhận message.
- Không dùng chỉ màu để thể hiện đáp án đúng/sai hoặc trạng thái hoạt động. Quiz có text và trạng thái rõ ràng.
- Giữ contrast, target size và reading order khi text wrap. Auto-scroll không kéo người đang đọc tin cũ xuống cuối một cách bất ngờ.

## Motion

[useMotionPolicy](../../frontend/src/components/motion/useMotionPolicy.ts) tập trung reduced-motion policy. Animation không quyết định business state và không che nội dung trong lúc chờ API. Orb AI được lazy load; `ThinkingOrbVisual` là presentation, không phải bằng chứng provider đã xử lý thành công.

Kiểm tra reduced motion cho dialog/dock/thinking states; animation kết thúc phải cleanup khi unmount. Đừng dùng opacity của toàn panel làm text mất đọc được trong transition.

## Voice

[Voice.tsx](../../frontend/src/features/real/Voice.tsx) chỉ yêu cầu micro sau thao tác chủ động; ghi âm có giới hạn 30 giây và gửi backend để transcribe. Browser permission, feature flag và VOICE/AI consent là các gate riêng. Âm thanh không phải message đã gửi; text phải được xem/sửa/chọn đưa vào composer. Xem [voice backend](../../backend/app/modules/voice/routes.py) trước khi sửa format audio hoặc giới hạn body.

## Cách xác minh

Các spec `activities`, `motion`, `ux-redesign`, `merge-readiness`, `states`, `auth` kiểm tra geometry/focus/keyboard/loading/error/empty. Axe checks hỗ trợ phát hiện vi phạm nhưng không thay thế kiểm tra thủ công bằng keyboard và đọc nội dung. Mọi kết luận PASS cần kết quả chạy cụ thể trong [verification](../verification.md).
