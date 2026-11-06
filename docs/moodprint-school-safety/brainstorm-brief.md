# MoodPrint School Safety: bản mô tả để brainstorm

Cập nhật ngày 06/11/2026. File này tự đủ ngữ cảnh, người đọc không cần xem repo.

## Cách dùng file này

Bạn đang đọc bản mô tả một sản phẩm đang ở giai đoạn lập kế hoạch. Hãy đóng vai một người phản biện giỏi về sản phẩm cho trẻ vị thành niên và về AI agent.

- Trả lời bằng tiếng Việt, giữ nguyên thuật ngữ kỹ thuật tiếng Anh.
- Mục 12 ghi các quyết định đã chốt. Đừng đề xuất lại, trừ khi có lý do mạnh và nêu rõ lý do đó.
- Phản biện thẳng. Chỉ ra chỗ yếu, chỗ thừa, chỗ dễ hỏng khi trình bày. Đừng chỉ khen.
- Mỗi đề xuất cần nói rõ đổi gì, được gì, tốn gì.
- Mục 15 là các câu hỏi cần brainstorm.

## 1. Tóm tắt

MoodPrint là dự án startup ở chương trình tiền ươm tạo, trước đây là ứng dụng nhật ký cảm xúc có nhiều trợ lý AI. Dự án đang chuyển hướng thành **ứng dụng giúp học sinh 11–17 tuổi đối mặt với bạo lực học đường và tìm tới được một người lớn thật**, để dự thi P-Innovation 2027.

Sản phẩm có một trợ lý AI duy nhất tên "Trợ lý", một hồ sơ lưu sự việc và bằng chứng, chức năng luyện nói trước khi nói chuyện với người lớn, và luồng khẩn cấp không phụ thuộc AI.

**Tình trạng**: kế hoạch đã xong, **chưa viết dòng code nào của sản phẩm mới**. Đợt này là bản release thật chạy model thật để trình bày, với nội dung hư cấu. Chưa có học sinh thật dùng.

## 2. Bài toán

**Người dùng**: học sinh 11–17 tuổi ở Việt Nam, chia hai nhóm ngôn ngữ 11–14 và 15–17. Viết teencode, không dấu, câu cụt, hay nói giảm, nói gián tiếp.

**Nỗi đau**:

- Bị bắt nạt trên mạng, bị chặn đường đòi tiền, chứng kiến bạn bị đánh, bị đe dọa bằng ảnh riêng tư, hoặc người gây hại là người lớn.
- Không biết chuyện đó có nghiêm trọng không, không biết nói với ai, nói thế nào.
- Sợ bị trả thù, sợ bị lộ, sợ bị coi là mách lẻo.
- Không biết lưu bằng chứng ngay từ đầu.
- Khi cần gấp thì không biết gọi đâu.

**Thước đo thành công**: em tới được một người lớn thật, không phải số tin nhắn hay thời gian dùng app. AI không thay người thật và không tự báo cho ai.

**Tình huống đại diện**:

- Minh An, 12 tuổi: một nhóm bạn lập group nói xấu và chế ảnh. Trợ lý hiểu chuyện, giúp lưu sự việc, luyện cách mở lời, soạn tin cho cô chủ nhiệm, xuất PDF.
- Tuấn Khang, 15 tuổi: bị nhóm trường khác chặn đường đòi tiền, sợ bị trả thù. Tin "thằng kia còn khoe con dao trong cặp" phải kích hoạt khẩn cấp ngay, không gọi model.
- Hà Linh, 13 tuổi: thấy bạn bị đánh và quay clip, muốn giúp nhưng sợ lộ.
- Bảo Nam, 16 tuổi: người gây hại là thầy chủ nhiệm. Trợ lý không được gợi ý nói với chính người đó.
- Một câu khó: "dạo này mình mệt quá, chắc biến mất thì mọi người nhẹ đầu hơn". Regex không bắt được, classifier phải hiểu là tín hiệu tự hại.

## 3. Hiện trạng kỹ thuật

**Nền tảng**: FastAPI dạng modular monolith, một worker, React 19 và Vite, Supabase cho PostgreSQL, Auth, Storage, chạy trên một máy EC2 với Caddy và Docker Compose. Agent dùng `openai-agents` 0.24.0.

**Đang tốt**: hơn 2.150 test backend và gần 400 test giao diện pass, có accounting chi phí AI theo từng lượt, SSE streaming, idempotency, upload trực tiếp lên Storage, chế độ khách ẩn danh tự xóa sau 2 giờ, pipeline release tự động có kiểm tra chữ ký.

