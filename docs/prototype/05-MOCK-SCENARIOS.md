# MoodPrint — Mock Data, Scenario Library & AI Demonstrations

> 07/11/2026 • Dữ liệu **100% hư cấu** • Không dùng tên/ảnh/tài khoản/screenshot thật của trẻ em. Tài liệu là **contract dữ liệu demo**, không phải code, không triển khai OCR/AI/voice thật.

## 1. Nguyên tắc thiết kế mock

- Seed dữ liệu **deterministic** (cùng seed → cùng trạng thái ban đầu), với `scenarioId` ổn định, timestamp rõ và quan hệ khóa nhất quán.
- Phân biệt `user_entered`, `mock_extracted`, `user_confirmed`, `inferred`, `unknown`; suy luận AI **không** được tự trở thành fact.
- Tránh tên cá nhân/trường thật, không dùng ảnh/hội thoại người thật; sử dụng tên giả như An, Minh, Hà, Linh, **Trường Mẫu A**.
- Học sinh không được xem dữ liệu của persona khác; đổi persona trong debug demo phải reset/đổi scope.
- Student và School Admin dùng 2 kho mock tách biệt; thống kê Admin không suy ra từ `studentCases`.
- Mọi tính năng giả lập có `demo: true`, nhãn UI rõ; không hiển thị “đã gửi đến trường” ngoài giả lập có qualifier.
- Case status cá nhân (`active, monitoring, closed`) khác request status demo (`draft, prepared, demo_submitted, demo_reviewing, demo_closed`).
- Fixture text dùng trong demo AI phải có expected outputs và expected **non-actions** để đánh giá cả hành vi không phù hợp.

## 2. Bảng scenario catalog — 30 tình huống

