# MoodPrint — Mobile-first Design System & UX Writing

> 07/11/2026 • Tên hệ thống: **MoodPrint UI** • Đây là **đặc tả**, chưa triển khai CSS/components. Thiết kế cho học sinh 11–17 tuổi, tiếng Việt mặc định, mobile web trước.

## 1. Design principles

1. **Calm first:** bình tĩnh, tin cậy, không màu sắc/hình ảnh kích thích căng thẳng hoặc hù dọa.
2. **Choice over pressure:** người dùng luôn được chọn kể tiếp, để sau, lưu nháp, tìm hỗ trợ; không giao nhiệm vụ ép buộc.
3. **Explain uncertainty:** hiển thị điều AI quan sát, điều AI suy đoán và điều chưa rõ dưới dạng khác nhau.
4. **One primary action:** mỗi màn hình có một CTA chính (chỉ hai CTA trong quyết định xác nhận).
5. **Mobile ergonomics:** thao tác 1 tay, mục tiêu chạm rộng, form ít trường một bước, nội dung có thể ngắt quãng.
6. **Truthful demo:** trạng thái mock/AI/voice/trường học giả được đánh nhãn rõ, không để người dùng ngộ nhận.
7. **Age-aware without infantilizing:** không dùng hình vẽ quá trẻ con; giọng gần gũi, không lên lớp; tránh ngôn ngữ hàn lâm.

## 2. Visual direction

**Định hướng:** Warm & quiet modern school wellbeing; tránh màu đỏ cảnh báo làm màu chủ đạo, tránh illustration mô tả cảnh đánh nhau/bắt nạt trực diện. Hình minh họa ưu tiên bàn học, sách, không gian trường học trung tính hoặc abstract shapes. Hình avatar AI mang cảm giác gần gũi nhưng **không hóa thân thành giáo viên/chuyên gia thật**.

**Logo MoodPrint:** wordmark chữ gọn; icon có thể kết hợp dấu thoại + nét bút/nhật ký. Không tái sử dụng biểu tượng cũ nếu gây lẫn chủ đề cảm xúc-only; vẫn giữ tên thương hiệu.

### Palette đề xuất (chưa coi là brand chính thức)

| Token | Hex | Mục đích | Quy tắc |
|---|---|---|---|
| `ink.strong` | `#183B37` | Heading/primary text | Trên nền trắng và ngà |
| `ink.default` | `#274B46` | Body text | Độ tương phản cao |
| `ink.muted` | `#506C66` | Secondary text | Không dùng cho helper quá nhỏ nếu thiếu tương phản |
| `bg.page` | `#F6FAF8` | App background | Trung tính mát, không xanh quá đậm |
| `bg.surface` | `#FFFFFF` | Cards/forms | Kết hợp border |
| `bg.subtle` | `#EAF3EF` | Highlight nhẹ | Không thay thế border/focus |
| `brand.primary` | `#126A61` | Primary button, active tab | Chữ trắng, contrast cần test |
| `brand.deep` | `#0E514B` | Hover/active dark | Chữ trắng |
| `brand.soft` | `#DDF1EB` | Chip/tinted card | Text `ink.strong` |
| `accent.lavender` | `#EBE7FB` | Learning/roleplay accent | Không dùng làm chữ |
| `border.default` | `#CCDDD7` | Card/input line | Đủ nhận diện trên bg |
| `status.info` | `#315D8D` | Info/link | Có icon/label |
| `status.warning` | `#8C5600` | Need review/caution | Đi kèm nội dung text |
| `status.danger` | `#B42318` | Urgent/error | Chỉ xuất hiện nơi cần chú ý |
| `focus.ring` | `#3C78B2` | Keyboard focus | Viền 3px + offset |

**Lưu ý:** bảng là ý định thiết kế, không phải chứng nhận WCAG. Khi implement phải đo contrast của từng tổ hợp chữ/nền, nhất là text thứ cấp và badge nhỏ.