**Đang thiếu**:

- Chat hiện chỉ có regex tự hại. Bộ thử cho thấy nó bỏ sót "nó bảo mai mang dao đến" và mọi câu về xâm hại, tống tiền, thương tích.
- CI của nhánh làm việc đang đỏ vì một lỗi accessibility nhỏ ở code cũ. Bản sửa đã có, chỉ cần đưa vào nhánh.
- Chưa có hồ sơ sự việc, knowledge base, TTS, nút khẩn cấp, người lớn tin cậy, kế hoạch an toàn.
- Trạng thái runtime nằm trong RAM của một process, nên không scale ngang được. Ở quy mô hiện tại thì chấp nhận được.
- Dưới cấu hình có trần chi phí, khách không dùng được giọng nói và chỉ khoảng 3 lượt chạy đồng thời. Plan đã có task sửa.

**Hệ thống cũ** gồm nhiều bot, group chat, proactive messaging, matching. Tất cả được đóng băng và ẩn đi bằng cấu hình `APP_PROFILE=school_safety`, không xóa, để các test cũ vẫn xanh.

## 4. Sản phẩm

Khung ứng dụng có 4 tab: **Trò chuyện, Hồ sơ, Luyện nói, Hỗ trợ**. Trên cùng luôn có hai nút:

- **Khẩn cấp**: mở các số 111 (bảo vệ trẻ em), 113, 115, chạy được khi mất mạng và không cần đăng nhập.
- **Thoát nhanh**: một chạm, xóa cache, chuyển sang trang trung tính, nút Back không quay lại nội dung.

Có thể đổi tên tab thành "Sổ tay" để người xung quanh không nhận ra.

**Vào app**: khách bấm "Dùng thử ngay" là vào chat, không hỏi tuổi, không có màn điều khoản, không thấy CAPTCHA. Dữ liệu khách tự xóa sau 2 giờ. Đăng ký tài khoản đóng trong đợt này. Phần hồ sơ nhiều ngày dùng một tài khoản trình bày có sẵn dữ liệu hư cấu.

**Sáu luồng nghiệp vụ** là state machine ở backend. Model chỉ đề xuất, backend quyết định chuyển bước:

| Luồng | Việc |
| --- | --- |
| WF-01 Hiểu tình huống | Phản chiếu, hỏi tối đa một câu mỗi lượt, tóm tắt có cấu trúc |
| WF-02 Ghi sự việc | Tạo hồ sơ, thêm sự việc, bằng chứng |
| WF-03 Kế hoạch an toàn | Kế hoạch từ template, hướng dẫn báo cáo trên nền tảng |
| WF-04 Nói với người lớn | Chọn người lớn tin cậy, soạn tin, thẻ tóm tắt để gọi 111 |
| WF-05 Người chứng kiến | Việc có thể làm, không khuyên can thiệp thể chất |
| WF-06 Khẩn cấp | Giữ thẻ khẩn cấp trên mọi lời, ngắt các luồng khác |

**Nguyên tắc hành động**: tool chỉ tạo đề xuất. Người dùng bấm xác nhận mới lưu. Ứng dụng không có nút gửi tin thay em, chỉ có nút sao chép.

**Hồ sơ**: nhiều sự việc theo dòng thời gian, sửa không phá hủy bản cũ, ảnh và video có mã SHA-256 cùng thời điểm do server ghi, khóa PIN tùy chọn, dùng bí danh cho người liên quan, xuất PDF ba phần có nhãn rõ. PDF nói rõ mã hash không chứng minh chuyện đã xảy ra.

**Luyện nói**: giữ để nói, sửa bản chép lời, gửi. Ba chế độ: kể lại, nói với người lớn (AI đóng vai có nhãn rõ), chuẩn bị gọi 111. Có chế độ `challenging`, AI đáp một câu khó nghe như "Chắc con cũng có lỗi gì đó" kèm gợi ý cách đáp lại. Cuối phiên có tóm tắt điều em làm tốt.

**Thinking**: chỉ hiện giai đoạn có thật từ backend như "Đang đọc tin của em", "Đang kiểm tra lại nguồn". Không có animation trong luồng khẩn cấp.

## 5. Agent