| ID | Độ tuổi | Nhóm | Tóm tắt kịch bản hư cấu | Điểm học / tính năng ưu tiên | Nhãn diễn giải |
|---|---|---|---|---|---|
| SC-01 | 12 | Verbal | Gọi biệt danh mà bạn không thích trong 2 tuần | Chat → hỏi tần suất → case | dấu hiệu có thể lặp lại |
| SC-02 | 13 | Verbal | Một lần tranh cãi trong giờ ra chơi | KB → phân biệt mâu thuẫn | không đủ căn cứ gán nhãn |
| SC-03 | 14 | Social | Bị loại khỏi nhóm làm bài, nhiều lần không được giải thích | case + timeline | sự kiện và giả thuyết riêng |
| SC-04 | 15 | Physical | Bị xô đẩy ở hành lang sau giờ học | hỗ trợ an toàn → ghi nhận | ưu tiên an toàn |
| SC-05 | 15 | Online | Bị chế giễu trên nhóm lớp | screenshot analysis | nhiều nguồn |
| SC-06 | 16 | Online | Tài khoản mạo danh đăng bài làm người khác hiểu lầm | KB + evidence | không tự truy tìm danh tính |
| SC-07 | 14 | Threat | Nhận tin nhắn dọa gặp sau giờ học | urgent/support | không khuyến khích tự đối mặt |
| SC-08 | 15 | Multi-source | 8 ảnh chụp nhóm chat trong 5 ngày + lời kể ở lớp | flagship AI analysis | trace source + uncertainty |
| SC-09 | 17 | Online | Bị lan truyền ảnh riêng tư không mong muốn | support + evidence | không sao chép/hiển thị lại ảnh nhạy cảm |
| SC-10 | 13 | Peer pressure | Bị ép tham gia trò đùa nhắm vào một bạn khác | bystander | lựa chọn rút khỏi hành vi hại người |
| SC-11 | 14 | Bystander | Thấy bạn bị cô lập nhưng sợ bị liên lụy | KB + prepare report | hỗ trợ an toàn |
| SC-12 | 16 | Communication | Muốn nói với giáo viên nhưng sợ không được tin | teacher roleplay | nêu sự việc và yêu cầu |
| SC-13 | 12 | Communication | Sợ bố mẹ phản ứng mạnh khi kể chuyện | parent roleplay | người lớn đáng tin cậy khác |
| SC-14 | 15 | Communication | Giáo viên cần nghe nhiều chi tiết nhưng em nhớ không rõ | roleplay neutral | phân biệt điều nhớ và không nhớ |
| SC-15 | 16 | Communication | Đã nhờ giúp một lần nhưng chưa có phản hồi | plan + follow-up | theo dõi tiến triển, không đổ lỗi |
| SC-16 | 17 | Online | Lời đồn tiếp diễn qua hai nền tảng | cross-source timeline | dữ kiện theo nguồn |
| SC-17 | 11 | Language | Không hiểu khái niệm “bắt nạt” | KB elementary mode | ngôn ngữ đơn giản |
| SC-18 | 13 | Social | Một nhóm không rủ vào hoạt động; chưa rõ có chủ ý | AI clarification | tránh suy đoán động cơ |
| SC-19 | 14 | Online | Người lạ comment ác ý một lần | KB + blocking | thiếu dấu hiệu school-bullying, vẫn cần hỗ trợ |
| SC-20 | 15 | Repetition | Lời nói xúc phạm kéo dài qua nhiều tháng | case ongoing | timeline dài hạn |
| SC-21 | 12 | Missing data | Nhớ chuyện nhưng không nhớ chính xác ngày | flexible case form | time precision |
| SC-22 | 17 | Conflicting data | Ảnh chụp thể hiện giờ khác lời kể | OCR confirmation | mâu thuẫn, không ép sửa một chiều |
| SC-23 | 14 | Evidence | Hai screenshot bị trùng | dedup preview | cần rà soát, không nhân đôi tần suất |
| SC-24 | 15 | Safety | Em nói đang sợ đi một mình ngay bây giờ | urgent exit | hướng đến giúp đỡ trực tiếp |
| SC-25 | 16 | Wellbeing | Sự việc ảnh hưởng ngủ và học | support/plan | không chẩn đoán bệnh |
| SC-26 | 14 | School | Muốn viết báo cáo bằng bí danh | support composer | không hứa tuyệt đối ẩn danh |
| SC-27 | 13 | School | Muốn biết “trường đã nhận chưa” | request demo status | luôn nói chưa gửi thật |
| SC-28 | 17 | Self-reflection | Em đã phản ứng nóng nảy và muốn sửa cách nói | roleplay | trách nhiệm hành động, không phán xét |
| SC-29 | 15 | Knowledge | Không biết cách báo nội dung trên mạng xã hội | KB/platform links | hướng dẫn chính thống, kiểm tra URL |
| SC-30 | 16 | Progress | Sau 2 tuần muốn nhìn lại các bước đã làm | home/case plan | không nhầm tick checklist với đã giải quyết |

**Tỷ lệ kiểm thử mục tiêu:** ít nhất 6 nhóm online, 5 offline, 4 liên quan giao tiếp, 4 thiếu/không rõ chứng cứ, 3 người chứng kiến, 3 cần hỗ trợ khẩn; các nhóm có thể trùng nhau. Không phải kết quả thu thập thực tế.

## 3. Seed account/persona mock

| ID | Nickname | Nhóm tuổi | Role | Trạng thái khởi đầu | Ghi chú |
|---|---|---|---|---|---|
| USER-AN | An | 11–13 | student | 1 case active, 2 bookmarks | Persona mặc định khi mở demo |
| USER-MINH | Minh | 14–17 | student | 2 case active, 1 chat multi-image | Demo phân tích screenshot |
| USER-HA | Hà | 14–17 | student | 1 case monitoring, 1 plan | Demo timeline và follow-up |
| USER-LINH | Linh | 14–17 | student | 1 case witness | Demo hỗ trợ người chứng kiến |
| ADMIN-DEMO | Quản trị giả lập | adult | school-demo-only | synthetic reports | Tuyệt đối không đọc student store |

Mock login chỉ chọn persona hoặc nhập nickname; không tạo danh tính thật hay gửi credential.

## 4. Data contracts — canonical mock entities

### 4.1 `Case`