### Semantic roles

- **Primary:** tiếp tục, lưu hồ sơ, bắt đầu luyện, tìm hỗ trợ.
- **Secondary:** xem thêm, lưu nháp, mở nguồn.
- **Tertiary/ghost:** bỏ qua, quay lại, đổi nguồn.
- **Critical:** xóa hồ sơ, khôi phục dữ liệu demo; có xác nhận và không đặt sát CTA primary.
- **Uncertainty:** icon `?`/`alert-circle` + chữ `Cần xác minh`; không tự đổi thành danger đỏ.

## 3. Typography tiếng Việt

**Font định hướng:** `Be Vietnam Pro` hoặc hệ thống sans hỗ trợ dấu tiếng Việt tốt; fallback `Inter`, `Arial`, system-ui. Không kèm font binary trong artifact. Line-height ưu tiên thoáng để đọc trên mobile.

| Role | Mobile px / line-height | Desktop px / line-height | Weight | Ví dụ |
|---|---|---|---|---|
| Display | 28 / 36 | 36 / 44 | 700 | “Bạn muốn bắt đầu từ đâu?” |
| H1 | 24 / 32 | 30 / 38 | 700 | Màn AI, Hồ sơ |
| H2 | 20 / 28 | 24 / 32 | 650/700 | Phòng luyện nói |
| H3 | 17 / 24 | 20 / 28 | 600 | Thẻ tính năng |
| Body | 16 / 25 | 16 / 26 | 400 | Bài Knowledge |
| Body compact | 14 / 22 | 14 / 22 | 400 | Form helper/chip |
| Label | 14 / 20 | 14 / 20 | 600 | Trường input |
| Caption | 12 / 18 | 12 / 18 | 400 | Source, metadata |
| Button | 15 / 22 | 15 / 22 | 600 | CTA |

Không dùng chữ dưới 12px cho nội dung phải đọc; không render đoạn văn dài bằng weight quá mảnh; tránh viết HOA toàn phần với các đoạn dành cho học sinh.

## 4. Spacing, sizing, radii

- Spacing scale: `4, 8, 12, 16, 20, 24, 32, 40, 48, 64` px.
- Horizontal padding mobile: **16px** trên 320–430; tablet 24px; desktop content tự căn giữa.
- Content max-width: article 720px; forms 640px; dashboard 1160px; chat stream 760px.
- Grid: mobile 1 column; feature quick actions 2 cols ở ≥360px nếu mỗi item đủ rộng; tại 320px có thể stack 1 cột nếu text wrap xấu.
- Cards: radius 16px, inner padding 16px, gap 12–16px, border 1px; shadow rất nhẹ khi cần phân tầng.
- Buttons/inputs: minimum height 44px; primary CTA 48–52px; touch target ≥44×44px; icon button có aria-label.
- Bottom nav: 64–72px + `safe-area-inset-bottom`; không che nội dung/footer/keyboard.
- Modal: full-width bottom sheet trên mobile, dialog max-width 480px trên desktop; hỗ trợ scroll riêng và visible close.
- Progress stepper: số bước rõ (ví dụ Bước 2/6), progress bar đi kèm tên bước.

## 5. Layout composition

### Home mobile

1. Header: logo/wordmark trái; profile/help bên phải.
2. Hero: lời mở + CTA Chat.
3. Quick action grid: Ghi lại sự việc / Luyện nói / Tìm hỗ trợ / Học qua ví dụ.
4. Recent Case: tối đa 2 thẻ, `Xem tất cả`.
5. Next step widget: kế hoạch/checklist nếu có.
6. Knowledge picks: 2 bài học.
7. Bottom nav 4 tab cố định.

**Tránh:** biểu đồ thống kê toàn trường dày đặc, tin giả “Trường bạn có 27 vụ”, lộ thông tin người khác. Nếu muốn kể về bạo lực học đường trong Home, sử dụng thẻ kiến thức có nguồn hoặc preview Admin Demo độc lập.