- Một agent, không multi-agent, không handoff.
- Model chỉ dùng `gpt-6-luna`, loại nhanh và rẻ nhất của dòng GPT-6.
- `max_turns=3`, tối đa 3 model call và 2 tool call mỗi lượt, input giới hạn 48.000 byte, output 4.000 token.
- `reasoning.effort` chọn giữa `medium` và `high` theo kết quả eval.
- Tool được cấp theo trạng thái, không cấp tất cả. Có 12 tool như `classify_situation`, `propose_event`, `search_knowledge`, `draft_message`, `build_111_card`.
- Câu trả lời có cấu trúc: tin nhắn, tham chiếu nguồn, bước đề xuất, tối đa 3 gợi ý trả lời nhanh.

**Vì dùng model nhỏ, độ thông minh phải đến từ**:

- Ngữ cảnh do backend cấp: nhóm tuổi, bước hiện tại, thông tin đã biết, số lần lặp lại do backend đếm.
- Playbook mỗi luồng có 5–8 hội thoại mẫu viết tay, ít nhất 2 ca khó.
- Mô tả tool nêu rõ khi nào dùng, khi nào không.

**Hành vi mong muốn**: phản chiếu đúng chi tiết em nói rồi đưa một bước tiếp theo, tối đa một câu hỏi, hiểu teencode, không sửa cách em viết, biết khi nào không hỏi thêm, không phán xử, không chẩn đoán, không hứa bí mật tuyệt đối, không làm bạn thân, luôn hướng tới người lớn thật.

## 6. An toàn

Lớp an toàn cứng nằm ngoài model, chạy trước mọi cổng AI.

| Tầng | Việc |
| --- | --- |
| 0. Chuẩn hóa | Bỏ dấu, teencode, ghép ký tự chèn như `m.u.o.n`, rút ký tự lặp |
| 1. Rule | Rule pack tiếng Việt, không gọi mạng |
| 2. Ngữ cảnh | Ghép tín hiệu qua nhiều tin |
| 3. Classifier | Luna với timeout 3 giây, hiểu cách nói gián tiếp. Timeout thì coi như mức vàng |
| 4. Postcheck | Kiểm tra lời model trước khi hiện |
| Template | Lời khẩn cấp viết sẵn theo nhãn và nhóm tuổi, không do model sinh |
| Fail-safe | OpenAI lỗi, hết tiền, mất mạng thì rule và nút khẩn cấp vẫn chạy. Rule pack có bản chạy ngay trên trình duyệt |

**8 nhãn**: đe dọa thể chất tức thời, vũ khí, thương tích nặng, xâm hại tình dục, tự hại (mặc định đỏ); tống tiền ép buộc, người lớn gây hại, nguy cơ trả thù (mặc định vàng).

- **Đỏ**: template và thẻ khẩn cấp hiện ngay. Với nội dung tình dục, không gửi gì tới model, kể cả classifier.
- **Vàng**: agent vẫn chạy, kèm hướng dẫn thận trọng và lối vào Tìm hỗ trợ.
- **Xanh**: chạy bình thường.

**Mục tiêu eval**: bộ ≥ 300 mẫu tiếng Việt tổng hợp, recall ≥ 0,95 cho tự hại, vũ khí, xâm hại, không có ca đỏ thành xanh trong holdout, báo động nhầm đề xuất ≤ 0,10.

## 7. Knowledge base

- 40–60 thẻ đã duyệt, mỗi thẻ 80–200 từ theo nhóm tuổi, mỗi claim trỏ về nguồn. Hiện dự kiến 47 thẻ.
- Sáu nhóm: hiểu chuyện gì đang xảy ra, an toàn, bằng chứng, báo cáo, quyền lợi, hỗ trợ.
- Nguồn: Luật Trẻ em, Nghị định 80/2017, Thông tư 18/2025 và 19/2025, Tổng đài 111, UNICEF, trang trợ giúp Facebook, YouTube, TikTok.
- Truy xuất hybrid từ keyword và vector, kết hợp bằng RRF. Verifier kiểm tra claim có được thẻ ủng hộ không. Không ủng hộ thì trả câu dự phòng "Mình chưa chắc...".
- Mọi câu pháp lý phải có thẻ. Không có thẻ thì không trả lời, không tự bịa số năm tù.
- Không dùng báo chí làm nguồn. Mọi thẻ do một người duyệt.

## 8. Giọng nói

- STT là `gpt-transcribe`, TTS là `gpt-realtime-2.1-mini`.
- Realtime là model sinh giọng, có thể nói khác văn bản đã kiểm duyệt. Backend so transcript với văn bản gốc, lệch thì bỏ audio, chỉ hiện chữ.
- Chữ luôn hiện trước, không stream audio. Audio không lưu.
- Chất lượng giọng tiếng Việt chưa được nghe thử. Sẽ chỉ biết khi chạy thật.

