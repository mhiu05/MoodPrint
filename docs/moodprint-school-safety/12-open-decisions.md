# 12 — Quyết định của owner

Cập nhật sau trả lời của owner. Câu trả lời giữ nguyên ý, dưới mỗi câu là cách áp dụng vào plan. Mục **Lưu ý** ghi chỗ plan giữ lại hoặc điều chỉnh, kèm lý do, để owner quyết định lại nếu muốn.

| ID | Quyết định | Trạng thái | Kết quả |
| --- | --- | --- | --- |
| OD-01 | Bản chất của staging | **Đã chốt** | Bản release thật, không có chế độ demo; tình huống mẫu chỉ là kịch bản Markdown |
| OD-02 | Duyệt nội dung | **Đã chốt, chặn G5** | `reviewed_by: mhiu05`; chỉ Facebook, YouTube, TikTok; tạm dùng ảnh mẫu |
| OD-03 | Upload ảnh, video | **Đã chốt, phải xác nhận lại ở G6** | Nhận mọi ảnh, video, không phân loại nội dung |
| OD-04 | TTS, STT | **Đã chốt** | `gpt-realtime-2.1-mini`, `gpt-transcribe`, không cần nghe thử |
| OD-05 | Chế độ khách | **Đã chốt, có điều chỉnh** | Vào thẳng, đủ tính năng, tự xóa sau 2 giờ; Turnstile đã đổi sang Invisible |
| OD-06 | Hướng hình ảnh | Đã chốt quy trình | Làm theo impeccable; hướng A là brief khởi đầu |
| OD-07 | Snapshot nguồn | Mặc định | `.tmp/`, không sửa `.gitignore` |
| OD-08 | Ngưỡng eval an toàn | Mặc định | Dùng ngưỡng đề xuất; không đạt thì báo owner |
| OD-09 | Quy tắc merge | **Đã chốt** | CI xanh ở nhánh con, PR, CI xanh trên `main`, release thành công |
| OD-10 | Tóm tắt nháp chạy qua agent | Mặc định | Đồng ý |
| OD-11 | Trần chi phí eval live | **Đã chốt** | Dưới 3 USD tổng; trần kỹ thuật 2,80 USD |
| OD-12 | Credential | **Đã chốt phần lớn** | Supabase MCP, AWS MCP, Cloudflare qua phiên trình duyệt của owner |
| OD-13 | Hệ thống cũ | **Đã chốt** | Đóng băng, không vá, không tương thích ngược |
| OD-14 | Model | **Đã chốt, có lưu ý** | Chỉ `gpt-6-luna` cho agent, classifier, verifier |
| OD-15 | Ai dùng sản phẩm | **Đã chốt** | Học sinh thật; mở sau khi qua cổng G6 |
| OD-16 | Đăng ký tài khoản | Mặc định, owner xem lại | Mở cho học sinh sau G6, vì khách chỉ giữ dữ liệu 2 giờ |

## OD-01 — Staging là bản release thật

**Trả lời**: Chốt lại staging và bản chất cũng giống staging, loại bỏ chế độ demo, luôn là bản release thật. Tình huống mẫu chỉ là kịch bản text dạng Markdown.

**Áp dụng**:

- Bỏ khái niệm demo trong sản phẩm, UI và tài liệu vận hành.
- `demo/*.md` là kịch bản chữ để đọc và để viết test. Không có trang, API hay dữ liệu nào trong sản phẩm dựa trên chúng.
- Năm nhân vật hư cấu chỉ dùng trong test local và eval. Không tạo tài khoản mẫu trên hosted.
- Staging chạy model thật.

**Lưu ý**: vẫn giữ một công tắc kỹ thuật `APP_PROFILE=school_safety`, mặc định trong code là `default`. Đây không phải chế độ demo. Nó là cách rẻ nhất để đóng băng hệ thống cũ theo OD-13: hơn 2.000 test cũ tiếp tục xanh mà không phải sửa hay xóa. Đổi mặc định sẽ làm vỡ các test đó và trái quy tắc không xóa test.

## OD-02 — Duyệt nội dung