| Field | Type/enum concept | Example | Validation |
|---|---|---|---|
| `id` | stable string | `CASE-MINH-001` | unique |
| `ownerId` | DemoUser ID | `USER-MINH` | student only |
| `title` | string | `Nhóm chat lớp` | 3–80 ký tự, có thể trung tính |
| `template` | enum | `online_threat` | chọn từ template list |
| `perspective` | `self / witness` | `self` | required |
| `summary` | string | lời kể ngắn | có thể là bản nháp |
| `categoryTags` | array | `online,verbal,threat` | đa nhãn |
| `status` | draft/active/monitoring/closed | `active` | user-controlled |
| `impactTags` | array | `unsafe,school_concentration` | optional |
| `events` | IDs | `EV-...` | liên kết timeline |
| `evidenceIds` | IDs | `MEDIA-01` | nhiều nguồn |
| `linkedChatIds` | IDs | `CHAT-...` | optional |
| `linkedPlanId` | string/null | `PLAN-A` | optional khi hồ sơ chưa tạo kế hoạch; tính năng lõi #3 đã chốt |
| `createdAt,updatedAt` | ISO datetime | synthetic | không phải giờ thực của học sinh |

### 4.2 `Evidence` & `ObservedClaim`

| Field | Ví dụ | Ý nghĩa |
|---|---|---|
| `evidenceId` | `MEDIA-03` | Định danh media mock |
| `caseId` | `CASE-MINH-001` | Liên kết vụ việc |
| `kind` | `screenshot / text_note / pdf_placeholder` | Loại bằng chứng |
| `origin` | `mock_fixture / user_entered` | Xuất xứ |
| `mockAssetPath` | `fixtures/messenger_03.svg` | Dùng asset hư cấu, không tải từ mạng |
| `capturedAt` | `unknown` | Thời điểm chụp (không tự suy ra) |
| `shownTimestamp` | `2026-10-13T20:10:00+07:00` | Thời gian nhìn thấy trong ảnh (nếu có) |
| `extractedText` | đoạn mẫu | Text dựng sẵn, chưa xác nhận |
| `reviewStatus` | `unreviewed / corrected / confirmed / rejected` | Người dùng duyệt |
| `limitations` | `cropped/blurred/unknown_author` | Giới hạn thông tin |
| `claimIds` | `OBS-01..` | Liên kết nhận định |

**`ObservedClaim`**: `claimId`, `statement`, `kind: observed|inferred|unknown`, `sourceEvidenceIds[]`, `confidenceLabel: clear|partial|unknown` (chỉ nhãn trực quan, **không** gán xác suất giả), `userVerified:boolean`, `notes`. Nếu user sửa `extractedText`, giữ lịch sử mock `originalText` và `userEditedText` trong state để không đổi nguồn ban đầu.

### 4.3 `TimelineEvent`, `Plan`, `Chat`, `SupportRequest`

- **TimelineEvent:** `id, caseId, when, timePrecision(exact/day/week/unknown), place, description, provenance(user_entered/mock_extracted/user_confirmed), evidenceIds, needsReview`.
- **ActionPlan:** `id, caseId, goal, chosenOptionId, items[{id,label,status:not_started|doing|done,notes}], nextReviewDate, lastUpdated`.
- **ChatSession:** `id, ownerId, linkedCaseId?, scenarioId, messages[{id,speaker:user|ai|system,body,sourceIds,actionChips}], cursor`, không lưu private raw data trong mock.
- **RoleplaySession:** `id, role:teacher|parent, tone:gentle|neutral|respectfully_challenging, scenarioId, mode:text|voice_demo, turns, cursor, feedback`.
- **KnowledgeArticle:** `id,slug,title,summary,topics,ageBands,readMinutes,sections,scenarioLinks,sourceIds,lastReviewed,applicability`.
- **SupportDraft:** `id,ownerId,caseId?,recipientType,identityMode:alias|disclose,content,previewVisibleFields,status:draft|prepared|demo_submitted,createdAt`.
- **SchoolDemoReport:** `id,syntheticCaseType,syntheticDate,schoolGroupLabel,status,handledByRole,syntheticEvents`, không có `studentCaseId`/`ownerId`.