## 9. Giao diện

- Quy trình thiết kế theo skill impeccable: làm brief cho từng màn trước khi code, sau đó critique, audit, polish.
- Hướng hình ảnh "Góc yên": sổ tay yên tĩnh, ấm, ít viền. Màu đỏ chỉ dành cho khẩn cấp.
- Chuyển động bằng GSAP, một khoảnh khắc chính là niêm phong bằng chứng. Khẩn cấp không bao giờ chờ animation.
- WCAG 2.2 AA, mobile 360px, chế độ tối, rà trên iPhone và Android thật.

## 10. Chi phí

Các số dưới đây là ước lượng, chưa đo trên prompt thật.

| Mục | Số |
| --- | --- |
| 100 người dùng/tháng | Khoảng 13 USD |
| 1.000 người dùng/tháng | Khoảng 133 USD |
| Khoản lớn nhất | TTS, khoảng một nửa |
| Trần vận hành | 20 USD/ngày, riêng khách 5 USD/ngày |
| Eval live | Dưới 3 USD tổng, ước tính khoảng 1,40 USD |

## 11. Cách triển khai

Claude Code lập kế hoạch và review. Grok viết code tới khi release. Một người là owner, duyệt nội dung, đọc 10 bản ghi hội thoại chọn ngẫu nhiên, xem ảnh giao diện.

| Gate | Nội dung |
| --- | --- |
| G0 | CI xanh |
| G1 | An toàn và agent đạt eval, owner đọc 10 bản ghi |
| G2 | KB và Hồ sơ đạt |
| G3 | Luyện nói đạt |
| G4 | Tích hợp, giao diện hết lỗi P0–P2, chạy trên điện thoại thật |
| G5 | Release staging, kịch bản chạy với model thật |

**Tiêu chuẩn hội thoại**: 35 kịch bản chạy live, chỉnh trên 20 kịch bản, 15 kịch bản còn lại chỉ chạy ở vòng cuối. Điểm từ 1 đến 5, mỗi nhóm ≥ 4,5, mọi kịch bản ≥ 4, nhóm an toàn không có điểm dưới 4.

**Bài trình bày 8 phút**: định vị vấn đề, hành trình chính, hồ sơ và bằng chứng, khẩn cấp không phụ thuộc AI, hiểu cách nói gián tiếp, trả lời có căn cứ và dám nói chưa biết, luyện nói, giới hạn của AI.

## 12. Đã chốt

| Quyết định | Nội dung |
| --- | --- |
| Mục tiêu đợt này | Trình bày sản phẩm với nội dung hư cấu |
| Ưu tiên | Độ thông minh của agent, độ chi tiết, độ hoàn thiện đứng trước tốc độ |
| Model ngôn ngữ | Chỉ `gpt-6-luna` |
| Môi trường | Bản release thật, model thật, không có chế độ demo trong code |
| Khách | Vào thẳng một chạm, đủ tính năng, tự xóa sau 2 giờ |
| Upload | Nhận mọi ảnh, video, không phân loại nội dung. Không bao giờ gửi file tới model |
| Nền tảng trong KB | Chỉ Facebook, YouTube, TikTok |
| Hệ thống cũ | Đóng băng, không vá |
| Tình huống mẫu | Chỉ là kịch bản Markdown, không có trang trong sản phẩm |
| Một agent | Không multi-agent |
| Không làm trong đợt này | ZDR với OpenAI, tư vấn pháp lý, luồng đồng ý của phụ huynh, đăng ký tài khoản, báo cáo giám sát |

**Điều kiện duy nhất**: không phát đường dẫn cho học sinh thật hoặc trường học. OpenAI yêu cầu bật zero data retention trước khi xử lý dữ liệu cá nhân trẻ dưới 13 tuổi. Luật Bảo vệ dữ liệu cá nhân 2025 của Việt Nam cũng cần tư vấn pháp lý về đồng ý của người đại diện. Các việc này để lại tới khi có học sinh thật.

## 13. Chỗ yếu đã biết

