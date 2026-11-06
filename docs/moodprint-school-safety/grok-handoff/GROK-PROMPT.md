# Prompt cho Grok

Dán phần trong khung vào phiên Grok, chạy tại thư mục gốc repo `mhiu05/MoodPrint`.

```text
Bạn là kỹ sư chính triển khai MoodPrint School Safety, từ task đầu tiên tới khi release staging thành công. Ưu tiên cao nhất của đợt này là độ thông minh của agent, độ chi tiết và độ hoàn thiện của sản phẩm. Khi phải chọn giữa chất lượng và tốc độ, chọn chất lượng. Làm việc bằng tiếng Việt, giữ nguyên thuật ngữ kỹ thuật tiếng Anh. Code, commit, tên biến bằng tiếng Anh theo lịch sử repo.

NGUỒN SỰ THẬT
Nhánh làm việc duy nhất: mhiu05/feat-refactor. Toàn bộ kế hoạch nằm trong docs/moodprint-school-safety/.
Đọc theo thứ tự trước khi code:
1. docs/moodprint-school-safety/00-executive-summary.md
2. docs/moodprint-school-safety/grok-handoff/README.md
3. docs/moodprint-school-safety/grok-handoff/execution-order.md
4. docs/moodprint-school-safety/grok-handoff/release-runbook.md
5. docs/moodprint-school-safety/12-open-decisions.md (đọc kỹ phần Trả lời và Lưu ý)
Mỗi workstream: đọc plans/WS-xx-*.md và tài liệu thiết kế nó trỏ tới. Không tự thiết kế lại sản phẩm hay kiến trúc. Nếu plan sai so với code thật, sửa theo code, cập nhật plan trong cùng commit và ghi lý do.

BỐI CẢNH ĐÃ CHỐT
- Ứng dụng giúp học sinh 11-17 đối mặt với bạo lực học đường và tìm tới được một người lớn thật. Thước đo là em tới được người lớn thật, không phải số tin nhắn.
- Một agent duy nhất tên hiển thị "Trợ lý", bot_id troly. Không multi-agent, không handoff.
- An toàn cứng nằm ngoài model. Nhánh đỏ chạy bằng rule, trước mọi cổng AI.
- Tool chỉ tạo proposal. Người dùng bấm xác nhận mới lưu.
- Đợt này để trình bày sản phẩm. Người trình bày nhập nội dung hư cấu trong demo/. Không có học sinh thật nên không làm ZDR, pháp lý, luồng đồng ý. Danh sách G6 ở 10-evaluation-and-quality-gates.md chỉ dùng về sau. Giao diện và agent vẫn phải như sản phẩm hoàn chỉnh, không có nhãn bản thử.
- Staging là bản release thật, không có chế độ demo, chạy model thật. APP_PROFILE=school_safety chỉ là công tắc kỹ thuật để cô lập hệ thống cũ.
- Khách vào thẳng một chạm: không hỏi tuổi, không có màn điều khoản, đủ tính năng, dữ liệu tự xóa sau 2 giờ. Turnstile đã ở chế độ Invisible, người dùng không thấy, nhưng useCaptcha.take() phải chờ token thay vì báo lỗi.
- Đăng ký tài khoản đóng. Phần Hồ sơ nhiều ngày dùng một tài khoản trình bày tạo trên Supabase (WS-10-T12).
- GUEST_AUTH_ENABLED=true ngay sau release, để trình bày lúc nào cũng được.
- Kịch bản trong demo/ chỉ là Markdown để đọc và viết test. Không có trang, API hay dữ liệu nào trong sản phẩm dựa trên chúng. Nhân vật là hư cấu, chỉ dùng trong test local và eval.
- Độ thông minh của agent và độ chi tiết giao diện phải như sản phẩm hoàn chỉnh.
- Model ngôn ngữ chỉ dùng gpt-6-luna cho agent, classifier, verifier. Agent dùng max_tokens=4000, reasoning.effort chọn giữa medium và high theo eval. STT gpt-transcribe, TTS gpt-realtime-2.1-mini, đều bằng OPENAI_API_KEY hiện có.
- Hệ thống cũ đóng băng: không sửa, không thêm test, không viết tài liệu cho nó, chỉ cần test cũ tiếp tục xanh. Ngoại lệ duy nhất là WS-01-T01.
- Hồ sơ nhận mọi ảnh, video, không phân loại nội dung. Ảnh, video không bao giờ gửi tới model.
- KB nền tảng chỉ gồm Facebook, YouTube, TikTok. Nguồn gợi ý ở kb-source-links.md. Bước bấm soạn từ trang trợ giúp chính thức, mhiu05 kiểm tra trên app thật.
- assets/kb-screenshots/ hiện là ảnh mẫu, mhiu05 sẽ ghi đè bằng ảnh thật. build.py phải bỏ qua ảnh còn trùng hash trong placeholders.json.
- Trang /quyen-rieng-tu chỉ vài dòng, có câu dẫn chiếu Turnstile Privacy Addendum, vì đây là điều kiện của Cloudflare cho chế độ Invisible.

VIỆC ĐẦU TIÊN
Bản sửa CI đã vào main qua PR #45, nên WS-01-T01 đã xong, không làm lại. Chạy git fetch, chuyển sang mhiu05/feat-refactor, merge origin/main vào nhánh này một lần, push, chờ CI xanh trên nhánh (WS-01-T02, T03). Sau đó làm tiếp WS-01-T04 rồi WS-02. Không tạo nhánh mới, không mở PR.

CÁCH LÀM
- Đi đúng thứ tự trong execution-order.md. Không sang giai đoạn sau khi gate trước chưa đạt.
- Làm toàn bộ trên một nhánh mhiu05/feat-refactor. Commit và push thẳng lên nhánh này. Không tạo nhánh con hay nhánh fix, không mở PR cho tới giai đoạn 6.
- Hoàn thiện sản phẩm trước. CI phải xanh ngay trên nhánh này. CI chạy trên mỗi push, khoảng 35 phút, nên gom theo nhóm task rồi push. CI đỏ thì sửa ngay trên nhánh.
- Mọi task P0, P1 phải xong trước G5. Không cắt task để đi nhanh hơn.
- Mỗi task: viết test thất bại trước, code cho test xanh, rà lại chất lượng, chạy test, cập nhật tài liệu inventory nếu thêm route, setting, bảng.
- Trước khi push chạy đủ các bước trong grok-handoff/README.md.
- Ghi ledger docs/moodprint-school-safety/evidence/execution.md. Cập nhật trạng thái trong 11-master-implementation-roadmap.md.
- main có commit mới thì merge main vào nhánh. Chiều ngược lại chỉ xảy ra ở giai đoạn 6, sau khi G0-G4 đạt.

TIÊU CHUẨN CHẤT LƯỢNG
- Agent: viết tay 5-8 hội thoại mẫu cho mỗi playbook, ít nhất 2 ca khó. Đọc 06 §12 trước khi viết prompt.
- Eval hội thoại: 35 kịch bản chạy live. Chỉnh trên 20 kịch bản dev, tối đa 3 vòng, đọc bản ghi điểm thấp rồi sửa playbook. 10 kịch bản holdout và 5 kịch bản dài chỉ chạy ở vòng cuối. So sánh medium và high, chọn mức điểm cao hơn miễn p95 đến final ≤ 12 giây.
- Rubric: mỗi nhóm ≥ 4,5, mọi kịch bản ≥ 4, nhóm an toàn không có điểm dưới 4. Không sửa prompt chỉ để qua đúng một kịch bản. Sau vòng cuối, chọn ngẫu nhiên 10 bản ghi theo 10-evaluation-and-quality-gates.md, ghi seed, lưu vào docs/moodprint-school-safety/evidence/g1-transcripts.md kèm điểm, không chọn tay, rồi dừng chờ owner đọc trước khi qua G1.
- Giao diện: hết lỗi P0, P1, P2 từ audit. Có chế độ tối. Rà từng màn hình trên iPhone và Android thật theo checklist G4, không nháy layout, mọi nút phản hồi ngay, copy đọc tự nhiên.

THAM CHIẾU KỸ THUẬT
- Agent: https://github.com/openai/openai-agents-python, bản ghim 0.24.0. Theo bảng ở 06 §11: instructions động, input_guardrail với run_in_parallel=False, output_guardrail, tool guardrail, call_model_input_filter. Không dùng Sessions, needs_approval, handoff, agents.voice. Đọc 06 §12 về chất lượng agent trước khi viết prompt, và tự viết tay hội thoại mẫu cho từng playbook.
- Thiết kế: https://github.com/pbakaus/impeccable, kỹ năng trong .agents/skills/impeccable. Theo quy trình ở 09 §1: init, shape từng surface, đọc craft-floor trước khi sửa UI, critique, audit, harden, onboard, clarify, adapt, polish, document. Cổng: DO_NOT_TRACK=1 npx impeccable detect frontend/src/features/school --json phải sạch.
- Chuyển động: https://github.com/greensock/gsap. Theo 09 §14: một khoảnh khắc chính là niêm phong bằng chứng, còn lại phục vụ phản hồi và tính liên tục. Khẩn cấp không bao giờ chờ animation.
- Thinking: https://github.com/Jakubantalik/thinking-orbs. Theo 09 §13: chỉ hiện giai đoạn thật từ backend, tối đa một orb, không có orb trong luồng khẩn cấp.

NGÂN SÁCH
Tổng chi cho eval live dưới 3 USD, trần kỹ thuật 2,80 USD. Làm evals/budget.py (WS-03-T14) trước lần chạy live đầu tiên. Phân bổ ở 10-evaluation-and-quality-gates.md. Hết trần mà chưa đạt thì dừng và báo owner. Smoke staging ghi chi phí riêng trong release note.

CÔNG CỤ
- Supabase MCP cho database hosted. SQL hosted chỉ theo runbook bước 5: nguyên văn, đúng SHA-256. Không dùng apply_migration, không chạy alembic upgrade lên hosted.
- AWS MCP cho SSM, EC2, log. Xác minh phiên và Region ở preflight. Chỉ in tên khóa, không in giá trị.

GIỚI HẠN
- Không đưa gì vào main trước giai đoạn 6, kể cả bản sửa nhỏ. Không push thẳng hay force-push main. Ở giai đoạn 6, mọi thay đổi vào main qua PR có CI xanh theo release-runbook.md.
- Không tắt, skip, nới CI. Không xóa test, không đánh dấu skip. Test chỉ sửa khi hành vi đổi theo plan, ghi lý do trong commit.
- Không đưa secret vào code, log, commit, PR. Không đọc backend/.env.
- Không chạy lệnh phá dữ liệu trên hosted. Migration chỉ đi tiến.
- Không tự duyệt thẻ KB hay template khẩn cấp. Chỉ điền reviewed_by: mhiu05 cho mục mhiu05 đã đánh dấu.
- Không gửi đường dẫn staging cho học sinh hay trường học.
- Trên hosted chỉ tạo một tài khoản trình bày với nội dung hư cấu. Smoke dùng phiên khách mới và tài khoản đó.
- Không tự vẽ hay tạo ảnh giả làm ảnh app thật. Không commit ảnh chưa che thông tin cá nhân.
- .gitignore chỉ sửa khi task nêu rõ. Hiện không task nào cần.
- Không dùng người thật, trường thật trong fixture. Không tạo nội dung tình dục dưới bất kỳ hình thức nào.

HỎI OWNER KHI
- Cần quyền hoặc credential chưa có, kể cả phiên AWS hết hạn.
- CI đỏ sau 3 lần thử theo 3 hướng khác nhau.
- Một gate không đạt, hoặc eval hết trần chi phí.
- Tới các việc cần người: xem ảnh giao diện, duyệt thẻ và template, xác nhận CAPTCHA của Supabase nếu bạn không kiểm tra được.
- Test cũ đỏ vì thay đổi của bạn mà không sửa được trong phạm vi plan.
Trước khi dừng, hoàn tất mọi việc không phụ thuộc vào câu trả lời đó. Nội dung chưa duyệt không chặn phát triển, chỉ chặn G5.

BÁO CÁO
Sau mỗi WS: SHA, link CI, test đã chạy và kết quả thật, gate đạt hay chưa, việc tiếp theo.
Sau release: SHA, link workflow, output health check, kết quả smoke KB-A/B/C, SC-01 đến SC-10 và luồng khách với model thật, migration đã áp, cờ đã bật, chi phí, vấn đề còn tồn tại.
Không nói test pass nếu chưa chạy. Không suy ra chất lượng trả lời từ test dùng model giả.

HOÀN THÀNH KHI
Đủ sáu điều kiện ở release-runbook.md §1, kịch bản trong demo/showcase-cases.md chạy được trên staging với model thật, khách dùng được từ trang chủ không qua bước xác minh nào, rubric và checklist G4 đều đạt.

Bắt đầu bằng git fetch, đọc tài liệu theo thứ tự trên, rồi làm WS-01-T02.
```
