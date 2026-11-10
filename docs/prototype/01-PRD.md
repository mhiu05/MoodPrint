# MoodPrint — Product Requirements Document (PRD)

> **Trạng thái:** Baseline thiết kế prototype • **Ngày:** 07/11/2026 • **Phạm vi:** mobile-first web, 100% mock data • **Mục đích:** tài liệu để UX/product/coding agent triển khai thống nhất; không phải tuyên bố đã có dịch vụ hỗ trợ hay hệ thống AI đang chạy.

## 1. Tóm tắt sản phẩm

**MoodPrint** là không gian đồng hành cho học sinh 11–17 tuổi gặp hoặc chứng kiến bắt nạt trực tiếp/trực tuyến. Sản phẩm giúp các em **nhận biết tình huống → kể và làm rõ → ghi nhận sự việc → chuẩn bị cách ứng phó → luyện trình bày → tìm nguồn hỗ trợ**. Ứng dụng không thay người lớn/cơ quan có thẩm quyền ra quyết định và không tự kết luận một cá nhân có hành vi vi phạm chỉ từ một phía câu chuyện.

**North-star trải nghiệm:** Một học sinh mở MoodPrint khi chưa biết phải làm gì có thể hoàn thành **một bước hữu ích tiếp theo** trong một phiên: hiểu hơn về tình huống, tạo bản ghi, chuẩn bị lời nói, tìm người đáng tin cậy hoặc mở kênh hỗ trợ phù hợp.

**Không phải:** mạng xã hội, nơi ghép đôi học sinh, công cụ điều tra người khác, hệ thống giám sát của nhà trường, dịch vụ tư vấn chuyên môn thật, nền tảng tiếp nhận tố cáo thật khi chưa có đối tác.

## 2. Quyết định đã chốt / còn mở

| ID | Nội dung | Trạng thái | Hệ quả |
|---|---|---|---|
| D01 | Chỉ dùng tên MoodPrint, không gắn số phiên bản | **Đã chốt** | Mọi copy/route/document dùng tên thống nhất |
| D02 | Xây lại source cũ; prototype ưu tiên trải nghiệm | **Đã chốt** | Không duy trì agents/backend/CI cũ cho prototype |
| D03 | React + Vite + TypeScript; FastAPI + OpenAI Agents SDK là hướng tương lai | **Đã chốt** | Stack backend chỉ mô tả, chưa triển khai |
| D04 | Dữ liệu mock, không gọi API thật, không deploy hạ tầng | **Đã chốt** | Gắn nhãn demo, mọi hành động chỉ làm việc trên mock state |
| D05 | Người dùng mục tiêu 11–17; buộc đăng ký để sử dụng, không guest | **Đã chốt cho thiết kế** | Hiển thị form đăng ký/đăng nhập **mô phỏng** |
| D06 | Mobile-first web, 4 tab Home / AI / Hồ sơ / Support | **Đã chốt** | Bottom navigation 4 mục |
| D07 | Student Dashboard và School Admin Demo tách biệt | **Đã chốt** | Không hiển thị dữ liệu trường học thực ở tab Home |
| D08 | Ẩn danh ở mức bí danh/giấu danh tính người gửi, không tuyệt đối | **Đã chốt** | Copy và trạng thái phải nêu đúng giới hạn |
| D09 | Một AI Companion thống nhất, gồm chat và roleplay | **Đã chốt** | Không bắt người dùng chọn agent nội bộ |
| D10 | 5 trụ cột sản phẩm: Knowledge Hub, Hồ sơ sự việc, Kế hoạch ứng phó, AI Companion & Roleplay, Support Center | **Đã chốt** | Mỗi tính năng có user journey và acceptance riêng |
| D11 | Tính năng lõi số 3 là **Kế hoạch ứng phó (Action Plan)**, bố trí **bên trong Hồ sơ sự việc** | **Đã chốt** | Route `/cases/:caseId/plan`, dùng case ID chung, không tạo tab thứ 5 |
| D12 | Website `moodprint.duckdns.org`, domain email `moodprintapp.com` | **Đã chốt** | Chỉ ghi nhận; không chạm DNS, SES, EC2 |
| D13 | Trường có thể nhận báo cáo/giám sát thật | **CHƯA CÓ TÍCH HỢP** | School Admin và gửi yêu cầu chỉ là demo giả lập |