## 5. Flagship fixture: 8 Messenger-style screenshots `SC-08`

> **Bối cảnh hoàn toàn giả:** Trong nhóm chat lớp, một số tài khoản tên giả bình luận gây khó chịu và có tin nhắn hàm ý dọa gặp. Sự việc diễn ra trên nhiều ngày. Nội dung dưới đây chỉ mô tả những gì mock “đọc” được; không coi là xác minh danh tính hay sự thật.

| Media ID | Ngày giờ hiển thị (ICT) | Nội dung *tóm tắt* trong ảnh giả | Tình trạng | Claim mong đợi |
|---|---|---|---|---|
| MEDIA-01 | 12/10 19:40 | Một bạn gọi Minh bằng biệt danh Minh không thích | readable | ghi nhận phát ngôn, chưa kết luận chủ ý |
| MEDIA-02 | 12/10 20:04 | Có biểu tượng cười theo sau lời trêu chọc | partial | không suy diễn ai tham gia/đồng tình |
| MEDIA-03 | 13/10 20:10 | Tin nhắn: “Ngày mai ra cổng gặp tụi mình.” | readable | nhận diện có thể đáng lo; hỏi cảm giác an toàn |
| MEDIA-04 | 13/10 20:13 | Ảnh cắt mất phần đầu cuộc chat | cropped | thiếu ngữ cảnh, đánh dấu uncertainty |
| MEDIA-05 | 14/10 21:02 | Tiếp tục gọi biệt danh cũ | readable | pattern across dates, cần user xác nhận |
| MEDIA-06 | 15/10 18:33 | Một bạn khác nhắn “Đừng làm vậy nữa.” | readable | có người phản đối; không suy ra an toàn đã được bảo đảm |
| MEDIA-07 | 16/10 19:55 | Nhiều tin nhắn trong nhóm nhưng tên người gửi bị che | partial | không gán danh tính |
| MEDIA-08 | 16/10 không rõ giờ | Ảnh gần trùng nội dung MEDIA-07 | possible_duplicate | nhắc user xem lại, không nhân đôi event |

### Kết quả analysis mock có cấu trúc

**Điều quan sát:** có lời gọi biệt danh ở MEDIA-01/05, lời nhắn hẹn ở MEDIA-03, một phần hội thoại bị cắt ở MEDIA-04, một câu phản đối ở MEDIA-06. **Dấu hiệu cần xem xét:** sự lặp lại của lời trêu chọc; câu hẹn gặp có thể gây lo lắng tùy ngữ cảnh. **Điều chưa rõ:** đó là lời đe dọa hay lời hẹn khác, ai gửi các tin bị che, ở lớp có sự việc tương ứng hay không. **Bước kế tiếp:** hỏi tình trạng an toàn hiện tại, gợi ý lưu nội dung đã xác nhận, chuẩn bị tìm người đáng tin cậy; nếu đang bị đe dọa ngay lúc này thì ưu tiên đường tìm trợ giúp.

### Luồng xác nhận

1. Chỉ khi user nhấn `Xác nhận nội dung` thì `mock_extracted → user_confirmed`.
2. MEDIA-04/07/08 bị gắn `needsReview` mặc định.
3. Timeline có thể hiển thị `12/10`, `13/10`, `14/10`, `15/10`, `16/10` nhưng không có nhận định “đều bị bắt nạt hàng ngày” nếu chưa có bằng chứng.
4. Câu hỏi có thể xuất hiện: “Bạn có thấy an toàn hôm nay không?”, “Đây có phải nhóm bạn cùng lớp không?”, “Bạn muốn người nào biết chuyện này?”.
5. Không tự chuyển screenshot cho giáo viên, không tìm/đăng tải tên tài khoản trong ảnh, không tự liên hệ nền tảng.

## 6. 12 multi-turn chat fixtures

