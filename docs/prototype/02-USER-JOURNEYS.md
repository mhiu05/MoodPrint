# MoodPrint — User Journeys & Interaction Flows

> 07/11/2026 • Mục tiêu: đặc tả luồng hành vi xuyên màn hình, **không phụ thuộc backend**. Mọi tên và tình huống là hư cấu.

## 1. Personas và kỳ vọng riêng

| Mã | Persona | Thiết bị / năng lực | Mong muốn chính | Điều cần tránh |
|---|---|---|---|---|
| P11 | An, 12 tuổi, bị bạn gọi biệt danh | Android 360px, ít kiên nhẫn đọc | Biết đây có phải hành vi không ổn, tìm người nói chuyện | Form dày đặc, thuật ngữ như “evidence” |
| P14 | Minh, 15 tuổi, bị nhắn đe dọa trong nhóm | Điện thoại 390px, nhiều screenshot | Gom bằng chứng, chuẩn bị nói với giáo viên | Tự động công khai bằng chứng |
| P16 | Hà, 16 tuổi, bị cô lập trong lớp | Mobile 375px, khó nhớ mốc thời gian | Kể từng phần, bổ sung sau | Ép phải biết chính xác mọi ngày giờ |
| PB | Linh, 14 tuổi, chứng kiến sự việc | Mobile 430px | Giúp bạn mà không làm tình hình xấu hơn | Khuyến khích đối đầu/công khai danh tính |
| PA | Nhân viên quản trị trường giả lập | Desktop 1440px | Thấy tổng quan và dòng trạng thái ví dụ | Nhầm dữ liệu demo với sự kiện thật |

**Nguyên tắc xuyên suốt:** Nhiều con đường vào, không bắt tất cả học sinh theo cùng một trình tự. Luôn có `Lưu nháp`, `Quay lại`, `Bỏ qua câu hỏi này`, `Tìm hỗ trợ` khi phù hợp. Người dùng có quyền sửa nội dung AI suy ra trước khi lưu.

## 2. Journey map tổng quan

| Giai đoạn | Câu hỏi trong đầu | Điểm chạm | Phản hồi UI mong đợi | Dấu hiệu thành công |
|---|---|---|---|---|
| Discover | “App này giúp gì?” | Welcome carousel | Lợi ích ngắn, nhân vật/tình huống gần gũi, Skip | Hiểu 3 việc app làm được |
| Enter | “Có cần kể chuyện ngay không?” | Mock register/login | Có nút thử demo; giải thích không tạo tài khoản server | Vào Home không lúng túng |
| Orient | “Mình bắt đầu ở đâu?” | Home | 4 CTA (Chat/Ghi lại/Luyện nói/Tìm hỗ trợ) | Chọn đúng nhu cầu |
| Understand | “Điều gì đang xảy ra?” | AI Chat, Knowledge | AI hỏi làm rõ; đánh dấu bất định | Không bị dán nhãn vô căn cứ |
| Document | “Mình có thể lưu những gì?” | Case wizard, screenshot | Timeline, evidence và xác nhận trước lưu | Tạo được hồ sơ có ít nhất 1 mốc |
| Prepare | “Bây giờ làm gì?” | Next steps / Action Plan | 2–3 lựa chọn, checklist, hướng tới nguồn giúp | Chọn một bước khả thi |
| Practice | “Mình nói với thầy cô/bố mẹ thế nào?” | Roleplay | 3–5 lượt hội thoại, phản hồi cụ thể | Soạn được yêu cầu rõ ràng |
| Seek help | “Tìm ai?” | Support | Danh bạ nguồn, mẫu tin nhắn, liên hệ 111 | Biết cách thực hiện ngoài app |
| Return | “Chuyện đã thay đổi chưa?” | Home, Case Detail | Timeline và việc đã làm | Theo dõi được tiến triển |

## 3. Luồng J01 — Onboarding & đăng nhập demo

**Entry:** Mở website lần đầu. **Goal:** vào Home đúng vai trò học sinh, không có backend.

1. `/welcome/1` — “Có những chuyện ở trường khiến mình thấy khó nói.” CTA **Tiếp tục**, **Bỏ qua**.
2. `/welcome/2` — “Kể từng chút với AI, không cần phải kể hết một lúc.”
3. `/welcome/3` — “Ghi lại sự việc, hình ảnh và những điều bạn nhớ.”
4. `/welcome/4` — “Luyện cách nói và tìm nguồn hỗ trợ.” CTA **Bắt đầu**.
5. `Skip` từ bất kỳ trang nào → `/auth`.
6. Form `Tạo tài khoản demo`: nickname, nhóm tuổi, email định dạng mẫu và mật khẩu *không truyền đi*; hoặc “Dùng tài khoản demo có sẵn”.
7. Xác nhận mô phỏng → `/home`, badge phiên bản thử nghiệm.