### Phân biệt phạm vi

- **Prototype chạy được:** React SPA với mock state và dữ liệu JSON/TS; điều hướng, nhập form, lọc, checklist, hội thoại dựng sẵn, replay roleplay, phản hồi mẫu, biểu đồ tổng hợp giả lập.
- **Thiết kế nhưng không triển khai:** FastAPI, DB/Auth, Agents SDK, RAG, STT/TTS, OCR, Apify, web search, map search, email/SMS, tích hợp school helpdesk.
- **Hành động ngoài ứng dụng:** Link nguồn chính thức, `tel:111`, mở URL website dịch vụ; người dùng tự quyết định truy cập. Không giả vờ đã có người nhận hỗ trợ.

## 3. Vấn đề & Jobs To Be Done

### 3.1 Các nhóm người dùng

| Persona | Hoàn cảnh | JTBD | Rào cản |
|---|---|---|---|
| P1 — Học sinh 11–13 | Không chắc trêu đùa/cô lập là bắt nạt | “Giúp em hiểu chuyện này và nói với người lớn bằng cách dễ hiểu” | Dễ bị quá tải văn bản, sợ bị mắng |
| P2 — Học sinh 14–17 | Bị đe dọa, tung tin online, sự việc kéo dài | “Giúp em lưu lại những gì xảy ra và chuẩn bị cách tìm hỗ trợ” | Ngại lộ danh tính, khó chứng minh chuỗi sự việc |
| P3 — Người chứng kiến | Thấy bạn bị cô lập/đe dọa | “Em có thể giúp mà không bị kéo vào nguy hiểm không?” | Sợ trả đũa, chưa biết kênh báo |
| P4 — Người hỗ trợ là người lớn | Giáo viên/phụ huynh được mô phỏng trong nội dung và roleplay | “Biết cách lắng nghe, hỏi và phản hồi có ích” | Có thể vô tình phủ nhận hoặc trách móc |
| P5 — Quản trị trường (demo riêng) | Cần hiểu dữ liệu tổng hợp giả lập | “Xem xu hướng và tiến độ xử lý mô phỏng” | Dễ hiểu nhầm dashboard là hệ thống vận hành thật |

### 3.2 Pain points được sản phẩm giải quyết

1. **Không nhận diện được vấn đề:** khó phân biệt mâu thuẫn một lần, trò đùa và dấu hiệu bắt nạt có chênh lệch quyền lực/lặp lại.
2. **Không biết kể bắt đầu từ đâu:** sự việc rời rạc, thiếu thời điểm, nơi xảy ra, điều đã thử.
3. **Khó giữ bằng chứng có ngữ cảnh:** nhiều ảnh chụp, đoạn chat, lời kể, có chỗ chưa chắc chắn.
4. **Không dám nói với người có thể giúp:** lo bị xem nhẹ, sợ đối thoại, không biết yêu cầu gì.
5. **Không thấy đường tiến lên:** sau khi kể xong cần lựa chọn bước tiếp theo và theo dõi.

## 4. Mục tiêu sản phẩm và chỉ số đánh giá prototype

| Mục tiêu | Kịch bản đo | Ngưỡng mong muốn (mục tiêu nội bộ, chưa đo) |
|---|---|---|
| Tìm được điểm bắt đầu | Từ Home chọn một hành động phù hợp | 90% người test tìm được trong 15 giây |
| Ghi lại sự việc | Tạo hồ sơ có thời điểm, tường thuật, mức ảnh hưởng và nguồn | ≥80% hoàn thành không cần trợ giúp |
| Hiểu AI phân tích không phải kết luận | Xem màn hình phân tích | ≥90% phân biệt “dữ kiện/nhận định/còn thiếu” |
| Chuẩn bị nhờ hỗ trợ | Tạo tin nhắn hoặc qua roleplay | ≥80% tạo được lời trình bày có yêu cầu rõ |
| Không ngộ nhận tích hợp thật | Xem School Admin / Support demo | 100% người test hiểu “chưa gửi thật” |
| Trải nghiệm di động | Kiểm thử 320/375/390/430px | Không tràn ngang; thao tác chính dùng một tay |
| Accessibility | Keyboard, focus, touch, screen reader | Không có lỗi chặn tác vụ quan trọng |

