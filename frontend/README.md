# Me2We

**Understand Yourself. Find Your People.**

Prototype React + Vite + TypeScript, thiết kế mobile-first. Mở ứng dụng vào danh sách năm trợ lý AI; không đăng nhập, onboarding hoặc nhập tuổi. Nội dung soạn sẵn và nhân vật hư cấu, mọi thay đổi chỉ ở RAM. Không có backend, LLM, microphone hay lưu trữ nội dung riêng tư.

## Chạy local

```powershell
cd D:\uomTao\startup\prototype
npm.cmd install
npm.cmd run dev
```

Mở **http://127.0.0.1:5173/**. Ứng dụng không tải font, ảnh hoặc thư viện từ CDN khi chạy.

```powershell
npm.cmd run typecheck
npm.cmd test
npm.cmd run build
npm.cmd run preview
```

Preview production: **http://127.0.0.1:4173/**.

## Trải nghiệm các bot

- **Mây:** chọn “Hôm nay mình hơi mệt” → “Kể một chút” → “Ghi lại cảm xúc”. Chỉ khi bạn chọn mới mở Nhịp; không chuyển transcript.
- **Gương:** “Mình thích đọc sách” → “Mình thích khoảng yên tĩnh khi đọc sách” → lưu, sửa hoặc bỏ qua nhận xét. Chỉ lưu vào hồ sơ riêng, không tự ghi nhớ hoặc chia sẻ.
- **Nhịp:** chọn cảm xúc ngay trong chat → “Xem xu hướng”. Biểu đồ tính từ những ngày đã tự ghi; ngày thiếu được giữ trống. Có thể xem chi tiết, sửa và xóa ghi nhận.
- **Rủ Rê:** “Giải đố” → đoán → “Xem đáp án”; hoặc “Học gì đó” → xem câu ví dụ.
- **Cầu Nối:** chọn mục tiêu → “Xem người phù hợp” hoặc sửa hồ sơ kết nối. Không tự gửi lời mời.

Chuyển bot rồi quay lại để tiếp tục hội thoại. Phản hồi đang chờ được gắn với bot gốc, không hiện trong thread khác. Lịch sử, preview và trạng thái tin mới dùng cùng kho dữ liệu phiên.

## Tìm bạn và cùng chơi

Bốn tab: **Trợ lý · Tìm bạn · Tin nhắn · Tôi**.

Tìm bạn → Làm quen → phản hồi mẫu “Đồng ý” → Mở trò chuyện. Composer chỉ xuất hiện khi domain xác nhận cả hai đã đồng ý. Tên và nhận diện chat người dùng tách khỏi bot AI.

Trong chat: **Cùng làm gì đó? → Câu hỏi làm quen → Mời cùng tham gia → Đồng ý hoạt động**. ACT01 có ba câu hỏi, trả lời/bỏ qua, phản hồi đối phương, tiến trình và hoàn thành. Back/Escape khi đang chơi cần chọn ở lại hoặc dừng. Học cùng nhau, Luyện tiếng Anh, Trò chơi nhỏ là bản xem trước.

Tôi → Hồ sơ kết nối → chọn thông tin → Xem trước → Cho phép chia sẻ. Mood, chat và nhận xét riêng không dùng để tự matching. Điểm chuẩn vẫn được kiểm tra trong unit tests: Mầm Xanh 90, Lá Non 78, Nắng Mai 68, Suối Nhỏ 44; UI thể hiện điểm chung thay cho điểm số.

Tùy chọn chat cho phép kết thúc hoặc chặn. Chia sẻ từng thông tin có xem trước, từ chối, thu hồi theo trường và theo chiều. Tắt MATCH, ngừng chia sẻ hoặc sửa nguồn đã liên kết đóng những dẫn xuất liên quan; bật lại không hồi sinh phòng cũ.

## Reset và giới hạn

**Tôi → Cài đặt và quyền riêng tư → Đặt lại bản trải nghiệm → Đặt lại toàn bộ**, hoặc tải lại trang. Reset tăng epoch, hủy job cũ và nạp lại dữ liệu mẫu. Không ghi localStorage, sessionStorage, cookie hoặc IndexedDB.

Thông báo ngắn xuất hiện lần đầu trong phiên. Có thể xem lại ở **Cài đặt → Về Me2We** hoặc thông tin từng bot.

`mocks/demo.ts` nạp nhân vật người trưởng thành hư cấu qua các action domain hiện có. `initialState()` vẫn fail-closed: tuổi unknown, mọi quyền tắt. Không triển khai memory dài hạn, delegation hoặc reasoning thật. Những cờ cho phép dùng lại chỉ là trạng thái quyền trong phiên mẫu.

Chỉ Vite development hỗ trợ query ngoài hash:

- `/?fixture=fresh&ai=off&mem=off&tools=1`: adult chưa chia sẻ, AI tắt.
- `/?fixture=teen&tools=1`: 16–17; chỉ soạn/xem nháp, không publish, matching hoặc chat người lạ.
- `/?fixture=unknown` hoặc `/?fixture=under16`: chặn phiên.
- `&tools=1`: công cụ kiểm thử nội bộ; không có trong bản production.

Query trong hash không đổi nhóm tuổi. Production bỏ qua harness. Quyền và kiểm tra tuổi trong domain được giữ nguyên.

## Kiểm thử và ảnh

```powershell
$env:PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH='C:/Users/minhh/AppData/Local/ms-playwright/chromium-1243/chrome-win64/chrome.exe'
npm.cmd run test:e2e
# Dev server đang chạy:
node tests/screenshots.mjs final
# Preview production ở 4173 đang chạy:
node tests/production-smoke.mjs
```

- [Báo cáo triển khai](IMPLEMENTATION-REPORT.md)
- [Kết quả tổng hợp](evidence/verification.json)
- [E2E Chromium](evidence/e2e-results.json)
- [Production smoke](evidence/production-smoke.json)
- [Ảnh cuối](evidence/me2we/round-final/manifest.json)

Ảnh trong `evidence/me2we/round-1`, `round-2`, `round-final` ghi lại các vòng kiểm tra trực tiếp bằng Chromium. Những ảnh `redesign-*`, `S*` trước đó là lịch sử của giao diện cũ.

## Cấu trúc

`companions/registry.ts`: contract, danh tính và starter prompts. `companions/scenarios.ts`: phản hồi soạn sẵn theo vai trò. `companions/Companions.tsx`: roster và shared chat. `companions/Cards.tsx`: mood, insight, gợi ý hồ sơ, hoạt động và điều hướng. `companions/Avatar.tsx`: bộ SVG tự dựng.

`State.bots` giữ các thread trong reducer hiện có; scheduler dùng job ID, epoch và phiên bản quyền để kiểm tra callback. Domain matching, mutual consent, reveal và ACT01 tiếp tục dùng reducer/policies hiện có. GSAP + @gsap/react có scope, cleanup và phản hồi khi người dùng đổi reduced motion.

Chỉ thay đổi trong `prototype/`; không sửa `.gitignore`, `documents/`, Charter, README/LICENSE gốc. Không commit, push, deploy public hay thay đổi database.