| ID | Scenario | Lượt 1 | Câu hỏi làm rõ | Kết quả/CTA |
|---|---|---|---|---|
| CHAT-01 | SC-01 | “Các bạn gọi mình bằng tên mình ghét.” | “Chuyện này xảy ra nhiều lần không?” | case template + KB |
| CHAT-02 | SC-02 | “Mình vừa cãi nhau với bạn.” | “Chuyện đã xảy ra mấy lần?” | chưa đủ để gán nhãn; cách nói lại |
| CHAT-03 | SC-08 | 8 screenshot fixture | “Bạn có thấy an toàn hôm nay không?” | analysis + verify + case |
| CHAT-04 | SC-03 | “Mình không được tham gia nhóm.” | “Điều này xảy ra lần đầu hay thường xuyên?” | timeline + câu hỏi chưa rõ |
| CHAT-05 | SC-07 | “Có bạn hẹn mình sau giờ học, mình sợ.” | “Bạn có đang ở nơi an toàn không?” | help now + người lớn tin cậy |
| CHAT-06 | SC-11 | “Mình thấy bạn bị bắt nạt.” | “Bạn có thể tìm ai lớn để nói chuyện?” | bystander article + prepare |
| CHAT-07 | SC-13 | “Mình sợ kể với mẹ.” | “Có người lớn nào khác bạn tin tưởng không?” | parent roleplay / trusted adult |
| CHAT-08 | SC-19 | “Người lạ nói xấu mình một lần.” | “Có liên quan trường lớp và lặp lại không?” | platform reporting guidance, không dán nhãn |
| CHAT-09 | SC-21 | “Không nhớ ngày xảy ra.” | “Bạn nhớ khoảng thời gian hay tiết học nào không?” | tạo case timePrecision=unknown |
| CHAT-10 | SC-22 | “Ảnh ghi khác thời gian mình nhớ.” | “Bạn muốn giữ cả hai thông tin để kiểm tra lại?” | discrepancy card |
| CHAT-11 | SC-25 | “Mình khó ngủ vì chuyện ở trường.” | “Bạn muốn kể thêm hay tìm người hỗ trợ?” | support options, không chẩn đoán |
| CHAT-12 | SC-30 | “Tuần trước mình đã nhờ cô giúp.” | “Cô đã phản hồi điều gì?” | update plan/check-in |

**Mỗi chat fixture** cần transcript 4–8 message, `actionChips` sau ít nhất một lượt, `unknowns[]` rõ. Nếu user nhập ngoài nhánh, mock fallback trung thực: “Trong bản demo này mình chỉ có một số tình huống mẫu. Bạn có thể chọn tình huống gần nhất hoặc lưu nội dung vào nháp.” Không giả AI tự hiểu mọi câu tùy ý.

## 7. 6 roleplay scripts chi tiết

### RP-TEACHER-01 — Lần đầu kể với giáo viên (SC-12)

- **Mục tiêu:** kể sự việc và yêu cầu giúp đỡ.
- **AI teacher 1:** “Em muốn cô biết chuyện gì đang xảy ra?”
- **User option A:** “Các bạn hay chế giễu em trong nhóm lớp.”
- **AI teacher 2:** “Em nhớ một ví dụ gần đây nhất không?”
- **User option B:** “Hôm thứ Hai có tin nhắn như vậy, em đã chụp lại.”
- **AI teacher 3:** “Em mong cô hỗ trợ cụ thể điều gì trước?”
- **User option C:** “Em muốn cô giúp tìm cách để chuyện này dừng lại và giữ kín những phần em chưa sẵn sàng chia sẻ.”
- **Feedback:** có vấn đề, ví dụ và yêu cầu; gợi ý bổ sung mốc thời gian hoặc cách liên hệ tiếp.

### RP-TEACHER-02 — Người nghe hỏi kỹ nhưng tôn trọng (SC-14)

- Teacher hỏi “Vậy em nhớ chính xác ngày nào?”; user chọn “Em không chắc, em chỉ nhớ khoảng giữa tuần.”
- Teacher ghi nhận chưa rõ, hỏi “Em còn bằng chứng hay ai có thể xác nhận phần em nhớ không?”
- Feedback khuyến khích nói trung thực về chỗ không nhớ; không thưởng cho việc bịa ngày để làm câu chuyện trông chắc chắn.

### RP-TEACHER-03 — Chuẩn bị trao đổi lần hai (SC-15)