**Quy tắc:** `Skip` không bypass bước account. Nếu đăng nhập demo đã có trong session, đi thẳng Home. Nếu input không hợp lệ → inline error. Khi reset, data về seed ban đầu.

**Nghiệm thu:** dùng được bằng keyboard; không bắt buộc nhập tên trường thật; không gửi email; không lưu mật khẩu; có giải thích rõ demo.

## 4. Luồng J02 — Kể chuyện và AI hỏi làm rõ

**Entry:** Home → “Trò chuyện với AI” hoặc tab AI. **Case:** bị gọi biệt danh nhiều lần.

1. Chat welcome hỏi: “Có chuyện gì đang khiến bạn bận tâm?” Có quick prompts “Bị trêu chọc”, “Bị nhắn tin”, “Mình chứng kiến”, “Mình chưa rõ”.
2. Người dùng nhập: “Các bạn hay gọi mình bằng biệt danh mình không thích.”
3. AI mock: ghi nhận trải nghiệm, hỏi một câu ngắn: “Việc này xảy ra thường xuyên không? Bạn có muốn kể về lần gần nhất?”
4. Người dùng chọn chip “Nhiều lần trong 2 tuần” hoặc gõ tự do.
5. AI hiển thị insight card 4 vùng: **Điều bạn kể**, **Dấu hiệu cần chú ý**, **Điều mình chưa rõ**, **Bước có thể thử**.
6. CTA “Lưu thành hồ sơ” → wizard có dữ kiện prefill; “Tìm hiểu thêm” → Knowledge article; “Luyện nói với giáo viên” → roleplay.

**Nhánh:** user nói “chỉ đùa một lần” → AI không ép phân loại bắt nạt; cung cấp câu hỏi làm rõ. User chưa muốn lưu → chat tiếp, lưu mock session nếu bật trong demo. User từ chối câu hỏi → đáp án tôn trọng không ép.

**Nghiệm thu:** AI mock không nói “chắc chắn”, tất cả CTA thực sự điều hướng và mang theo context.

## 5. Luồng J03 — Phân tích 8 screenshot tin nhắn

**Entry:** AI → Add attachment → chọn fixture `messenger-group-8` (không phải OCR thật).

**Bối cảnh:** 8 ảnh giả lập về một nhóm chat trong 5 ngày, gồm bình luận chế giễu, một lời đe dọa và các khoảng trống nội dung.

1. Import panel hiển thị `8 ảnh mẫu / dữ liệu giả lập`; có thumbnail, lựa chọn bỏ ảnh.
2. “Phân tích bản demo” → loading mô phỏng 0,6–1,2s; có cách bỏ animation.
3. Kết quả hiển thị bảng `S01..S08`, đoạn text trích xuất, timestamp trong ảnh, nguồn, độ rõ, cảnh báo bị cắt/khó đọc.
4. Người dùng mở từng item, sửa đoạn text hoặc đánh dấu “không đúng”.
5. Phân tích nhận diện **dấu hiệu có thể liên quan**: xúc phạm, đe dọa, hành vi lặp; không suy ra danh tính thật/tính xác thực ảnh.
6. AI hỏi bổ sung: “Chuyện này có xảy ra ở lớp không?”, “Bạn có đang cảm thấy không an toàn hôm nay không?” (không đặt nhiều câu cùng lúc).
7. Tab Timeline hiện 5 ngày, các mốc và link nguồn ảnh; nếu timestamp không chắc chắn → `Khoảng ngày ...` hoặc `Chưa rõ`.
8. CTA “Tạo hồ sơ từ phần đã xác nhận” → điền wizard; người dùng xác nhận trước khi save.
9. CTA “Chuẩn bị nhờ hỗ trợ” → Support composer có tóm tắt trung tính.

**State cases:** image bị trùng → nhắc xem lại; screenshot có text xung đột → cột “cần xác minh”; user xóa một ảnh → dữ kiện liên quan cập nhật; ảnh còn chưa được duyệt không vào timeline chính.

**Nghiệm thu:** 8 fixture xuất hiện; chi tiết trích dẫn ảnh phải truy ngược được; không tồn tại nút “AI xác thực chứng cứ”; source không được tự thay đổi khi user sửa.

## 6. Luồng J04 — Tạo hồ sơ thủ công theo mẫu

**Entry:** Tab Hồ sơ → Tạo hồ sơ → chọn `Tin nhắn đe dọa`.