### Chat mobile

- Header: `AI Companion` + trạng thái `Mô phỏng` + help shortcut.
- Messages xếp dọc, bóng thoại AI đủ rộng, không lạm dụng avatar mỗi dòng.
- Attachment card là thumbnail + tên file + source state; không bắt user mở modal mới để xem warning.
- Quick replies đặt trên composer, có horizontal scroll *chỉ cho chips*.
- Composer sticky phía trên bàn phím; textarea auto-grow tối đa 5 dòng, icon attach, Send rõ trạng thái.
- Khi AI trả phân tích, dùng 4 card nhỏ: `Điều đã kể`, `Dấu hiệu`, `Chưa rõ`, `Gợi ý`.

### Incident mobile

- Card list: tên trung tính, loại, cập nhật, trạng thái, một dòng mô tả; không hiển thị tên người liên quan trên danh sách.
- Detail: tabs/segmented `Tổng quan`, `Dòng thời gian`, `Bằng chứng`, `Bước tiếp theo` với horizontal overflow có indicator nếu cần.
- Evidence viewer: thumbnail, metadata, `Trích từ ảnh mẫu`, `Người dùng xác nhận`, `Chưa xác minh`, no fabricated OCR confidence number.

### Roleplay mobile

- Setup: avatar/role abstract illustration, mục tiêu, mức độ, lựa chọn Text/Voice demo.
- In-session: active role header, transcript visible, large record/send-like demo control (nhãn rõ), pause/stop, progress.
- Feedback: không dùng điểm 0–100, xếp theo `Đã làm rõ / Có thể bổ sung / Câu gợi ý`.

### Support mobile

- Hierarchy: `Cần hỗ trợ ngay` có nhận diện rõ; `Tìm người giúp` / `Học cách xử lý` / `Soạn tin nhắn`.
- Information density thấp; cảnh báo ra ngoài app mở liên kết rõ.
- Alias selector có giải thích 1 câu, popup đọc thêm, không mặc định là ẩn danh tuyệt đối.

## 6. Component specification

| Component | Props/variants thiết kế | Tương tác | Error/empty/accessibility |
|---|---|---|---|
| `Button` | primary, secondary, ghost, danger, loading | onClick/keyboard | disable thật khi không thể thực hiện; loading + aria-live |
| `TextField` | label, hint, counter, required, multiline | focus/change/blur | lỗi cạnh trường, không chỉ toast |
| `BottomNav` | 4 items, active, icon/label | nav links | label luôn hiển thị; safe area |
| `FeatureCard` | icon, title, description, action | single click target | không lồng button trong button |
| `CaseCard` | status, type, lastActivity, preview | open | ẩn thông tin nhạy cảm trên list |
| `StatusPill` | draft/active/monitoring/closed/demo | đọc trạng thái | icon/word đi kèm màu |
| `EvidenceTile` | media, provenance, timePrecision | preview/verify | alt text hoặc label mô tả |
| `ChatBubble` | user/AI/system, sources, actions | copy/expand | source được liên kết nếu có |
| `AnalysisSection` | observed/inferred/unknown/suggested | accordion | không biến inference thành fact |
| `TimelineItem` | date, precision, provenance | view evidence | thứ tự chronologically coherent |
| `RoleplayControls` | text/voice demo, pause, stop, retry | state transitions | nhãn Voice demo, no microphone capture |
| `KnowledgeCard` | category, age, readTime, source | open/save | tag nguồn, thời gian rà soát |
| `QuizChoice` | selected, feedback, explanation | choose | không chấm điểm con người |
| `SupportComposer` | recipient, identityMode, caseLink | preview/copy | marker draft, no real send |
| `UrgentHelpCard` | source, phone, website | `tel:`/external | không cần account/AI gate |
| `SchoolDemoBanner` | fixed | always visible | trong chart tooltip cũng ghi demo |
| `Toast` | success/info/error | auto-dismiss after accessible duration | quan trọng dùng inline + focus management |