Không báo các số trên như kết quả đạt được; đây là tiêu chí để kiểm tra sau khi code.

## 5. Phạm vi chức năng chi tiết

### F1. Knowledge Hub

- **Tìm kiếm** theo tên vấn đề, tình huống, câu hỏi; mock full-text/fuzzy đơn giản, bộ lọc topic/độ tuổi/đối tượng.
- **Content taxonomy:** trực tiếp, online, cô lập/xã hội, đe dọa, ảnh riêng tư, ứng xử của người chứng kiến, nói chuyện với người lớn, sức khỏe tinh thần và tìm hỗ trợ.
- **Content formats:** bài hướng dẫn 3–7 phút, checklist từng bước, FAQ, tình huống lựa chọn A/B/C, quiz ngắn, video/ảnh tham chiếu chỉ khi có nguồn/giấy phép.
- **Bài chi tiết:** tiêu đề dễ hiểu, tóm tắt 30 giây, điều cần biết, lựa chọn hành động, điều không nên làm, khi cần nhờ giúp ngay, link nguồn, ngày rà soát.
- **Tương tác:** đánh dấu đã đọc, bookmark, tiếp tục đọc, “Thảo luận tình huống này với AI” (mở chat mock có ngữ cảnh).
- **Edge cases:** không có kết quả → gợi ý topic; link hỏng → hiển thị nguồn URL để tự mở; nguồn ngoài Việt Nam → nhãn phạm vi áp dụng.

**Acceptance:** ít nhất 24 bài/khối nội dung mock chất lượng, 10 tương tác tình huống, 5 quiz; mỗi bài có ít nhất một metadata nguồn và không gắn số liệu không kiểm chứng.

### F2. Hồ sơ sự việc (Incident Cases)

- **Danh sách:** số hồ sơ, trạng thái `draft/active/monitoring/closed`, tìm kiếm/lọc, sort mới nhất, card tóm tắt.
- **Bộ mẫu:** bị trêu chọc/xúc phạm, tin nhắn đe dọa, bị cô lập, xô xát, lan truyền ảnh, mạo danh, chứng kiến sự việc, mẫu tự do.
- **Tạo/sửa:** tên hồ sơ (có thể dùng tên trung tính), bối cảnh, thời gian dự kiến/không rõ, địa điểm, sự việc, người có liên quan theo vai trò, ảnh hưởng, điều đã thử, người tin cậy; nhập dần/lưu nháp.
- **Timeline:** nhiều mốc trong một hồ sơ; phân biệt sự kiện do người dùng kể và sự kiện được mô phỏng trích xuất từ file.
- **Evidence:** ảnh chụp tin nhắn, file mock PDF, văn bản người dùng chép, ghi chú; mỗi bằng chứng có nhãn nguồn, ngày giờ người dùng khai, ngày giờ hiển thị trong ảnh, trường nào chưa kiểm chứng.
- **AI-assisted entry:** lối vào “Kể chuyện để tạo hồ sơ”; mock flow trích dữ kiện → xác nhận từng trường → lưu.
- **Mối liên hệ:** một chat session có thể gắn một hồ sơ; nhiều lần kể chuyện bổ sung vào cùng hồ sơ nhưng phải được người dùng xác nhận.
- **Xuất báo cáo:** preview in/Markdown/PDF placeholder — prototype có thể tạo plain text printable từ mock state; không tuyên bố chứng cứ pháp lý.
- **Thao tác nguy hiểm:** xóa hồ sơ cần xác nhận; không tự gửi nội dung cho ai.