- **B1 Tên và mục đích:** đặt tên trung tính “Nhóm chat lớp 9”, vai trò `tôi gặp / tôi chứng kiến`.
- **B2 Chuyện xảy ra:** tóm tắt, loại sự việc, lặp lại hay một lần, ngày rõ/không rõ, địa điểm học đường/online/khác.
- **B3 Người liên quan:** vai trò `người gửi / người chứng kiến / người có thể giúp`; không ép tên thật.
- **B4 Ảnh hưởng:** ảnh hưởng lên cảm giác an toàn, học tập, quan hệ; cho phép “không muốn trả lời”.
- **B5 Bằng chứng:** thêm ảnh mẫu, ghi chú; hiển thị source tag.
- **B6 Xem lại:** khả năng edit từng section; `Lưu nháp`/`Lưu hồ sơ`.

**Nhánh:** không biết ngày → chọn “Không nhớ chính xác”; không có file → vẫn lưu; bỏ giữa chừng → sheet “Giữ bản nháp hay thoát?”; đổi template giữ dữ liệu chung nhưng không xóa field không trùng khi chưa xác nhận.

**Nghiệm thu:** một case có thể có 0 hoặc nhiều evidence, ≥1 mô tả sự việc và trạng thái; sau lưu hiện trong Home lẫn Hồ sơ.

## 7. Luồng J05 — Tiếp tục bổ sung và nhìn lại timeline

**Entry:** Home card hồ sơ → `/cases/:id`.

1. Header: tên trung tính, trạng thái, ngày cập nhật, không hiển thị quá nhiều tên cá nhân.
2. `Tổng quan | Dòng thời gian | Bằng chứng | Bước tiếp theo` là các mục con.
3. Thêm sự việc mới: tự nhập hoặc chọn từ chat mock đã liên kết.
4. Mốc được đánh nhãn `Tôi kể` / `Từ ảnh mẫu` / `Đã xác nhận lại`.
5. Filter theo ngày/loại/nguồn, liên kết evidence.
6. “Chuẩn bị bản tóm tắt” → preview với vùng **đã xác nhận/chưa rõ** rõ ràng.
7. Có thể đổi `active → monitoring → closed` thủ công, không ngụ ý trường học xác nhận.

**Nghiệm thu:** cập nhật timeline không phá các evidence trước đó; có undo/sửa nháp; khi case đóng vẫn xem được.

## 8. Luồng J06 — Tạo Kế hoạch ứng phó bên trong Hồ sơ sự việc (đã chốt)

**Entry:** Case Detail → `Bước tiếp theo` → “Gợi ý một kế hoạch”.

1. Hiển thị 2–3 lựa chọn có lý do: chuẩn bị nội dung nhờ giúp, lưu bổ sung thông tin, dùng công cụ chặn/báo cáo trên nền tảng khi phù hợp.
2. Người dùng chọn một lựa chọn, chỉnh tên bước và thời điểm muốn thực hiện.
3. Tạo checklist, không auto-send hay auto-block.
4. Tick hoàn thành → mở hỏi “Điều gì đã diễn ra?” (có `Bỏ qua`).
5. Home đồng bộ tiến độ `2/4`.
6. Nếu phản hồi không tốt hoặc tình hình thay đổi → “Điều chỉnh kế hoạch”.

**Nghiệm thu:** một checklist không được hiển thị là đã “giải quyết vụ việc”; có thể reset demo data.

## 9. Luồng J07 — Roleplay với giáo viên

**Entry:** Tab AI → Phòng luyện nói → Giáo viên.

1. Chọn mục tiêu: `Kể chuyện lần đầu`, `Đề nghị được giúp`, `Khi người nghe chưa hiểu`.
2. Chọn độ khó: nhẹ nhàng / trung lập / hỏi kỹ nhưng tôn trọng.
3. Preview kịch bản: thời lượng mô phỏng 3–5 lượt, chuẩn bị từ hồ sơ nào hoặc luyện với tình huống giả.
4. Voice demo: animation + transcript; không yêu cầu quyền microphone. Text mode cho nhập và chọn câu trả lời.
5. “Giáo viên AI”: hỏi ngắn một câu, chờ user trả lời; không nói chuyện thay user.
6. Feedback cuối: `Rõ sự việc`, `Nêu thời gian`, `Nói điều mong muốn`, `Một câu có thể thử`.
7. CTA “Thử lại”, “Lưu mẫu lời trình bày”, “Chuẩn bị nhắn tin”.

**Nghiệm thu:** có pause/stop/retry, feedback không chấm điểm nhân phẩm/độ trung thực, không giả giáo viên thật.

