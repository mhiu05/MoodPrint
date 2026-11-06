# 12 — Quyết định của owner

Cập nhật 06/11/2026 sau phản hồi của owner. Mỗi mục có trạng thái và mặc định. Grok đi theo mặc định khi chưa có trả lời, trừ mục ghi **Chặn**.

| ID | Quyết định | Trạng thái | Kết quả hoặc mặc định |
| --- | --- | --- | --- |
| OD-01 | Chuyển staging hiện tại sang demo | **Đã chốt** | Giữ tên staging, bản chất là demo, chạy model thật |
| OD-02 | Ai duyệt template và thẻ KB | **Mở, chặn G5** | Owner duyệt một lượt; Grok chuẩn bị bảng duyệt, không tự duyệt |
| OD-03 | Ranh giới chặn upload nội dung tình dục | Mặc định | Chặn khi tự khai, hoặc phiên/case có nhãn |
| OD-04 | Nhà cung cấp TTS, STT | **Đã chốt** | Dùng `OPENAI_API_KEY` hiện có cho cả hai |
| OD-05 | Chế độ khách trên staging | Mặc định | Bật nếu SSM đủ cấu hình guest; nếu không, chỉ Tìm hỗ trợ |
| OD-06 | Hướng hình ảnh | **Đã chốt quy trình** | Làm theo impeccable; hướng A là brief khởi đầu |
| OD-07 | Snapshot nguồn để ở đâu | Mặc định | `.tmp/`, không sửa `.gitignore` |
| OD-08 | Ngưỡng eval an toàn | Mặc định | Dùng ngưỡng đề xuất; không đạt thì báo owner |
| OD-09 | Bật branch protection | Mặc định | Giữ nguyên, Grok tuân thủ quy tắc |
| OD-10 | Tóm tắt nháp chạy qua agent | Mặc định | Đồng ý |
| OD-11 | Trần chi phí eval live | **Đã chốt** | Dưới 3 USD tổng; trần kỹ thuật 2,80 USD |
| OD-12 | Bàn giao credential | **Đã chốt phần lớn** | Supabase MCP, AWS MCP; xem bên dưới |
| OD-13 | Áp engine an toàn cho chat production | Mặc định | Không đổi; làm sau MVP |
| OD-14 | Model của agent | Mặc định, đổi được qua env | `gpt-6.1-terra` cho agent, `gpt-6-luna` cho lượt phụ |

## OD-01 — Staging là môi trường demo

Owner chốt: giữ tên staging, bản chất là demo, vẫn chạy model thật.

Hệ quả: tài khoản hiện có không vào được app khi profile demo bật, dữ liệu của họ không bị xóa. Dữ liệu demo nằm chung database. Hạng mục tách database thuộc cổng trước thí điểm thật ở [04](04-feature-gap-analysis.md).

## OD-02 — Ai duyệt template và thẻ KB

Grok không được tự điền `reviewed_by`. Vì đây là demo, đề xuất **owner tự duyệt** và ghi rõ giới hạn trong tài liệu dự thi. Duyệt bởi chuyên gia là việc của giai đoạn thí điểm.

Để không chặn phát triển:

- WS-03, WS-05 phát triển và eval được với nội dung `draft`, cờ `--include-draft` chỉ dùng trong eval local.
- Grok chuẩn bị `evidence/content-review.md`: mỗi template và thẻ một dòng, kèm nguồn.
- **Chặn G5**: image chỉ đóng gói nội dung đã duyệt. Cần ít nhất 40 thẻ approved và toàn bộ template khẩn cấp.

Việc thu thập `manual_capture` trên TikTok, Zalo, Facebook, Messenger, Instagram, YouTube, Discord cần người thao tác trên app thật. Nếu nhóm không kịp đủ 7 nền tảng, tối thiểu Zalo, TikTok, Facebook phục vụ demo.

## OD-03 — Ranh giới chặn upload

Spec cấm upload ảnh hoặc video nội dung tình dục liên quan trẻ em. Không có công cụ tự động nhận diện, không được gửi ảnh như vậy tới model.

| Phương án | Hành vi |
| --- | --- |
| A | Chặn khi tự khai có nội dung hình ảnh tình dục, hoặc phiên/case có nhãn `sexual_abuse_exploitation`. Vẫn lưu được tin nhắn quấy rối bằng chữ ở case khác |
| B | Chặn mọi upload trong case có hành vi `sexual_harassment` |

**Mặc định**: A. Tài liệu dự thi phải nói đây là biện pháp giảm rủi ro, không phải đảm bảo.

## OD-04 — TTS và STT dùng OpenAI

Owner chốt dùng key OpenAI hiện có, không thêm nhà cung cấp. Ràng buộc kỹ thuật và cách xử lý ở [08](08-speaking-practice-design.md):

- `gpt-4o-mini-tts` shutdown 06/01/2027 nên chỉ là phương án phụ.
- Đường chính là `gpt-realtime-2.1-mini`. Đây là model sinh giọng nên backend so transcript với văn bản đã duyệt trước khi phát.

Cần owner nghe thử giọng tiếng Việt một lần trước G3.