**Trả lời**: Hiện tại chỉ cần xét Facebook, YouTube, TikTok. Reviewed by: mhiu05. Việc research tài liệu để lưu thẻ KB dạng text thì Claude gợi ý chi tiết một số link nguồn uy tín. Tạm thời tạo một vài ảnh mẫu liên quan, mhiu05 sẽ chèn ảnh thật sau.

**Áp dụng**:

- Link nguồn đã tra ở [kb-source-links](kb-source-links.md).
- Thẻ `report` giảm còn 3 nền tảng, tổng khoảng 47 thẻ, vẫn đạt mức 40–60.
- Grok soạn nháp và lập `evidence/content-review.md`. mhiu05 đánh dấu từng mục. Grok chỉ điền `reviewed_by: mhiu05` cho mục đã được đánh dấu, không tự duyệt.
- WS-03, WS-05 vẫn phát triển và eval được với nội dung `draft`, cờ `--include-draft` chỉ dùng trong eval local.
- **Chặn G5**: image chỉ đóng gói nội dung đã duyệt, cần ít nhất 40 thẻ và toàn bộ template khẩn cấp.

**Ảnh**: chín ảnh mẫu ở [assets/kb-screenshots](assets/kb-screenshots/README.md), mỗi ảnh ghi việc cần chụp. mhiu05 ghi đè đúng tên file khi có ảnh thật, đã che thông tin cá nhân vì repo công khai. Ảnh mẫu không bao giờ lên sản phẩm: `build.py` bỏ qua ảnh còn trùng hash trong `placeholders.json`, thẻ vẫn hiện chữ. Bước bấm trong thẻ lấy từ trang trợ giúp chính thức; mhiu05 kiểm tra trên app thật trước khi đánh dấu duyệt.

**Lưu ý**: bỏ Zalo tạo một khoảng trống, vì persona `kb-a` và thực tế học sinh Việt Nam dùng Zalo nhiều. Khi được hỏi về Zalo, Trợ lý trả lời "mình chưa chắc" và hướng tới người lớn thay vì đoán. KB-A đổi sang Facebook. Thêm Zalo sau chỉ cần thêm thẻ.

## OD-03 — Upload ảnh, video

**Trả lời**: Tạm thời bỏ qua phần phân biệt nội dung ảnh, video có liên quan tới tình dục hay không. Chấp nhận mọi input ảnh, video.

**Áp dụng**:

- Bỏ bước tự kiểm tra chung, bỏ `EVIDENCE_BLOCKED`.
- Hồ sơ nhận ảnh và video theo danh sách MIME của bucket hiện có: ảnh ≤ 10 MiB, video ≤ 50 MiB. Tính SHA-256 cho cả hai.
- PDF nhúng ảnh; video chỉ ghi tên, thời điểm, mã SHA-256.

**Giữ lại, không làm tăng ma sát**:

- Ảnh, video **không bao giờ** gửi tới model. Plan chưa từng cần việc này.
- Bucket private, chỉ chủ sở hữu đọc được qua signed URL 60 giây.
- Tầng rule của Safety Engine với lời kể bằng chữ giữ nguyên: template, không gọi model.
- Một dòng nhắc cố định ở màn tải lên, không chặn gì: "Nếu nội dung liên quan tới hình ảnh tình dục của trẻ em, đừng lưu hay gửi đi. Hãy gọi 111."

**Lưu ý rủi ro**: quyết định này đảo yêu cầu ở §4.3 của prompt gốc. Với học sinh thật (OD-15), rủi ro không còn là giả định: một em bị tống tiền bằng ảnh riêng tư có thể tải chính ảnh đó lên làm bằng chứng. Lưu nội dung xâm hại tình dục trẻ em có thể vi phạm pháp luật và điều khoản của nhà cung cấp, kể cả khi không cố ý. Với tài khoản đăng ký (OD-16), file không tự xóa sau 2 giờ.

**Bước hẹp Claude thêm vào, owner bỏ được**: chỉ khi người dùng đã có sự kiện an toàn nhãn `sexual_abuse_exploitation`, trước khi tải file app hỏi một câu: "File này có hình ảnh riêng tư của em hoặc của bạn khác không?" Chọn có thì không tải lên và hiện hướng dẫn gọi 111. Bước này không đọc nội dung file, và người dùng khác không bao giờ thấy nó. Ảnh chụp tin nhắn đe dọa vẫn lưu được. Muốn bỏ, xóa WS-06-T13.