**Acceptance:** 8 mẫu đầu vào, tạo mới/sửa/lưu nháp/đính kèm mock/lọc hồ sơ và timeline rõ nguồn gốc; dữ liệu cập nhật nhất quán ở Home và AI.

### F3. Kế hoạch ứng phó (Action Plan) — tính năng lõi đã chốt, nằm trong Hồ sơ sự việc

**Vị trí và điều hướng:** mỗi hồ sơ có mục **Kế hoạch ứng phó** (route `/cases/:caseId/plan`), truy cập từ Case Detail, AI analysis và Home (deep link tới hồ sơ tương ứng). Không tạo tab thứ năm hoặc một không gian dữ liệu tách rời hồ sơ.

- **Bắt đầu:** người dùng có thể tạo kế hoạch thủ công từ hồ sơ, hoặc chọn một trong 2–3 phương án được AI mock gợi ý sau khi phân tích. Mọi gợi ý luôn có lý do, điều kiện áp dụng, điểm cần cân nhắc và lựa chọn 'Em chưa sẵn sàng'.
- **Cấu trúc:** `planId`, `caseId`, mục tiêu, tiêu đề, độ ưu tiên, trạng thái `draft/active/paused/completed`, các lựa chọn, danh sách bước nhỏ (`PlanItem`), người có thể hỗ trợ, ngày xem lại, ghi chú kết quả và nguồn đề xuất.
- **Tương tác:** thêm/sửa/xóa mục việc, đổi thứ tự, đánh dấu hoàn tất, tạm dừng/tiếp tục, đặt ngày xem lại, lưu ghi chú. Home hiển thị tiến độ lấy từ cùng mock store; hỗ trợ nhiều hồ sơ, không trộn checklist giữa các hồ sơ.
- **Liên kết:** từ AI Chat/Analysis có CTA 'Thêm vào kế hoạch ứng phó'; từ Support có CTA 'Chuẩn bị liên hệ' và quay lại kế hoạch; từ Hồ sơ có thể xem timeline bên cạnh những bước đã thực hiện.
- **Kế hoạch trong tình huống nguy cấp:** ưu tiên đường tìm hỗ trợ phù hợp và không đưa ra nhiệm vụ khiến học sinh phải tự đối đầu với người đe dọa. Gợi ý kế hoạch không thay thế trợ giúp trực tiếp.
- **Ngữ nghĩa trạng thái:** đánh dấu 'Hoàn tất' nghĩa là người dùng tự ghi đã làm bước đó; **không** có nghĩa MoodPrint đã gửi thư, nhà trường đã nhận báo cáo hoặc tình huống đã an toàn.
- **Mock demo:** các cập nhật chỉ thay đổi state local/deterministic fixture. Không có reminder, liên hệ, gửi báo cáo hoặc nhận diện mối nguy ngoài đời thực.

**Acceptance:** từ một hồ sơ tạo/chọn được kế hoạch; chỉnh sửa tối thiểu 3 bước, cập nhật trạng thái và ghi chú; quay lại Home thấy tiến độ đúng; reload/reset demo theo cơ chế mock đã định; không có bước nào tự tuyên bố đã liên hệ người khác. Cần có empty, draft, paused, completed và error/retry states cho demo.

### F4. AI Companion & Roleplay

**Một companion thống nhất**, hai entry point:

1. **Chat:** nhập text, chọn prompt gợi ý, thêm file giả, chọn hồ sơ liên quan, phân tích tình huống, hỏi làm rõ và xuất tóm tắt có cấu trúc.
2. **Roleplay:** chọn vai `parent/teacher` (có thể mở rộng trusted adult/counselor), mục tiêu buổi tập, mức độ hỗ trợ `gentle/neutral/challenging-but-respectful`, giao tiếp text hoặc voice demo, luyện nhiều lượt, feedback sau buổi.

**Khu phân tích:** tách `Thông tin nhìn thấy/được kể`, `Dấu hiệu có thể liên quan`, `Điều chưa rõ`, `Gợi ý bước tiếp theo`; mỗi nhận định liên kết evidence IDs/source khi có. OCR 8 ảnh là **fixture chuẩn bị sẵn**, có luồng người dùng rà soát và sửa trước khi lưu vào hồ sơ.