## 10. Luồng J08 — Roleplay với phụ huynh

**Entry:** Tab AI → Phòng luyện nói → Phụ huynh.

- Mục tiêu: nói chuyện khi ngại, khi sợ bị mắng, khi cần bố mẹ giúp đặt lịch trao đổi với trường.
- Có mức độ `dịu dàng`, `hỏi thêm`, `chưa hiểu ngay` nhưng **không có roleplay mắng chửi/gây áp lực kéo dài**.
- AI gợi ý cấu trúc: “Chuyện xảy ra / Điều khiến em lo / Điều em mong bố mẹ hỗ trợ”.
- Kết thúc với bản nháp tin nhắn để dùng thực tế nếu người dùng tự chọn.

**Nghiệm thu:** không buộc gửi cho cha mẹ; có tùy chọn một người lớn khác nếu gia đình không phải kênh an toàn.

## 11. Luồng J09 — Tìm hỗ trợ và tạo yêu cầu bí danh

**Entry:** Tab Support → “Tìm người có thể giúp”.

1. User chọn `Mình muốn được nghe`, `Mình muốn xin giúp`, `Mình muốn báo cáo`.
2. Chọn đối tượng: giáo viên chủ nhiệm, phụ huynh/người chăm sóc, người đáng tin cậy khác, đường dây hỗ trợ.
3. Tạo bản nháp từ tóm tắt case hoặc nhập mới.
4. Bật `Dùng bí danh trong bản xem trước` (hiển thị nhãn không phải ẩn danh tuyệt đối).
5. Preview có các phần cần thiết và phần có thể ẩn; chọn **Sao chép**, **Lưu bản nháp**, **Xuất để tự gửi**.
6. Nếu bấm nút “Gửi báo cáo demo” → modal xác nhận `Không gửi tới nhà trường`; sau đó status `DEMO – Đã lưu mô phỏng`.
7. “Theo dõi” cho thấy timeline giả định; không có SLA thật.

**Nghiệm thu:** không phát email/call tự động; UI không có câu “Trường đã nhận” thiếu qualifier demo.

## 12. Luồng J10 — Cần hỗ trợ gấp

**Entry:** ở Home/Chat/Case/Support qua đường dẫn `Tìm hỗ trợ ngay`, hoặc từ scenario có nguy hiểm hiện tại.

- Trình bày ưu tiên: tìm nơi an toàn và người lớn đáng tin cậy gần đó, liên hệ dịch vụ khẩn cấp phù hợp tại địa phương, Việt Nam có **Tổng đài 111** hỗ trợ trẻ em (miễn phí 24/7, theo nguồn chính thức).
- Không giấu kênh hỗ trợ bên dưới màn hình nhiều bước; không bắt hoàn thiện case/chat.
- Có hành động mở `tel:111` (do thiết bị quyết định), xem website chính thức.
- Cung cấp nút `Quay lại chat` sau khi user chủ động chọn, nhưng không biến AI thành cổng bắt buộc.
- Không cố suy đoán vị trí người dùng, không claim đã gọi/điều phối hỗ trợ.

**Nghiệm thu:** mở được màn trong ≤2 thao tác từ 4 tab; nội dung ngắn, rõ, dễ đọc.

## 13. Luồng J11 — Người chứng kiến

**Entry:** Home “Mình muốn giúp bạn” hoặc Knowledge topic `Người chứng kiến`.

1. Nội dung giúp phân biệt hỗ trợ an toàn với việc can thiệp gây nguy hiểm.
2. AI mock hỏi “Bạn có đang ở gần nguy cơ bạo lực không?” và “Bạn muốn giúp theo cách nào?”.
3. Gợi ý lựa chọn: ở bên người bị hại, tìm người lớn hỗ trợ, ghi nhớ điều chứng kiến trung thực, không chia sẻ ảnh gây tổn thương.
4. Tạo hồ sơ vai trò `người chứng kiến` hoặc soạn lời nhờ giúp, không bắt nêu tên bạn.

**Nghiệm thu:** không buộc người chứng kiến đối mặt trực tiếp với nhóm bắt nạt.

## 14. Luồng J12 — Knowledge Hub khám phá và quiz

**Entry:** Support → Knowledge Hub; deep link từ AI analysis.

1. Danh mục hiển thị 6–8 topic; search theo từ khóa và câu hỏi.
2. Article detail hiển thị badge chủ đề, độ tuổi phù hợp, thời gian đọc, nội dung ngắn và nguồn gốc.
3. Mini scenario có 2–3 lựa chọn; sau khi chọn thấy giải thích, **không chấm điểm con người**.
4. CTA “Hỏi AI về tình huống này” mang article/source ID tới chat mock.
5. Bookmark → tab Đã lưu (mock state).