## 7. Iconography & imagery

- Sử dụng bộ icon nét đều (Lucide có thể là nguồn tham chiếu); icon mang nghĩa rõ: Chat, Folder, Mic, Book, Hand-heart, Phone, Shield.
- Không dùng ảnh thật của trẻ bị thương, khóc hoặc đang bị hành hung để trang trí.
- Persona illustrations giả lập không gợi ra danh tính của người thật.
- Nếu dùng ảnh minh họa từ nguồn ngoài, ghi credit/giấy phép và bản lưu trong asset manifest; ưu tiên vector tự thiết kế/ảnh đã có quyền.
- Ảnh chụp tin nhắn mock: dùng tên người gửi tổng hợp, không sao chép ảnh/tin nhắn cá nhân trên Facebook/TikTok.

## 8. Microcopy library

| Ngữ cảnh | Nên dùng | Tránh |
|---|---|---|
| Home | “Bạn muốn bắt đầu từ đâu?” | “Hãy báo cáo ngay!” |
| Chat | “Bạn có thể kể từng chút một.” | “Mình hiểu chính xác bạn đang trải qua.” |
| Phân tích | “Có một số dấu hiệu đáng chú ý, nhưng mình cần hỏi thêm.” | “Xác nhận đây là bắt nạt.” |
| OCR fixture | “Kiểm tra lại nội dung nhận diện từ ảnh mẫu.” | “Bằng chứng đã được xác thực.” |
| Case | “Lưu để xem lại khi bạn cần.” | “Hồ sơ bằng chứng pháp lý.” |
| Roleplay | “Hãy thử nói theo cách của bạn; bạn có thể làm lại.” | “Bạn trả lời sai.” |
| Support | “Bạn muốn chuẩn bị lời nhắn cho ai?” | “AI sẽ giải quyết với nhà trường.” |
| Bí danh | “Tên hiển thị trong bản nháp: [Bí danh]” | “Hoàn toàn ẩn danh.” |
| School Demo | “Dữ liệu giả lập. Chưa kết nối trường học.” | “Đang xử lý yêu cầu của bạn.” |
| Help now | “Nếu bạn đang không an toàn, hãy tìm người lớn đáng tin cậy hoặc liên hệ dịch vụ hỗ trợ.” | “Hãy chat tiếp để AI xác định trước.” |

## 9. UX states và emotional pacing

- **Empty:** mời hành động nhỏ, không tạo cảm giác hụt hẫng “Bạn chưa làm gì”.
- **Loading mock:** ≤1–1,5s cho cảm giác chuyển màn, có skip/reduced-motion; không cố làm giả “AI suy nghĩ thật”.
- **Error:** mô tả điều gì chưa hoàn tất và nút sửa/thử lại; giữ draft.
- **Success:** nói rõ hành động vừa xảy ra (`Đã lưu bản nháp`, `Đã thêm mốc`) thay vì thông báo mơ hồ `Thành công`.
- **Warning:** ít dùng; giải thích khi có mục `Không chắc chắn`; không dùng cảnh báo đỏ chỉ vì cảm xúc buồn.
- **Urgent:** tone ngắn và bình tĩnh, link hỗ trợ xuất hiện ngay; không đặt bước dài trước.

## 10. Motion, sound, haptics (web)

- Motion 120–180ms cho nhấn/chuyển trạng thái; 220–300ms cho panel/drawer; tắt với `prefers-reduced-motion`.
- Không tự phát âm thanh voice demo hoặc TTS mock khi mở màn; chỉ phát khi người dùng chọn.
- Không sử dụng animated “thinking orbs” liên tục khiến người dùng tưởng mô hình đang thực thi lệnh thật; nếu dùng, có nhãn demo.
- Tránh confetti/gameification cho sự việc bắt nạt; checklist completion chỉ phản hồi tinh tế.

