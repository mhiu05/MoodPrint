# 12 — Quyết định cần owner

Mỗi mục có phương án và đề xuất. Mặc định an toàn cho biết Grok làm gì nếu chưa có trả lời. Mục đánh dấu **Chặn** nghĩa là Grok phải dừng khi tới gate tương ứng.

| ID | Quyết định | Chặn gate | Đề xuất ngắn |
| --- | --- | --- | --- |
| OD-01 | Chuyển staging hiện tại sang demo | G5 | Chuyển, sau khi kiểm tra tài khoản đang hoạt động |
| OD-02 | Ai duyệt template và thẻ KB | G1, G2 | Owner chỉ định một người có chuyên môn |
| OD-03 | Ranh giới chặn upload nội dung tình dục | G2 | Chặn khi tự khai hoặc khi phiên, case có nhãn |
| OD-04 | Nhà cung cấp TTS | G3 | FPT.AI nếu bake-off đạt |
| OD-05 | Chế độ khách trên staging | G5 | Có nếu cấu hình guest sẵn; nếu không, chỉ Tìm hỗ trợ |
| OD-06 | Hướng hình ảnh | WS-09 | Hướng A |
| OD-07 | Snapshot nguồn để ở đâu | Không | `.tmp/`, không sửa `.gitignore` |
| OD-08 | Ngưỡng eval an toàn | G1 | Chốt sau baseline |
| OD-09 | Bật branch protection | Không | Bật |
| OD-10 | Tóm tắt nháp chạy qua agent | Không | Đồng ý |
| OD-11 | Trần chi phí eval live | G1 | 5 USD mỗi gate |
| OD-12 | Bàn giao credential | G5 | Danh sách ở dưới |
| OD-13 | Áp engine an toàn cho chat production | Không | Làm ngay sau MVP |

## OD-01 — Chuyển staging sang demo

`moodprint.duckdns.org` đang chạy MoodPrint 18+, dùng chung Supabase với dữ liệu có thể là thật. Profile demo khóa mọi tài khoản không có `school_profiles` khỏi app. Dữ liệu không bị xóa.

| Phương án | Ưu | Nhược |
| --- | --- | --- |
| A. Chuyển staging hiện có sang `APP_PROFILE=school_safety_demo` | Không thêm hạ tầng; đúng prompt | Tài khoản hiện có không dùng được app trong thời gian demo; dữ liệu demo nằm chung DB |
| B. Subdomain, service riêng cùng EC2 | Hai bản cùng chạy | Cần sửa Caddyfile, compose trên host; thêm RAM |
| C. Project Supabase riêng | Tách dữ liệu sạch | Thêm provisioning, migration từ đầu |

**Đề xuất**: A cho MVP. Owner kiểm tra có người dùng đang hoạt động không. C trước khi thí điểm thật.

**Mặc định**: Grok không flip profile trên staging khi chưa có xác nhận.

## OD-02 — Ai duyệt template và thẻ KB

Grok không được tự điền `reviewed_by`. Không có người duyệt thì không có thẻ `approved`, KB rỗng, G2 không qua được.

| Phương án | Ưu | Nhược |
| --- | --- | --- |
| A. Chuyên gia tâm lý học đường và người có kiến thức pháp lý | Đúng nhất | Cần tìm người, có thời gian chờ |
| B. Owner tự duyệt, ghi rõ giới hạn | Nhanh | Không phải đánh giá chuyên môn; phải ghi trong tài liệu dự thi |
| C. A cho template khẩn cấp và thẻ pháp lý, B cho thẻ kỹ năng và nền tảng | Cân bằng | Hai luồng |

**Đề xuất**: C. **Chặn** G1 (template) và G2 (thẻ).

Cũng cần người thực hiện `manual_capture` trên TikTok, Zalo, Facebook, Messenger, Instagram, YouTube, Discord.

## OD-03 — Ranh giới chặn upload nội dung tình dục

Spec cấm upload ảnh hoặc video nội dung tình dục liên quan trẻ em. Không có công cụ tự động nhận diện; không được gửi ảnh như vậy tới model. Câu hỏi còn mở: ảnh chụp **tin nhắn** quấy rối bằng chữ có được lưu không.

| Phương án | Hành vi |
| --- | --- |
| A. Chỉ chặn khi học sinh tự khai có nội dung hình ảnh tình dục, hoặc phiên/case có nhãn `sexual_abuse_exploitation` | Vẫn lưu được tin nhắn quấy rối bằng chữ ở các case khác |
| B. Chặn mọi upload trong case có hành vi `sexual_harassment` | An toàn hơn, nhưng mất bằng chứng tin nhắn |

**Đề xuất**: A. Tài liệu dự thi phải nói rõ đây là biện pháp giảm rủi ro, không phải đảm bảo. Nên hỏi người duyệt ở OD-02.

**Mặc định**: A.

## OD-04 — Nhà cung cấp TTS

OpenAI TTS tắt 06/01/2027. Realtime không đảm bảo đọc nguyên văn. Xem [08](08-speaking-practice-design.md).

| Phương án | Ưu | Nhược |
| --- | --- | --- |
| A. FPT.AI | Giá công khai, miễn phí 100.000 ký tự/tháng, nhà cung cấp Việt Nam | API có thể bất đồng bộ; điều khoản chưa đọc |
| B. Azure | API đồng bộ quen thuộc | Cần tài khoản; giá và giọng vi-VN chưa xác minh |
| C. Google Chirp 3 HD | 1M ký tự miễn phí/tháng | vi-VN chưa xác nhận |
| D. Tắt TTS, chỉ hiện chữ | Không phụ thuộc | Mất phần "nghe" của Luyện nói |