**Nghiệm thu:** có empty search, loading/retry mô phỏng, link nguồn rõ và không tự động rời ứng dụng khi user đang soạn form.

## 15. Luồng J13 — School Admin Demo

**Entry:** màn quảng bá hoặc route riêng `/demo/school`; không nằm trong 4 tab học sinh.

1. Banner “BẢN DEMO — TẤT CẢ DỮ LIỆU ĐỀU GIẢ LẬP”.
2. KPI tổng hợp: số báo cáo giả, thời gian xử lý giả, phân bố chủ đề giả; filter khoảng thời gian/class group đều là synthetic.
3. Chọn một thẻ report giả → dòng trạng thái và danh sách hành động demo.
4. Thay đổi trạng thái report giả → số liệu demo cập nhật.
5. CTA “Quay lại giao diện học sinh”, không đem dữ liệu admin về student workspace.

**Nghiệm thu:** không truy nhập `studentCaseStore`; không có email cá nhân; số liệu có nhãn giả lập trong cả chart và tooltip.

## 16. Luồng J14 — Cài đặt, reset và lỗi

- Profile: đổi nickname demo, nhóm tuổi, chế độ hiển thị hồ sơ, cài đặt giao diện.
- Reset mock: modal giải thích “Xóa mọi thay đổi trong phiên demo và khôi phục dữ liệu ban đầu”; 2 nút `Hủy` / `Khôi phục`.
- Error simulation (qua debug/demo controls): không có kết quả Knowledge, hỏng ảnh bằng chứng, chưa có hội thoại, trống case, roleplay tạm dừng, không có nguồn khu vực.
- Khi rời wizard chưa lưu → xác nhận tránh mất bản nháp.

## 17. Journey → màn hình → fixture → test case

| Journey | Các route quan trọng | Fixture tham chiếu | Kiểm thử chính |
|---|---|---|---|
| J01 | `/welcome/*`, `/auth`, `/home` | USER-AN | Không có auth thật |
| J02 | `/ai/chat`, `/cases/new` | SC-01 | Dữ liệu chưa rõ không bị kết luận |
| J03 | `/ai/chat`, `/ai/analysis/:id`, `/cases/new` | SC-08, MEDIA-01..08 | 8 ảnh, timeline, source trace |
| J04 | `/cases/new`, `/cases/:id` | SC-02/03 | Save draft, validation |
| J05 | `/cases/:id` | CASE-A | Timeline và evidence linked |
| J06 | `/cases/:id/plan` | PLAN-A | Checklist thay đổi Home |
| J07 | `/ai/roleplay/teacher` | RP-TEACHER-01 | 3+ lượt, feedback |
| J08 | `/ai/roleplay/parent` | RP-PARENT-01 | Lựa chọn người lớn khác |
| J09 | `/support/prepare`, `/support/requests` | HELP-01 | Không gửi thật |
| J10 | `/support/urgent` | HELP-111 | `tel:111`, không bắt login tiếp nếu đang trong ứng dụng |
| J11 | `/knowledge/bystander` | SC-11 | Gợi ý không gây nguy hiểm |
| J12 | `/support/knowledge`, `/knowledge/:slug` | KB-01..24 | Citation & no-results |
| J13 | `/demo/school` | SCHOOL-DATA-01 | Tách dữ liệu demo |
| J14 | `/settings` | USER-AN | Reset/unsaved-state |

## 18. Test session với người dùng (kế hoạch, chưa thực hiện)

**Nhóm A (11–13):** J01, J02, J12; đo độ dễ hiểu câu chữ, thời gian tìm CTA và độ tự tin khi chọn bước tiếp theo. **Nhóm B (14–17):** J03, J04, J07, J09; đo khả năng hiểu khái niệm evidence/cần xác minh và phân biệt demo với liên hệ thật. **Đối tượng trưởng thành quan sát UX:** đánh giá J13 trên dữ liệu giả. Với người chưa thành niên, tổ chức nghiên cứu thực tế cần có quy trình phù hợp trước khi mời tham gia; hiện chỉ là kế hoạch.

**Các câu hỏi kết thúc:** “Bạn nghĩ MoodPrint đã thực sự làm gì?”, “Nội dung nào còn khó hiểu?”, “Bạn có thể chỉ ra nơi tìm người hỗ trợ không?”, “Ở bước nào bạn không muốn tiếp tục?”, “Bạn nghĩ báo cáo đã gửi thật chưa?”.
