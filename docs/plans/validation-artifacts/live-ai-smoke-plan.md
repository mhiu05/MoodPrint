# Live AI smoke preparation — chưa được bật

> Historical preparation before the authorized live run. Superseded by [24Oct2026 live evaluation](live-ai/final-evaluation.md), [usage](live-ai/performance-usage.json), and [local0006 accounting rehearsal](live-ai/accounting-local-verification.json). Fixed-budget permission gates in this historical draft do not override the user's later explicit authorization. New remote SQL still requires separate approval.

24/10/2026, Asia/Bangkok. Model đang cấu hình: `gpt-6-luna`; OpenAI key đã có, không cần cung cấp lại. `AI_ENABLED=false`, `STT_ENABLED=false`; chưa gọi live provider.

## Privacy đã kiểm tra được và phần còn thiếu

Code hiện tại dùng Responses qua Agents SDK0.24.0, `store=False`, tracing disabled/sensitive tracing false, retries0, buffered output và không lưu transcript vào PostgreSQL. Fake transport tests kiểm outbound mapping; đây không phải bằng chứng privacy settings của tài khoản OpenAI đã được xác minh.

Theo [OpenAI Data Controls](https://developers.openai.com/api/docs/guides/your-data), application state và abuse-monitoring retention là hai cơ chế riêng. `store=false` không tự chứng minh Zero Data Retention. Abuse-monitoring logs mặc định có thể giữ prompts/responses tối đa30 ngày, với ngoại lệ theo tài liệu. ZDR/MAM cần được OpenAI chấp thuận và có cấu hình ở organization/project; các giới hạn endpoint/model vẫn áp dụng. Chưa kiểm tra Data Controls của organization/project gắn với key hiện có, nên gate account privacy vẫn BLOCKED.

## Smoke dự kiến sau khi đủ gates

1. Supabase migration/runtime/Auth E2E PASS và có actor synthetic tự khai báo tuổi/consent hợp lệ; không dùng dữ liệu người thật.
2. Ghi bằng chứng account/project Data Controls, endpoint/region/retention được duyệt; không thay đổi privacy settings ngầm.
3. Người dùng cấp một mức ngân sách USD cụ thể và số requests tối đa. Chưa có budget được duyệt; không tự đặt mức tiền thay người dùng.
4. Đối chiếu giá model hiện hành, input/output caps và reservation ceiling trước khi bật. Durable accounting chưa hoàn tất; smoke phải có counter hạn định, uncertainty record và không retry provider lỗi.
5. Một prompt synthetic ngắn, một bot Mây, không tools/memory/audio, không background/conversations API; dùng key/model sẵn có. Bật cục bộ theo phạm vi được duyệt, không sửa default feature flags để mở cho mọi người.
6. Ghi model/version, request count, SDK usage thực nhận, estimated cost theo bảng giá ghi ngày, latency và terminal status; không log prompt/reply/key/headers. Không dùng response text làm evidence thay cho usage/status.
7. Chạy cancellation/revoke một cách có giới hạn ngân sách riêng nếu được duyệt; xác nhận không late final/tool. Sau smoke đóng context và kiểm feature flags trở lại trạng thái được duyệt.

STT có review/usage gate riêng; smoke text không phê duyệt voice hoặc processor deletion. Chưa thực thi smoke/eval A/B/C và không tuyên bố live M1 PASS.