**Đề xuất**: A nếu bake-off đạt; D là phương án dự phòng. Owner cấp API key qua kênh runtime.

**Mặc định**: `TTS_PROVIDER=none`. Mọi thứ vẫn chạy, chỉ không có tiếng. G3 không đạt phần TTS.

## OD-05 — Chế độ khách trên staging

Guest cần CAPTCHA, `GUEST_ABUSE_HMAC_KEY`, `GUEST_DAILY_BUDGET_USD`, `GUEST_PRICING_JSON`. Tìm trong tài liệu không xác định được staging đã đủ các giá trị này hay chưa (UNKNOWN). Guest ép hội thoại tạm, nhưng metadata vẫn lưu tới khi cleanup; phải nói thật như [01 §7](01-codebase-audit.md#7-guest-thật-sự-lưu-gì-o10).

| Phương án | Hành vi |
| --- | --- |
| A. Bật nếu cấu hình sẵn | Thử Trợ lý không cần tài khoản |
| B. Tắt | Chỉ Tìm hỗ trợ công khai và tài khoản demo |

**Đề xuất**: A nếu đủ cấu hình; nếu không, B cho đợt đầu.

**Mặc định**: B.

## OD-06 — Hướng hình ảnh

Xem [09 §1](09-ux-and-user-flows.md#1-hướng-hình-ảnh). **Đề xuất**: A "Góc yên", giữ token hiện có.

**Mặc định**: A.

## OD-07 — Snapshot nguồn để ở đâu

| Phương án | Ưu | Nhược |
| --- | --- | --- |
| A. `.tmp/kb/raw/`, đã gitignore | Không sửa `.gitignore`; không phát hành lại nguồn | Snapshot chỉ ở máy người chạy |
| B. Thêm `kb/sources/raw/` vào `.gitignore` | Đường dẫn gọn | Cần sửa `.gitignore` |
| C. Lưu trong kho riêng tư | Bền vững | Thêm hạ tầng |

**Đề xuất**: A; manifest giữ sha256. **Mặc định**: A.

## OD-08 — Ngưỡng eval an toàn

Đề xuất ở [10](10-evaluation-and-quality-gates.md). Grok chạy baseline, báo số thật, owner chốt. **Chặn** G1.

## OD-09 — Branch protection

`main` không có protection. Giới hạn của Grok hiện dựa vào kỷ luật. **Đề xuất**: bật yêu cầu PR và check `verify`. Workflow publish chỉ cần push vào main nên không bị ảnh hưởng. **Mặc định**: giữ nguyên, Grok tuân thủ quy tắc.

## OD-10 — Tóm tắt nháp chạy qua agent

Prompt chỉ cho phép bốn loại lượt gọi không phải agent. Tóm tắt case và tóm tắt phiên luyện nói không thuộc bốn loại đó.

**Thiết kế**: cả hai là lượt của chính agent `troly`, có prompt riêng, không tool ghi, đi qua postcheck. Không phát sinh lượt gọi loại mới. Lý do cần: học sinh cần bản tóm tắt để đọc lại và chuyển cho người lớn; template không tạo được.

**Đề xuất**: đồng ý. **Mặc định**: đồng ý, vì không vi phạm định nghĩa ở §2 của prompt.

## OD-11 — Trần chi phí eval live

Ước tính: eval an toàn 300 mẫu dưới 0,10 USD theo giá niêm yết; eval hội thoại và smoke vài USD. Ledger nội bộ tính bảo thủ cao hơn. **Đề xuất**: 5 USD mỗi gate, tổng 20 USD. Mọi runner live bắt buộc `--confirm-live --max-usd`. **Mặc định**: Grok không chạy live khi chưa có con số. **Chặn** G1 phần classifier.

## OD-12 — Bàn giao credential

| Credential | Dùng cho | Cách cấp |
| --- | --- | --- |
| `DATABASE_MIGRATION_URL`, `SUPABASE_URL` | `apply_supabase_review.py --apply` | Environment của process, không qua command line |
| Quyền ghi SSM `/moodprint/staging/runtime` | Đặt `APP_PROFILE`, cờ, key | Owner tự làm, hoặc cấp quyền tạm |
| Auth Admin key | `scripts/seed_school_demo.py` | Environment |
| `JOURNAL_STORAGE_KEY` có trong SSM không | Upload bằng chứng | Owner xác nhận (UNKNOWN) |
| TTS API key | WS-08 | SSM |
| Quyền SSM Session trên EC2 | Xem log, rollback | Owner |

Với AWS: Region của project phải được xác nhận tại **AWS Settings > View all projects > Overview > Additional Info > Region**. Code `release_gate.py` ghi `ap-southeast-2` (INFERRED là Region hiện tại). Xem [release-runbook](grok-handoff/release-runbook.md).

**Đề xuất**: owner tự cập nhật SSM và áp SQL theo lệnh Grok chuẩn bị, hoặc cấp credential có thời hạn.

**Chặn** G5.

## OD-13 — Áp engine an toàn cho chat production

Lỗ hổng ở [01 §4](01-codebase-audit.md#4-lỗ-hổng-an-toàn-ưu-tiên-số-1-o4) vẫn tồn tại trong profile `default`, vì prompt yêu cầu giữ hành vi production. Người dùng 18+ cũng có thể gặp khủng hoảng. **Đề xuất**: sau MVP, mở một workstream riêng để dùng tầng rule và template cho profile mặc định. **Mặc định**: không đổi.