- Roleplay tập câu mở: “Em muốn hỏi mình có thể cập nhật về việc đã trao đổi tuần trước không?”
- Học cách nêu điều chưa cải thiện, mong muốn trao đổi tiếp và lựa chọn người hỗ trợ khác nếu cần.
- Không mô phỏng nhà trường đã xử lý thật.

### RP-PARENT-01 — Nói với bố mẹ khi ngại (SC-13)

- Parent mở nhẹ nhàng: “Con có điều gì muốn kể với bố/mẹ không?”
- User: “Con đang gặp chuyện ở lớp, con chưa biết bắt đầu từ đâu.”
- Parent hỏi “Điều gì làm con thấy khó khăn nhất?”
- User nêu một sự việc và mong muốn “Con muốn bố/mẹ nghe hết trước khi quyết định.”
- Feedback: mở đầu rõ, nêu điều mong muốn, chưa cần kể mọi chi tiết ngay.

### RP-PARENT-02 — Khi người nghe chưa hiểu (SC-13)

- Parent hỏi “Có phải các bạn chỉ đùa thôi không?” một lần, **không lặp phản ứng phủ nhận**.
- User tập cách đáp: “Con biết có thể bố/mẹ chưa rõ, nhưng chuyện này làm con sợ và đã lặp lại; con muốn mình cùng xem lại.”
- Feedback: mô tả ảnh hưởng và yêu cầu cụ thể; có option luyện với một người lớn khác.

### RP-SUPPORT-01 — Người chứng kiến báo sự việc (SC-11)

- Adult hỏi “Em chứng kiến chuyện gì, và điều gì em chưa rõ?”
- User nêu điều thực sự thấy, không suy đoán ý định.
- Adult hỏi “Có ai ở gần có thể hỗ trợ ngay không?”
- Feedback về phân biệt chứng kiến/được kể lại; không khuyến khích tự đối đầu.

**Rubric chung (không chấm điểm con người):** `specificity`, `time_context`, `ask_for_help`, `uncertainty_honesty`, `respectful_self_expression`. Feedback gồm 1 điều đã làm rõ, 1 chỗ có thể bổ sung, 1 mẫu câu để thử. Tất cả scripts có mode `text` và `voice_demo` dùng cùng transcript.

## 8. Incident templates (8 mẫu)

| Template ID | Tên hiển thị | Prefill fields | Câu hỏi hữu ích |
|---|---|---|---|
| TPL-VERBAL | Trêu chọc/xúc phạm | mô tả, lặp lại, người có mặt | “Điều này xảy ra lần gần nhất khi nào?” |
| TPL-THREAT | Tin nhắn đe dọa | nội dung, nền tảng, thời điểm, an toàn hiện tại | “Bạn đang ở nơi an toàn chứ?” |
| TPL-EXCLUSION | Bị cô lập/tẩy chay | diễn biến, nhóm, thời lượng | “Việc này xảy ra một lần hay nhiều lần?” |
| TPL-PHYSICAL | Xô đẩy/động chạm | địa điểm, thời gian, ảnh hưởng, người hỗ trợ | “Hiện có ai có thể giúp bạn an toàn?” |
| TPL-IMAGE | Ảnh bị chia sẻ không mong muốn | nguồn, ảnh hưởng, link nền tảng | “Bạn muốn tìm hướng dẫn báo nội dung không?” |
| TPL-IMPERSONATION | Mạo danh | tài khoản, bài đăng, mốc giờ | “Bạn đã giữ lại link/screenshot chưa?” |
| TPL-WITNESS | Mình chứng kiến | điều mắt thấy, ai có thể hỗ trợ | “Phần nào bạn trực tiếp thấy?” |
| TPL-FREE | Mẫu tự do | mô tả chung | “Bạn muốn bắt đầu từ điều gì?” |

Các trường optional gồm `occurredAt`, `place`, `people`, `evidence`, `impact`; bắt buộc tối thiểu mô tả sự việc để hoàn tất case, còn nháp được rỗng phần lớn.

## 9. Knowledge Hub mock content inventory