## OD-05 — Chế độ khách

Guest cần CAPTCHA, `GUEST_ABUSE_HMAC_KEY`, `GUEST_DAILY_BUDGET_USD`, `GUEST_PRICING_JSON`. Grok kiểm tra **tên khóa** trong SSM qua AWS MCP, không in giá trị. Guest ép hội thoại tạm; metadata vẫn lưu tới khi cleanup, phải nói thật như [01 §7](01-codebase-audit.md#7-guest-thật-sự-lưu-gì-o10).

**Mặc định**: đủ cấu hình thì bật; thiếu thì chỉ có Tìm hỗ trợ công khai và tài khoản demo.

## OD-06 — Hướng hình ảnh

Owner yêu cầu tham khảo impeccable. Quy trình ở [09 §1](09-ux-and-user-flows.md#1-hướng-hình-ảnh-và-quy-trình-impeccable). Brief khởi đầu là hướng A "Góc yên". Owner xem ảnh chụp ở G4.

## OD-07 — Snapshot nguồn

**Mặc định**: `.tmp/kb/raw/`, đã được gitignore. Manifest giữ sha256. Không phát hành lại nguồn.

## OD-08 — Ngưỡng eval an toàn

**Mặc định**: áp ngưỡng ở [10](10-evaluation-and-quality-gates.md). Grok chạy baseline, chỉnh rule trên `dev`. Nếu `holdout` không đạt sau khi đã dùng hết phần ngân sách cho hạng mục này, dừng và báo owner kèm số thật.

## OD-09 — Branch protection

`main` không có protection. Giới hạn của Grok dựa vào kỷ luật. Nên bật yêu cầu PR và check `verify`. **Mặc định**: không đổi.

## OD-10 — Tóm tắt nháp chạy qua agent

Prompt chỉ cho phép bốn loại lượt gọi không phải agent. Tóm tắt case và tóm tắt phiên luyện nói là lượt của chính agent `troly`, không tool ghi, đi qua postcheck, nên không phát sinh loại lượt mới. **Mặc định**: đồng ý.

## OD-11 — Trần chi phí eval live

Owner chốt: **dưới 3 USD**. Áp dụng cho mọi lần chạy eval tốn tiền, cộng dồn qua các WS. Phân bổ ở [10 §Ngân sách](10-evaluation-and-quality-gates.md#ngân-sách-eval-live). Trần kỹ thuật 2,80 USD do `evals/budget.py` cưỡng chế.

Smoke trên staging và diễn tập demo là vận hành, không phải eval. Chúng nằm trong `AI_DAILY_BUDGET_USD`, được ghi chi phí riêng ở release note.

## OD-12 — Credential

| Việc | Đường đi | Trạng thái |
| --- | --- | --- |
| SQL hosted | Supabase MCP. Đã kiểm tra: chạy bằng role `postgres`, là chủ các bảng `moodprint`, có quyền CREATE | Sẵn sàng |
| SSM, EC2, log | AWS MCP theo owner xác nhận | **Chưa kiểm chứng trong phiên audit**: `aws-mcp` timeout, `aws sts` trên máy audit trả exit 253 |
| Auth Admin cho seed | Khóa server trong SSM, đọc vào RAM, không in | Cần kiểm tra `JOURNAL_STORAGE_KEY` có phải khóa server đủ quyền Auth Admin không |
| OpenAI, Voyage | Đã có trong SSM theo tài liệu release 05/11/2026 | Grok kiểm tra tên khóa |

Region của project xác nhận tại **AWS Settings > View all projects > Overview > Additional Info > Region**. Nếu không xác nhận được, kiểm tra `~/.aws/config`. Code và `deployment.conf.example` ghi `ap-southeast-2`.

Nếu MCP không chạy được SQL nguyên văn, hoặc AWS MCP không truy cập được SSM: dừng và báo owner, không tìm đường vòng.

## OD-13 — Engine an toàn cho chat production

Lỗ hổng ở [01 §4](01-codebase-audit.md#4-lỗ-hổng-an-toàn-ưu-tiên-số-1-o4) vẫn còn trong profile `default`. Nên mở workstream riêng sau MVP. **Mặc định**: không đổi.

## OD-14 — Model của agent

Owner yêu cầu độ thông minh cao. `gpt-6-luna` là model tối ưu cho tác vụ khối lượng lớn. `gpt-6.1-terra` được mô tả là nhanh, viết rõ và tự nhiên, giá cao hơn 10 lần ở input và output.

| Vai trò | Model | Lý do |
| --- | --- | --- |
| Agent `troly` | `gpt-6.1-terra`, `reasoning.effort=medium` | Chất lượng hội thoại tiếng Việt, gọi tool |
| Classifier, verifier | `gpt-6-luna` | Cấu trúc đơn giản, rẻ, nhanh |

`ASSISTANT_MODEL` đổi qua env sang `gpt-6-luna` hoặc `gpt-6.1-sol` mà không sửa code. Eval so sánh Luna và Terra trên cùng kịch bản trong trần chi phí. Chọn cuối theo kết quả, không theo tên model.
