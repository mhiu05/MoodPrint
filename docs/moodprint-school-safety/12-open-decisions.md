# 12 — Quyết định của owner

Cập nhật sau trả lời của owner. Câu trả lời giữ nguyên ý, dưới mỗi câu là cách áp dụng vào plan. Mục **Lưu ý** ghi chỗ plan giữ lại hoặc điều chỉnh, kèm lý do, để owner quyết định lại nếu muốn.

| ID | Quyết định | Trạng thái | Kết quả |
| --- | --- | --- | --- |
| OD-01 | Bản chất của staging | **Đã chốt** | Bản release thật, không có chế độ demo; ví dụ mẫu để khách đọc và thử |
| OD-02 | Duyệt nội dung | **Đã chốt, chặn G5** | `reviewed_by: mhiu05`; chỉ Facebook, YouTube, TikTok |
| OD-03 | Upload ảnh, video | **Đã chốt, có rủi ro** | Nhận mọi ảnh, video, không phân loại nội dung |
| OD-04 | TTS, STT | **Đã chốt** | `gpt-realtime-2.1-mini`, `gpt-transcribe`, không cần nghe thử |
| OD-05 | Chế độ khách | **Đã chốt, có điều chỉnh** | Vào thẳng, đủ tính năng, dữ liệu tự xóa sau 2 giờ |
| OD-06 | Hướng hình ảnh | Đã chốt quy trình | Làm theo impeccable; hướng A là brief khởi đầu |
| OD-07 | Snapshot nguồn | Mặc định | `.tmp/`, không sửa `.gitignore` |
| OD-08 | Ngưỡng eval an toàn | Mặc định | Dùng ngưỡng đề xuất; không đạt thì báo owner |
| OD-09 | Quy tắc merge | **Đã chốt** | CI xanh ở nhánh con, PR, CI xanh trên `main`, release thành công |
| OD-10 | Tóm tắt nháp chạy qua agent | Mặc định | Đồng ý |
| OD-11 | Trần chi phí eval live | **Đã chốt** | Dưới 3 USD tổng; trần kỹ thuật 2,80 USD |
| OD-12 | Credential | **Đã chốt phần lớn** | Supabase MCP, AWS MCP |
| OD-13 | Hệ thống cũ | **Đã chốt** | Đóng băng, không vá, không tương thích ngược |
| OD-14 | Model | **Đã chốt** | Chỉ `gpt-6-luna` cho agent, classifier, verifier |
| OD-15 | Ai được dùng bản release | **Mở, cần owner trả lời** | Mặc định: khách đánh giá, chưa hướng tới học sinh thật |

## OD-01 — Staging là bản release thật

**Trả lời**: Chốt lại staging và bản chất cũng giống staging, loại bỏ chế độ demo, luôn là bản release thật. Phần kịch bản demo coi như một số ví dụ chi tiết cụ thể để khách hàng đọc qua, thử nghiệm.

**Áp dụng**:

- Bỏ khái niệm demo trong sản phẩm, UI và tài liệu vận hành.
- `demo/` trở thành **tình huống mẫu**: khách đọc được trên trang `/vi-du` và bấm "Thử tình huống này" ([09 §15](09-ux-and-user-flows.md#15-tình-huống-mẫu)).
- Năm persona hư cấu thành **tài khoản mẫu** có sẵn dữ liệu. Dùng cho smoke và minh họa.
- Staging chạy model thật.

**Lưu ý**: vẫn giữ một công tắc kỹ thuật `APP_PROFILE=school_safety`, mặc định trong code là `default`. Đây không phải chế độ demo. Nó là cách rẻ nhất để đóng băng hệ thống cũ theo OD-13: hơn 2.000 test cũ tiếp tục xanh mà không phải sửa hay xóa. Đổi mặc định sẽ làm vỡ các test đó và trái quy tắc không xóa test.

**Đăng ký tài khoản vẫn đóng.** Khách đã dùng được đầy đủ nên chưa cần đăng ký, lại tránh thu email của trẻ vị thành niên. Muốn mở thì quyết định ở OD-15.

## OD-02 — Duyệt nội dung

**Trả lời**: Hiện tại chỉ cần xét Facebook, YouTube, TikTok. Reviewed by: mhiu05. mhiu05 sẽ trực tiếp chụp màn hình app thật; việc research tài liệu để lưu thẻ KB dạng text thì Claude gợi ý chi tiết một số link nguồn uy tín.

**Áp dụng**:

- Link nguồn đã tra ở [kb-source-links](kb-source-links.md).
- Thẻ `report` giảm còn 3 nền tảng, tổng khoảng 47 thẻ, vẫn đạt mức 40–60.
- Grok soạn nháp và lập `evidence/content-review.md`. mhiu05 đánh dấu từng mục. Grok chỉ điền `reviewed_by: mhiu05` cho mục đã được đánh dấu, không tự duyệt.
- WS-03, WS-05 vẫn phát triển và eval được với nội dung `draft`, cờ `--include-draft` chỉ dùng trong eval local.
- **Chặn G5**: image chỉ đóng gói nội dung đã duyệt, cần ít nhất 40 thẻ và toàn bộ template khẩn cấp.
- Ảnh chụp đặt ở `.tmp/kb/manual/<platform>/`, **không commit**, vì repo công khai và ảnh có thể lộ tài khoản. Grok chuyển thành các bước bằng chữ trong `kb/sources/manual/`.

**Lưu ý**: bỏ Zalo tạo một khoảng trống, vì persona `kb-a` và thực tế học sinh Việt Nam dùng Zalo nhiều. Khi được hỏi về Zalo, Trợ lý trả lời "mình chưa chắc" và hướng tới người lớn thay vì đoán. KB-A đổi sang Facebook. Thêm Zalo sau chỉ cần thêm thẻ.

## OD-03 — Upload ảnh, video

**Trả lời**: Tạm thời bỏ qua phần phân biệt nội dung ảnh, video có liên quan tới tình dục hay không. Chấp nhận mọi input ảnh, video.

**Áp dụng**:

- Bỏ bước tự kiểm tra, bỏ `EVIDENCE_BLOCKED`.
- Hồ sơ nhận ảnh và video theo danh sách MIME của bucket hiện có: ảnh ≤ 10 MiB, video ≤ 50 MiB. Tính SHA-256 cho cả hai.
- PDF nhúng ảnh; video chỉ ghi tên, thời điểm, mã SHA-256.

**Giữ lại, không làm tăng ma sát**:

- Ảnh, video **không bao giờ** gửi tới model. Plan chưa từng cần việc này.
- Bucket private, chỉ chủ sở hữu đọc được qua signed URL 60 giây.
- Tầng rule của Safety Engine với lời kể bằng chữ giữ nguyên: template, không gọi model.
- Một dòng nhắc cố định ở màn tải lên, không chặn gì: "Nếu nội dung liên quan tới hình ảnh tình dục của trẻ em, đừng lưu hay gửi đi. Hãy gọi 111."

**Lưu ý rủi ro**: quyết định này đảo yêu cầu ở §4.3 của prompt gốc. Ở bản release thật, kết hợp với khách vào thẳng (OD-05), bất kỳ ai cũng có thể tải file lên mà không ai kiểm tra. Lưu trữ nội dung xâm hại tình dục trẻ em có thể vi phạm pháp luật và điều khoản của nhà cung cấp, kể cả khi không cố ý. Rủi ro hiện được giới hạn vì đăng ký đóng, nên file của người ngoài chỉ đến từ khách và bị xóa theo vòng đời 2 giờ. Phải xem lại quyết định này trước khi hướng tới học sinh thật hoặc mở đăng ký (OD-15).

## OD-04 — TTS và STT

**Trả lời**: Dùng model `gpt-realtime-2.1-mini` là chính luôn, không cần nghe thử giọng Việt một lần trước G3.

**Áp dụng**: bỏ phương án `gpt-4o-mini-tts`, bỏ bước owner nghe thử. Giọng mặc định `marin`, TO_VERIFY với Realtime.

**Giữ lại**: kiểm tra tự động `verbatim_ok` trước khi phát. Đây không phải nghe thử: Realtime là model sinh giọng, có thể nói khác văn bản đã qua kiểm duyệt an toàn. Chất lượng giọng tiếng Việt sẽ chỉ được biết ở bước smoke; lỗi thì tắt TTS bằng `TTS_PROVIDER=none`, chữ vẫn chạy.

## OD-05 — Chế độ khách

**Trả lời**: Guest không cần xác minh gì cả, cứ thế vào trải nghiệm, chỉ khác là dữ liệu tự xóa sau 2 giờ. Không ràng buộc cho guest, để guest thoải mái sử dụng, ưu tiên trải nghiệm thay vì hạn chế về quyền dữ liệu.

**Áp dụng**:

- Một chạm "Dùng thử ngay": không hỏi tuổi, không có màn điều khoản chặn.
- Khách có đủ Trợ lý, Hồ sơ, Luyện nói, xuất PDF.
- Nhóm tuổi mặc định `11-14` (ngôn ngữ dễ nhất), đổi được ở Cài đặt.
- Một thông báo không chặn: đây là AI, dữ liệu tự xóa sau 2 giờ.
- Nâng hạn mức tới mức người dùng thật không chạm tới trong 2 giờ: 200 lượt chat, 20 lượt/phút, 60 bản ghi, 30 phút thu âm, 6 bản ghi/phút.

**Giữ lại hai lớp người dùng không nhìn thấy**, vì đây là tiền thật và không có tài khoản:

| Lớp | Vì sao | Trải nghiệm |
| --- | --- | --- |
| Cloudflare Turnstile chạy nền | Supabase cần token CAPTCHA khi tạo phiên ẩn danh. Không có nó, bot gọi tốn tiền API không giới hạn | Không có ô bấm nếu widget đặt Invisible |
| Trần `GUEST_DAILY_BUDGET_USD` tối đa 5 USD, code đang ép | Chặn chi phí mất kiểm soát | Hết trần: Trợ lý báo bận, khẩn cấp vẫn chạy |

**Việc của mhiu05**: đổi widget Turnstile sang Invisible trên Cloudflare. Nếu không, thỉnh thoảng người dùng thấy một ô kiểm tra.

**Phải sửa trong code** (đã thêm task): dưới cấu hình có trần, `kind_available` đang đóng giọng nói của guest; mỗi lượt guest giữ 1,53 USD nên chỉ khoảng 3 lượt chạy đồng thời. Trần input cứng hạ mức giữ còn 0,10 USD; `guest_ai_global_concurrency` mặc định 10 và `guest_voice_per_minute` mặc định 2 cũng được nâng lên 30 và 6.

**Nói thật về "tự xóa sau 2 giờ"**: hàng trong database bị xóa và quyền truy cập file bị thu hồi khi hết giờ. Object trong Storage bị xóa theo hàng đợi, trễ thêm tối đa 2 giờ 5 phút (`DELETE_DELAY`, vì upload token sống 2 giờ), tức khoảng 4 giờ kể từ lúc vào. Nội dung đã gửi OpenAI theo chính sách của họ (`store=False`, chưa phải zero data retention). Copy trong app không được hứa quá mức này.

## OD-06 — Hướng hình ảnh

Quy trình ở [09 §1](09-ux-and-user-flows.md#1-hướng-hình-ảnh-và-quy-trình-impeccable). Brief khởi đầu là hướng A "Góc yên". Owner xem ảnh chụp ở G4.

## OD-07 — Snapshot nguồn

**Mặc định**: `.tmp/kb/raw/`, đã được gitignore. Manifest giữ sha256. Không phát hành lại nguồn.

## OD-08 — Ngưỡng eval an toàn

**Mặc định**: áp ngưỡng ở [10](10-evaluation-and-quality-gates.md). Grok chạy baseline, chỉnh rule trên `dev`. Nếu `holdout` không đạt sau khi đã dùng hết phần ngân sách cho hạng mục này, dừng và báo owner kèm số thật.

## OD-09 — Quy tắc merge

**Trả lời**: CI pass ở nhánh con, rồi PR merge CI pass ở nhánh `main`, release thành công là được.

**Áp dụng**: đúng quy trình trong [grok-handoff/README](grok-handoff/README.md). Không bật branch protection. Grok vẫn không push thẳng vào `main`.

## OD-10 — Tóm tắt nháp chạy qua agent

Tóm tắt case và tóm tắt phiên luyện nói là lượt của chính agent `troly`, không tool ghi, đi qua postcheck, nên không phát sinh loại lượt mới. **Mặc định**: đồng ý.

## OD-11 — Trần chi phí eval live

Owner chốt: **dưới 3 USD**, cộng dồn qua các WS. Phân bổ ở [10](10-evaluation-and-quality-gates.md#ngân-sách-eval-live). Trần kỹ thuật 2,80 USD do `evals/budget.py` cưỡng chế. Dùng Luna làm ước tính giảm còn khoảng 0,60 USD, nên chạy live được nhiều kịch bản hơn.

Smoke trên staging là vận hành, không phải eval. Nó nằm trong `AI_DAILY_BUDGET_USD`, ghi chi phí riêng ở release note.

## OD-12 — Credential

| Việc | Đường đi | Trạng thái |
| --- | --- | --- |
| SQL hosted | Supabase MCP. Đã kiểm tra: role `postgres`, chủ các bảng `moodprint`, có quyền CREATE | Sẵn sàng |
| SSM, EC2, log | AWS MCP theo owner xác nhận | **Chưa kiểm chứng**: `aws-mcp` lỗi kết nối ở cả hai phiên, `aws sts` trên máy audit trả exit 253 |
| Auth Admin cho seed | Khóa server trong SSM, đọc vào RAM, không in | Cần kiểm tra `JOURNAL_STORAGE_KEY` có đủ quyền Auth Admin không |
| OpenAI, Voyage | Đã có trong SSM theo tài liệu release 05/11/2026 | Grok kiểm tra tên khóa |

Region của project xác nhận tại **AWS Settings > View all projects > Overview > Additional Info > Region**. Nếu không xác nhận được, kiểm tra `~/.aws/config`. Code và `deployment.conf.example` ghi `ap-southeast-2`.

Nếu MCP không chạy được SQL nguyên văn, hoặc AWS MCP không truy cập được SSM: dừng và báo owner, không tìm đường vòng.

## OD-13 — Hệ thống cũ

**Trả lời**: Ưu tiên tuyệt đối hệ thống mới. Đóng băng, cô lập hoàn toàn chat cũ, không tốn tài nguyên vá hay tương thích ngược.

1. Phạm vi an toàn: Safety Engine mới là trọng tâm duy nhất. Không đem engine mới vá cho chat cũ, không duy trì song song luồng chat cũ trong đợt này.
2. Kiến trúc và giao diện: được bỏ qua hoặc ẩn hoàn toàn tính năng cũ (bot cũ, nhóm chat, proactive, social...). Staging trỏ 100% vào giao diện mới và `troly`.
3. Mục tiêu: tập trung toàn bộ thời gian, công sức và ngân sách eval để hoàn thiện 7 tầng an toàn, bộ thẻ KB và các luồng nghiệp vụ.

**Áp dụng**: code cũ giữ nguyên, ẩn hoàn toàn trên staging qua `APP_PROFILE=school_safety`. Không thêm test, không sửa lỗi, không viết tài liệu cho nó. Ràng buộc còn lại duy nhất: test cũ phải tiếp tục xanh, vì CI là điều kiện release theo OD-09.

**Lưu ý**: WS-01-T01 sửa một lỗi nhỏ ở `GroupChat.tsx`, là code cũ. Vẫn phải làm vì nó đang làm CI đỏ và chặn mọi release. Đây là ngoại lệ duy nhất.

## OD-14 — Model

**Trả lời**: Chỉ sử dụng model `gpt-6-luna`, không sử dụng model khác.

**Áp dụng**: agent, classifier, verifier đều dùng `gpt-6-luna`. Bỏ `ASSISTANT_MODEL`, bỏ so sánh model, `CAPPED_RATES` không đổi. Chi phí giảm còn khoảng 13 USD/tháng cho 100 người dùng.

**Phạm vi**: câu này được hiểu là model ngôn ngữ. `gpt-transcribe`, `gpt-realtime-2.1-mini` (OD-04) và Voyage vẫn dùng, vì Luna không xử lý âm thanh hay embedding.

**Lưu ý**: độ thông minh sẽ dựa vào ngữ cảnh, playbook viết tay và `reasoning.effort`. Nếu rubric không đạt, nâng `reasoning.effort` từ `medium` lên `high` trước. Đổi model phải hỏi owner.

## OD-15 — Ai được dùng bản release này

**Cần owner trả lời.** OD-01 chuyển sản phẩm từ demo hư cấu sang bản release thật. Nhiều việc từng được hoãn vì lý do "chỉ dùng persona hư cấu". Phải làm rõ "khách hàng" là ai.

| Phương án | Ý nghĩa | Hệ quả |
| --- | --- | --- |
| A. Khách đánh giá | Ban giám khảo, nhà trường, phụ huynh, giáo viên xem và thử bằng tình huống mẫu | Release được theo plan hiện tại |
| B. Học sinh thật dùng | Trẻ 11–17 nhập chuyện thật của mình | Phải qua toàn bộ cổng ở [04](04-feature-gap-analysis.md#cổng-bắt-buộc-trước-khi-mở-cho-học-sinh-thật) trước |

Điểm bắt buộc nếu chọn B, không thể bỏ qua bằng quyết định sản phẩm: [hướng dẫn Under-18 của OpenAI](https://developers.openai.com/api/docs/guides/safety-checks/under-18-api-guidance) yêu cầu bật zero data retention trước khi xử lý dữ liệu cá nhân của trẻ dưới 13 tuổi, và OpenAI có quyền đình chỉ API nếu vi phạm. Nhóm 11-14 có trẻ dưới 13.

**Mặc định**: A. Trang chủ và thông báo khách ghi: đây là bản trải nghiệm, hãy dùng tình huống mẫu, đừng nhập thông tin thật. Thông báo không chặn. Grok không quảng bá sản phẩm tới học sinh.