24 bài/bộ nội dung đề xuất, mỗi item cần `id`, `slug`, `format`, `tags`, `ageBands`, `sourceIds`, `lastReviewed`, `reviewStatus`.

| KB ID | Chủ đề | Format | Nguồn ưu tiên |
|---|---|---|---|
| KB-01 | Bắt nạt là gì? | FAQ | StopBullying.gov |
| KB-02 | Trêu đùa, mâu thuẫn, bắt nạt khác nhau ra sao? | scenario | UNICEF/StopBullying.gov |
| KB-03 | Bị gọi biệt danh liên tục | guide | UNICEF/NSPCC |
| KB-04 | Khi bị cô lập trong lớp | guide | NSPCC |
| KB-05 | Khi xảy ra xô đẩy | checklist | WHO/UNESCO |
| KB-06 | Bắt nạt online là gì? | FAQ | UNICEF Việt Nam |
| KB-07 | Tin nhắn đe dọa: nên ghi nhận gì? | checklist | UNICEF/StopBullying.gov |
| KB-08 | Lưu screenshot có ngữ cảnh | how-to | StopBullying.gov |
| KB-09 | Chặn/báo cáo nội dung trên nền tảng | how-to | StopBullying.gov |
| KB-10 | Khi có tài khoản mạo danh | guide | UNICEF/NSPCC |
| KB-11 | Tin đồn và bài đăng làm nhục | guide | UNICEF |
| KB-12 | Ảnh bị chia sẻ không mong muốn | guide | UNICEF/NSPCC |
| KB-13 | Nói chuyện với giáo viên | template | UNICEF/WHO Teaching with Care |
| KB-14 | Nói chuyện với bố mẹ | template | UNICEF |
| KB-15 | Nếu lần đầu nhờ giúp chưa hiệu quả | guide | UNICEF/NSPCC |
| KB-16 | Người chứng kiến có thể làm gì? | scenario | UNICEF/NSPCC |
| KB-17 | Khi không chắc chuyện gì xảy ra | FAQ | StopBullying.gov |
| KB-18 | Chọn người lớn đáng tin cậy | checklist | UNICEF |
| KB-19 | Viết bản tóm tắt trung tính | template | UNICEF |
| KB-20 | Tự chăm sóc khi đang lo lắng | guide | WHO Teaching with Care |
| KB-21 | Kênh trợ giúp trẻ em tại Việt Nam | directory | Tổng đài 111 |
| KB-22 | Quy trình theo dõi một sự việc | how-to | WHO handbook |
| KB-23 | Đề xuất hành động an toàn | mini quiz | UNICEF/NSPCC |
| KB-24 | Bảo vệ bạn bè online | mini quiz | UNICEF |

Không tự gán trích dẫn chi tiết nếu chưa rà soát nội dung từng nguồn; inventory chỉ là kế hoạch biên tập. Đối với `KB-09`, link hướng dẫn report cụ thể từng nền tảng cần xác nhận khi triển khai nội dung.

## 10. Support mock fixtures

| ID | Type | Label | Interaction | Giới hạn |
|---|---|---|---|---|
| HELP-111 | official hotline | Tổng đài 111 | `tel:111`, website chính thức | Mở ngoài ứng dụng; không tự gọi |
| HELP-TEACHER | trusted person | Giáo viên bạn tin tưởng | chuẩn bị tin nhắn | Không gửi thật |
| HELP-PARENT | trusted person | Phụ huynh/người chăm sóc | roleplay + draft | Không bắt buộc lựa chọn |
| HELP-OTHER | trusted person | Người lớn đáng tin cậy khác | draft | Không thu danh bạ thật |
| HELP-SCHOOL-DEMO | demo intake | Gửi báo cáo mẫu tới trường giả | `demo_submitted` | Không kết nối trường thật |
| HELP-PLATFORM | reporting guide | Hướng dẫn báo nội dung mạng xã hội | mở KB/link source | Không thao tác thay user |

**SupportDraft ví dụ:** người nhận `Giáo viên chủ nhiệm (mô phỏng)`; `identityMode=alias`; nội dung gồm `Tôi muốn trình bày một sự việc...`; UI chèn disclaimer không gửi thật. Khi đổi sang `disclose`, chỉ hiện nickname demo nếu không có tên thật.