## 11. Accessibility & inclusive design checklist

- [ ] Target chạm 44×44px; touch spacing đủ tránh bấm nhầm.
- [ ] Body 16px, không ép zoom; contrast văn bản thường đạt WCAG AA trên từng cặp màu.
- [ ] Focus indicator rõ và giữ focus sau dialog/toast.
- [ ] Input có visible labels, helper, error message gắn với input.
- [ ] Không chỉ dùng màu để phân biệt status/source/certainty.
- [ ] Screen reader đọc transcript ai/user theo thứ tự; tránh auto-announce toàn bộ chat dài.
- [ ] `Escape` đóng overlay nhưng không làm mất draft nếu chưa xác nhận.
- [ ] Cung cấp text alternative cho voice demo và nội dung hình ảnh.
- [ ] Responsive 320px không horizontal overflow (ngoại trừ chips/timeline có chủ ý và indicator).
- [ ] Tắt animation theo reduced-motion; trạng thái loading có text.
- [ ] Ngôn ngữ `vi-VN`, ngày tháng dd/mm/yyyy, giờ 24h, timezone phù hợp.
- [ ] Bài Knowledge có mục lục ngắn, chia heading rõ, không text wall.

## 12. Thiết kế màn School Admin Demo

- **Khác brand shell:** vẫn cùng màu/typography nhưng toolbar, banner `DEMO CHO NHÀ TRƯỜNG` và logo phụ.
- **KPI có qualifier:** “31 báo cáo *mẫu*”, “7 yêu cầu *mô phỏng đang xem xét*”, “2,4 ngày *dữ liệu giả lập*”. Đây chỉ là con số thiết kế, không phải dữ liệu về bất kỳ trường thật nào.
- **Charts:** bar theo category và line theo tuần, có table text alternative; không gán “trường bạn” hoặc địa danh có thật.
- **Drill-down:** synthetic IDs, không cho tra từ student data; fake role/department generic.
- **Charts trên mobile:** card 1 cột + list summary, không cắt nhãn trục để tiết kiệm chỗ.

## 13. UI QA checklist theo viewport

| Màn | 320 | 375/390 | 430 | 768 | 1440 | Điều kiện bắt buộc |
|---|---:|---:|---:|---:|---:|---|
| Onboarding | ✓ | ✓ | ✓ | ✓ | ✓ | CTA/Skip luôn thấy |
| Home | ✓ | ✓ | ✓ | ✓ | ✓ | 4 nav không chồng nhau |
| AI chat | ✓ | ✓ | ✓ | ✓ | ✓ | composer không bị bàn phím che |
| OCR analysis | ✓ | ✓ | ✓ | ✓ | ✓ | ảnh/text/timeline đọc được |
| Case wizard | ✓ | ✓ | ✓ | ✓ | ✓ | không mất draft |
| Roleplay | ✓ | ✓ | ✓ | ✓ | ✓ | pause/stop có label |
| Knowledge | ✓ | ✓ | ✓ | ✓ | ✓ | bài dễ đọc |
| Support | ✓ | ✓ | ✓ | ✓ | ✓ | 111 dễ tìm |
| Admin demo | ✓ | ✓ | ✓ | ✓ | ✓ | badge demo trên mọi view |

## 14. Hand-off sản phẩm → UI implementation

Mỗi màn hình phải có: (1) screenshot/wireframe, (2) route, (3) component map, (4) trạng thái normal/empty/loading/error, (5) event/state changes, (6) accessibility notes, (7) fixture IDs, (8) QA checklist. Không được code riêng từng màn với mock dữ liệu khác nguồn. Tham chiếu `03-INFORMATION-ARCHITECTURE.md` cho route, `05-MOCK-SCENARIOS.md` cho seed IDs.