**Voice demo:** hiển thị transcript dựng sẵn, waveform animation, nút play/pause mô phỏng. Không yêu cầu microphone permission, không gọi OpenAI thật; dùng nhãn “Mô phỏng” rõ ràng.

**Acceptance:** tối thiểu 12 chat flows đa lượt, 6 roleplay scripts, 3 mẫu phân tích ảnh/timeline; có kịch bản mơ hồ, mâu thuẫn dữ liệu, dữ liệu thiếu và khẩn cấp.

### F5. Support Center

- **Nguồn trợ giúp:** liên hệ người đáng tin cậy (mẫu hồ sơ không tự gửi), giáo viên, phụ huynh, ban giám hiệu, chuyên viên khi có thật; link đến kênh chính thống.
- **Soạn yêu cầu:** chọn đối tượng, mục đích, mức chi tiết, dùng bí danh/hiển thị tên, xem trước nội dung, sao chép/tải xuống.
- **Báo cáo demo:** bắt đầu → xem trước → xác nhận → màn **“Đã lưu bản nháp báo cáo trong bản demo — chưa gửi tới nhà trường”**. Có thể mô phỏng status timeline trên dữ liệu giả, gắn watermark **DEMO**.
- **Theo dõi hỗ trợ:** `draft/prepared/demo_submitted/demo_reviewing/demo_closed`, không dùng `received_by_school` hoặc `contacted` trừ khi gắn nhãn demo.
- **Link điều hướng:** Knowledge Hub, người tin cậy, cài đặt hồ sơ, đường hỗ trợ khẩn cấp.
- **Ẩn danh:** profile nickname; trường `identity_mode: alias | disclose` áp dụng trên *bản xem trước*, giải thích “người quản lý hệ thống có thể biết tài khoản khi có hệ thống thật; không phải ẩn danh tuyệt đối”.

**Acceptance:** soạn/copy/xem trước mẫu tin nhắn; nguồn hỗ trợ phân loại theo đối tượng và điều kiện; không giả trạng thái tiếp nhận thật.

### F6. Student Dashboard

Không gọi đây là bảng thống kê toàn trường. Home hiển thị: lời chào, 4 hành động nhanh, tiến độ hồ sơ cá nhân, checklist kế hoạch, nội dung Knowledge Hub nổi bật, bản tin/tips an toàn được kiểm chứng. Không trưng biểu đồ nhạy cảm về trường hay người khác.

### F7. School Admin Demo — độc lập

- Entry riêng ở `/demo/school` qua liên kết “Xem bản demo dành cho nhà trường” với banner rõ ràng.
- KPI tổng hợp **giả lập**: số báo cáo theo tháng, loại sự việc, trạng thái xử lý, thời gian phản hồi mẫu, chủ đề cần ưu tiên.
- Data chỉ từ tập `school_demo_*.json` riêng, không được truy cập hồ sơ Student Workspace, kể cả trong mock state.
- Drill-down chỉ vào **hồ sơ giả** được tạo cho demo nhà trường, có nhãn; không có tên học sinh thật hay chi tiết định danh.
- No real export/notification/action to school. Các nút quản lý chỉ đổi state demo cục bộ.

## 6. Hệ thống account và onboarding (mock)

- Truy cập lần đầu: 4 trang giới thiệu `Next / Back / Skip`; bỏ qua đến màn đăng ký/đăng nhập.
- Đăng ký mô phỏng: nickname, nhóm tuổi 11–13/14–17, email demo (không gửi), mật khẩu demo (không gửi/không lưu mật khẩu thật), lựa chọn mối quan tâm. Thông báo rõ “Tài khoản minh họa, chưa tạo trên server”.
- Login mock: nút “Vào thử với tài khoản demo”, không diễn đạt là đăng nhập thật. Chuyển Home; persist lựa chọn UI trên session/local mock tùy thiết kế, nhưng không lưu secrets.
- Đăng xuất: reset demo session; dữ liệu mẫu mặc định có thể được khôi phục; có điều khiển “Reset dữ liệu demo”.
- Vị trí hiển thị trợ giúp khẩn cấp phải truy cập được từ Home, chat, case detail và Support; đối với nguy hiểm tức thời, gợi ý tìm người lớn tin cậy/dịch vụ khẩn cấp; VN: Tổng đài 111 là dịch vụ trẻ em miễn phí 24/7 (nguồn chính thức).