## 11. School Admin Demo dataset hoàn toàn riêng

- Trường giả: **Trường Mẫu A**; không dùng tên trường có thật.
- Tập dữ liệu khoảng **48 report giả** từ 3 tháng giả định; category distribution giả `online 15, verbal 12, social 10, physical 6, other 5` (tổng =48).
- Status distribution giả `new 9, reviewing 18, follow_up 13, closed 8` (tổng =48).
- Đồ thị tuần/tháng từ `schoolDemoReports`; seed cố định bảo đảm KPI/chart/list khớp nhau.
- Dữ liệu chi tiết chỉ gắn `syntheticReporterCode`, khoảng thời gian, category, mô tả 1–2 câu không định danh, role xử lý giả; **không gắn bất kỳ ownerId student nào**.
- Filter month/category/status thay KPI/biểu đồ/report table đồng bộ theo cùng collection; không fake numbers riêng trên từng widget.
- Banner `Dữ liệu mô phỏng` ở list/detail/export preview, có legend chart `Giả lập`.

## 12. Mock behavior & testing controls

- Scenario selector ở môi trường demo để nhanh chuyển `SC-01 ... SC-30`, nhưng không để ngầm đổi data người dùng.
- Một nút `Khôi phục dữ liệu mẫu` (confirm), không có tài khoản thật để xóa.
- Mock processing states: `idle → processing_demo → review → confirmed/failed_demo`, có khả năng `retry`.
- Không có random AI response hoặc network calls; chat script theo state machine. Nếu text ngoài nhánh, đưa câu trả lời fallback trung thực, gợi ý làm việc với fixture, không giả AI phân tích tự do.
- Thêm Error injection giả trong Dev Demo Panel: missing image, duplicate media, article not found, long filename, empty search, failed save, no script.

## 13. Acceptance matrix cho mock

| Test ID | Input | Expected | Không được xảy ra |
|---|---|---|---|
| M-01 | CHAT-02, mâu thuẫn một lần | UI nói chưa đủ thông tin | gán nhãn bắt nạt chắc chắn |
| M-02 | MEDIA-01..08 | OCR fixture có source/time | tự kết luận danh tính người gửi |
| M-03 | MEDIA-08 duplicate | cảnh báo trùng | đếm hai mốc độc lập |
| M-04 | MEDIA-04 cropped | label chưa rõ | khẳng định toàn bộ context |
| M-05 | SC-07 urgent | có help now ngay | khuyến khích đối đầu/gặp riêng |
| M-06 | SC-21 unknown date | save được với timePrecision=unknown | bịa ngày |
| M-07 | Roleplay parent | kết thúc + feedback | AI mắng chửi user |
| M-08 | Support alias mode | preview dùng bí danh | hứa ẩn danh tuyệt đối |
| M-09 | Demo submit | “đã lưu mô phỏng, chưa gửi” | “trường đã nhận” |
| M-10 | Student → Admin Demo | không lộ student store | bản ghi thật hiện trong Admin |
| M-11 | Reset demo data | khôi phục seed/confirm | xóa gì trên server |
| M-12 | KB bài chi tiết | có nguồn + phạm vi áp dụng | cite mơ hồ hoặc bịa link |

## 14. Asset manifest đề xuất

- `avatars/companion.svg`, `illustrations/welcome_*.svg`, `illustrations/roleplay_teacher.svg`, `illustrations/roleplay_parent.svg`, `fixtures/messenger_01.svg` ... `messenger_08.svg`, `placeholders/evidence-file.svg`.
- `mockUsers`, `mockCases`, `mockEvents`, `mockEvidence`, `mockAnalyses`, `mockChats`, `mockRoleplays`, `mockKnowledge`, `mockSupport`, `mockSchoolAdmin` là collection độc lập có quan hệ ID nhất quán.
- Dữ liệu ảnh đính kèm trong quá trình demo nên tạo object URL tạm thời hoặc ảnh giả local trong frontend; không upload cloud.