1. **Chưa kiểm chứng gì với người dùng thật.** Mọi giả định về cách học sinh nói và điều các em cần đến từ suy luận và kịch bản hư cấu.
2. **Một demo hư cấu khó chứng minh tác động.** Thước đo là "em tới được người lớn thật", nhưng demo không đo được điều đó.
3. **Model nhỏ.** OpenAI khuyên dùng flagship cho trẻ vị thành niên, đây là khuyến nghị chứ không bắt buộc. Chưa biết Luna có đạt rubric không.
4. **Không có người thật trong vòng lặp.** App không báo cho ai. Với ca nguy hiểm thật, app chỉ hướng dẫn gọi 111.
5. **Khách chỉ giữ dữ liệu 2 giờ**, trong khi giá trị của Hồ sơ nằm ở theo dõi nhiều ngày.
6. **Thiếu Zalo**, nền tảng học sinh Việt Nam dùng nhiều. Trợ lý sẽ nói "mình chưa chắc".
7. **Nội dung chỉ một người duyệt**, chưa có chuyên gia tâm lý học đường hay luật sư. Văn bản pháp luật có chỗ chưa đọc toàn văn. Luật Trẻ em định nghĩa trẻ em là dưới 16 tuổi, nên nhóm 16–17 cần viết cẩn thận.
8. **Giọng tiếng Việt chưa nghe thử.**
9. **Phạm vi lớn so với nguồn lực**: 10 workstream, hơn 130 task, một owner, code do AI viết.
10. **Một máy chủ, một worker.** Trình bày trực tiếp phụ thuộc mạng và API bên ngoài.
11. **Chưa có mô hình kinh doanh** và chưa có đường đi cụ thể từ bản demo tới trường học.

## 14. Rủi ro khi trình bày

- Model trả lời khác kịch bản, vì một số bước là xác suất.
- Mạng hội trường yếu. Dự phòng là hotspot, video quay sẵn, và các nhánh không cần model.
- Turnstile lỗi khi vào chế độ khách. Cloudflare đang báo chưa thấy lệnh `siteverify`, cần kiểm tra CAPTCHA của Supabase.
- Hết trần chi phí ngày đúng lúc trình bày.

## 15. Câu hỏi cần brainstorm

**Sản phẩm**

1. "Tới được người lớn thật" có phải thước đo đúng không? Có cách nào thể hiện nó trong một bản demo hư cấu không?
2. Trong 6 luồng và 4 tab, phần nào thuyết phục nhất với ban giám khảo? Phần nào nên cắt hoặc gộp để sản phẩm sắc nét hơn?
3. 30 giây đầu của một em 12 tuổi đang sợ nên diễn ra thế nào? Câu đầu tiên của Trợ lý nên là gì?
4. Có tính năng nhỏ nào tạo khác biệt lớn mà plan đang bỏ sót không?
5. Có ý tưởng nào khiến sản phẩm khác hẳn một chatbot tâm lý thông thường không?

**Agent**

6. Với model nhỏ, kỹ thuật nào nâng độ thông minh cảm nhận được nhiều nhất?
7. Rubric chấm "thông minh" nên đo gì để không bị khớp vào kịch bản? Tiêu chí nào đang thiếu?
8. Những ca hội thoại khó nào nên có trong playbook mà danh sách hiện tại chưa nghĩ tới?
9. Làm sao để Trợ lý ấm áp mà không giả làm bạn, và không sáo rỗng?
10. Có nên để Trợ lý chủ động hỏi thăm trong cùng phiên khi em im lặng lâu không?

**An toàn**

11. Cân bằng báo động nhầm và bỏ sót thế nào? Báo động nhầm quá nhiều có làm em bỏ app không?
12. Khi template khẩn cấp hiện lên giữa cuộc trò chuyện, làm sao để em không thấy bị bỏ rơi?
13. Khi người gây hại là cha mẹ hoặc thầy cô, luồng nào là an toàn nhất?
14. Ngoài rule và classifier, có cách nào phát hiện leo thang qua nhiều phiên mà vẫn tôn trọng riêng tư không?

**Trình bày và chiến lược**

15. Bài trình bày 8 phút nên sắp xếp thế nào để ấn tượng nhất? Ca nào nên mở đầu?
16. Ban giám khảo sẽ hỏi khó những gì, và nên trả lời thế nào, nhất là về dữ liệu trẻ em và trách nhiệm khi AI sai?
17. Mô hình kinh doanh nào hợp lý: bán cho trường, phòng giáo dục, tổ chức xã hội, hay miễn phí có tài trợ?
18. Từ demo tới một trường thí điểm đầu tiên, các bước tối thiểu là gì?
19. Nên kiểm chứng giả định với ai sớm nhất, khi chưa cho học sinh dùng sản phẩm?

**Cắt giảm**

20. Nếu chỉ giữ được 50% phạm vi mà không giảm chất lượng, nên giữ phần nào?
21. Rủi ro lớn nhất mà bản mô tả này chưa nhắc tới là gì?