Quyết định này phải được xác nhận lại với tư vấn pháp lý ở [G6](10-evaluation-and-quality-gates.md#cổng-g6-mở-cho-học-sinh-thật).

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
| Cloudflare Turnstile chạy nền | Supabase cần token CAPTCHA khi tạo phiên ẩn danh. Không có nó, bot gọi tốn tiền API không giới hạn | Không có ô bấm |
| Trần `GUEST_DAILY_BUDGET_USD` tối đa 5 USD, code đang ép | Chặn chi phí mất kiểm soát | Hết trần: Trợ lý báo bận, khẩn cấp vẫn chạy |

**Turnstile đã đổi sang Invisible ngày 06/11/2026**: widget `MoodPrint Guest`, hostnames `127.0.0.1`, `localhost`, `moodprint.duckdns.org`. Site key và secret giữ nguyên. Cloudflare đặt điều kiện: chính sách quyền riêng tư của app phải dẫn chiếu [Turnstile Privacy Addendum](https://www.cloudflare.com/en-gb/turnstile-privacy-policy/). Owner đã đồng ý; WS-09-T22 thực hiện.

**Cần kiểm tra**: Cloudflare đang báo "Siteverify isn't being called" cho widget này. Backend gửi token sang Supabase, nên Supabase là bên phải gọi siteverify. Nếu CAPTCHA protection của Supabase chưa bật, token không được kiểm tra và bot vào tự do. WS-10-T00 phải xác nhận trước release.

**Phải sửa trong code** (đã thêm task): dưới cấu hình có trần, `kind_available` đang đóng giọng nói của guest; mỗi lượt guest giữ 1,53 USD nên chỉ khoảng 3 lượt chạy đồng thời. Trần input cứng hạ mức giữ còn 0,10 USD; `guest_ai_global_concurrency` mặc định 10 và `guest_voice_per_minute` mặc định 2 cũng được nâng lên 30 và 6. `useCaptcha.take()` đang báo lỗi nếu token chưa về, phải đổi sang chờ token.

**Nói thật về "tự xóa sau 2 giờ"**: hàng trong database bị xóa và quyền truy cập file bị thu hồi khi hết giờ. Object trong Storage bị xóa theo hàng đợi, trễ thêm tối đa 2 giờ 5 phút (`DELETE_DELAY`, vì upload token sống 2 giờ), tức khoảng 4 giờ kể từ lúc vào. Hiện `store=False` chưa phải zero data retention: OpenAI giữ log giám sát lạm dụng tới 30 ngày. Sau khi bật ZDR ở G6, phần này không còn. Copy trong app không được hứa quá mức thực tế.

**Liên quan tới học sinh thật**: khách không khai tuổi, nên phải coi như có trẻ dưới 13 tuổi, và khách không có bước đồng ý nào. Xem [OD-15](#od-15--ai-dùng-sản-phẩm).

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
| SSM, EC2, log | AWS MCP theo owner xác nhận | **Chưa kiểm chứng**: `aws-mcp` lỗi kết nối ở mọi phiên, `aws sts` trên máy audit trả exit 253 |
| Cloudflare Turnstile | Trình duyệt của owner; máy audit không có API token | Đã đổi widget sang Invisible, không lưu credential |
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

**Lưu ý khi có học sinh thật**: [hướng dẫn Under-18](https://developers.openai.com/api/docs/guides/safety-checks/under-18-api-guidance) khuyên dùng model flagship mới nhất khi phục vụ trẻ vị thành niên, vì có lớp an toàn mới nhất. `gpt-6-luna` là model nhanh và rẻ nhất; flagship hiện là `gpt-6-astra`. Đây là khuyến nghị, không phải điều kiện bắt buộc. Plan giữ Luna theo OD-14 và bù bằng các tầng an toàn ngoài model. Nếu eval an toàn hoặc rubric không đạt, đây là điều đầu tiên nên xem lại.

## OD-15 — Ai dùng sản phẩm

**Trả lời**: Mặc định luôn là học sinh thật dùng. Tình huống mẫu chỉ là kịch bản text dạng Markdown.

**Áp dụng**: mọi thiết kế, copy và test coi người dùng là trẻ 11–17 thật với dữ liệu thật. Không còn thông báo kiểu "đừng nhập thông tin thật". Không tạo dữ liệu mẫu trên hosted. Sau khi mở, Grok không đọc nội dung của học sinh trên hosted.

**Khi nào mở**: sản phẩm được xây cho học sinh thật từ đầu, nhưng chỉ mở cho học sinh sau khi đủ các điều kiện ở [cổng G6](10-evaluation-and-quality-gates.md#cổng-g6-mở-cho-học-sinh-thật). Trước đó `GUEST_AUTH_ENABLED` và `SCHOOL_SIGNUP_ENABLED` để `false`, trang chủ hiện Tìm hỗ trợ và các số khẩn cấp. Hai điều kiện dưới đây không thể bỏ bằng quyết định sản phẩm.

**1. OpenAI zero data retention.** [Hướng dẫn Under-18](https://developers.openai.com/api/docs/guides/safety-checks/under-18-api-guidance) yêu cầu không xử lý dữ liệu cá nhân của trẻ dưới 13 tuổi hoặc dưới tuổi đồng ý số khi chưa bật ZDR, và OpenAI có quyền kiểm tra, cảnh báo, đình chỉ API. Nhóm 11–14 có trẻ dưới 13, và khách không khai tuổi, nên ZDR là bắt buộc cho toàn bộ sản phẩm. ZDR [cần OpenAI duyệt trước](https://developers.openai.com/api/docs/guides/your-data#data-retention-controls-for-abuse-monitoring), qua đội sales, rồi bật tại Settings → Organization → Data controls → Data Retention. `/v1/responses`, `/v1/audio/transcriptions`, `/v1/realtime` đều thuộc danh sách hỗ trợ. Code không cần đổi vì đã dùng `store=False`.

**2. Luật Bảo vệ dữ liệu cá nhân 91/2025/QH15**, hiệu lực 01/01/2026. Theo [bài phân tích trên LSVN](https://lsvn.vn/cong-bo-du-lieu-ca-nhan-cua-tre-tu-07-tuoi-phai-duoc-nguoi-dai-dien-dong-y-a167752.html), người đại diện theo pháp luật thực hiện quyền của chủ thể dữ liệu là trẻ em, trừ các trường hợp không cần đồng ý ở khoản 1 Điều 19, và phải ngừng xử lý khi người đại diện rút đồng ý. Đây là nguồn thứ cấp, chưa đọc nguyên văn. Khách không có bước đồng ý nào (OD-05), nên đây là chỗ dễ va chạm nhất. Nếu luật sư kết luận cần đồng ý của người đại diện cả với khách, phải thêm một bước vào luồng khách. Đồng thời phải chú ý trường hợp người gây hại chính là cha mẹ.

## OD-16 — Đăng ký tài khoản

**Mặc định, owner xem lại**: mở đăng ký cho học sinh sau G6. Khách chỉ giữ dữ liệu 2 giờ, nên Hồ sơ theo dõi nhiều ngày, là giá trị chính với học sinh thật, không dùng được nếu chỉ có chế độ khách.

- `POST /api/v1/school/signup`: email, mật khẩu, nhóm tuổi tự khai, qua Supabase. Không yêu cầu 18+. `POST /auth/signup` của hệ thống cũ giữ 403.
- Màn điều khoản có một ô xác nhận bố mẹ hoặc người giám hộ biết em dùng ứng dụng. Đây là tự khai, chưa phải xác minh đồng ý. Luật sư quyết định có đủ không ở G6.
- Em không hỏi được người giám hộ vì đang không an toàn ở nhà vẫn có chế độ khách và 111.
- Chưa chuyển dữ liệu khách sang tài khoản. Khách xuất PDF trước khi hết giờ.
- WS-10-T00 kiểm tra giới hạn gửi email xác nhận của Supabase.

Nếu muốn chỉ giữ chế độ khách, đặt `SCHOOL_SIGNUP_ENABLED=false`; khi đó Hồ sơ chỉ tồn tại 2 giờ.