## 7. Nội dung và giọng điệu UX

**Tone:** tôn trọng, nhẹ nhàng, không đổ lỗi, không cam đoan quá mức, rõ bước tiếp theo; đối tượng 11–13 dùng câu ngắn và nút dễ hiểu, 14–17 có thể xem chi tiết mở rộng. Không dùng “bạn chắc chắn đang bị bắt nạt” khi thiếu thông tin; dùng “có dấu hiệu cần tìm hiểu thêm”.

**Copy mẫu:**
- Home: “Bạn muốn bắt đầu từ đâu?”
- AI: “Bạn có thể kể từng chút một. Mình sẽ hỏi thêm nếu cần hiểu rõ.”
- Phân tích: “Dưới đây là những gì mình nhận ra từ dữ liệu mẫu. Hãy kiểm tra lại trước khi lưu.”
- Nguồn trợ giúp: “Bạn muốn chuẩn bị lời nhắn cho ai?”
- Ẩn danh: “Dùng bí danh trong bản xem trước; đây không phải ẩn danh tuyệt đối.”
- Kết quả mock: “Đã lưu trong bản demo. Chưa có nội dung nào được gửi đến nhà trường.”

## 8. Non-functional dành riêng cho prototype

- Tương thích viewport 320/360/375/390/430/768/1024/1440; không tràn ngang.
- UI keyboard operable, focus rõ, `aria` phù hợp, label cho input, target chạm 44×44px, không phụ thuộc màu duy nhất.
- Cho phép dừng/tiếp tục animation; `prefers-reduced-motion`.
- Mock data không chứa số điện thoại/email thật của học sinh; chỉ dùng tên/ảnh giả không định danh.
- Có trạng thái empty/loading/error/disabled/success/confirmation; loading mock không nên ngụ ý mạng thật nếu không gọi mạng.
- Không gửi telemetry/content của người dùng ra bên ngoài khi đang ở prototype; hạn chế icon/image hotlink bên thứ ba.
- Dùng web app PWA-friendly UI nhưng không bật push notification thực.
- Không reset hoặc thay đổi database/CI/CD/AWS/DNS/SES theo yêu cầu này.

## 9. Ưu tiên và phạm vi theo từng đợt

| Ưu tiên | Nhóm | Định nghĩa xong |
|---|---|---|
| P0 | Onboarding mock, Shell, Home, AI chat, hồ sơ, Support khẩn cấp | Chạy được end-to-end hai hành trình chính |
| P1 | Knowledge Hub, screenshot analysis fixture, timeline, roleplay text, Action Plan lồng trong hồ sơ | Hành trình 6 bước có thể demo |
| P1 | Roleplay voice demo, support composer, case export preview | Trình diễn AI/voice mà không gọi API |
| P2 | School Admin Demo, quiz, microinteractions, deep linking, skeletons, offline/empty | Sản phẩm có chiều sâu và hoàn thiện |
| Future | FastAPI, Auth, AI, RAG, OCR, STT/TTS, external reporting, automation | Chỉ ghi vào tài liệu kiến trúc |

## 10. Definition of Done và test nghiệm thu

- [ ] Mọi màn hình trong IA có route; đi đến được bằng UI, kể cả back và deep link.
- [ ] 4 tab cố định trên mobile; màn detail có back rõ, không mất nhập liệu khi đổi tab ngoài ý muốn.
- [ ] 20+ bộ dữ liệu tình huống giả, ít nhất một case theo mạch 8 screenshots, đa độ tuổi/ngữ cảnh.
- [ ] Tạo/sửa/xem/đóng/mở case với mock state, cập nhật tất cả màn liên quan.
- [ ] AI mock có ít nhất một lần hỏi làm rõ và giải thích điều gì chưa chắc chắn.
- [ ] Roleplay teacher + parent có ít nhất 3 lượt nói, pause/retry/feedback.
- [ ] Knowledge Hub có nguồn, tìm kiếm, filter, bài chi tiết, tình huống tương tác.
- [ ] Support Center có liên hệ 111, tạo bản nháp, lựa chọn bí danh/hiện tên và banner “chưa gửi”.
- [ ] School Admin Demo độc lập dữ liệu và luôn hiển thị “Dữ liệu mô phỏng”.
- [ ] Các hành động thật chưa hỗ trợ đều có fallback rõ, không button chết.
- [ ] Chạy kiểm tra giao diện ở 7 viewport, keyboard, screen-reader smoke và happy/error/empty paths.
- [ ] Không có khóa API, Supabase URL với credential, request thật hoặc script deploy trong bundle prototype.

## 11. Rủi ro & phụ thuộc

| Rủi ro | Biện pháp prototype | Khi xây hệ thống thật |
|---|---|---|
| Gây hiểu nhầm AI là chuyên gia/người tiếp nhận | Gắn nhãn AI và demo, copy trung thực | Quy trình kiểm định, xử lý ca nguy hiểm |
| Gửi báo cáo thật chưa có trường đối tác | Không gửi; chỉ mô phỏng | Thỏa thuận tiếp nhận, xác thực role và SLA |
| OCR/screenshot bị hiểu sai | Chỉ dùng fixture, bắt xác nhận từng trường | Confidence/source trace, kiểm thử multimodal |
| Tư vấn khẩn cấp sai | Kênh trợ giúp rõ, không chỉ dựa trên chat | Escalation, đánh giá nguy cơ, hỗ trợ con người |
| “Ẩn danh” gây kỳ vọng sai | Diễn đạt chính xác chế độ bí danh | Phân quyền/khả năng truy vết/thông báo |
| Sản phẩm cho trẻ 11–17 | Nghiên cứu copy và trải nghiệm phù hợp tuổi | Trước vận hành thật phải giải quyết nghĩa vụ bảo vệ trẻ em, quyền dữ liệu, trách nhiệm hỗ trợ |

## 12. Nguồn tham khảo chính và dấu vết nghiên cứu

- UNICEF Việt Nam, **Bắt nạt trực tuyến là gì – Làm thế nào để ngăn chặn điều này?**: https://www.unicef.org/vietnam/vi/bat-nat-truc-tuyen-la-gi-lam-the-nao-de-ngan-chan-dieu-nay
- UNICEF Việt Nam, **Cách nói chuyện với những người có thẩm quyền về hành vi bắt nạt trong trường học**: https://www.unicef.org/vietnam/vi/cach-noi-chuyen-voi-nhung-nguoi-co-tham-quyen-ve-hanh-vi-bat-nat-trong-truong-hoc
- WHO/UNICEF/UNESCO, **Teaching with Care** (10/09/2026): https://www.who.int/publications/i/item/9789240124912
- UNESCO, **Connected and safe** (26/10/2026): https://www.unesco.org/en/articles/connected-and-safe-policy-orientations-address-online-and-technology-facilitated-violence-education
- StopBullying.gov, **What is bullying?**: https://www.stopbullying.gov/bullying/what-is-bullying
- StopBullying.gov, **Report cyberbullying**: https://www.stopbullying.gov/cyberbullying/how-to-report
- Tổng đài quốc gia bảo vệ trẻ em 111: https://tongdai111.vn/tin/so-dien-thoai-bao-ve-tre-em

> Các nguồn định hướng nội dung, không thay thế tham vấn chuyên gia, nghiên cứu người dùng trực tiếp hoặc quy trình xác nhận với trường học. Chi tiết kỹ thuật tương lai xem `06-FUTURE-TECHNICAL-ARCHITECTURE.md`.
