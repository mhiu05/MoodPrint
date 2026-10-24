# Kế hoạch smoke test AI, bộ nhớ và STT

**Hiện tại:** chỉ có kiểm tra cấu hình lịch sử; chưa có request trả phí mới trong task này. `backend/tests/test_sdk_adapter.py`, `test_memory.py`, `test_embeddings.py`, `test_voice.py` là kiểm tra offline/mock hoặc PostgreSQL synthetic; không được gọi là provider live PASS. Các evidence cũ trong `docs/plans/validation-artifacts/live-ai/` là HISTORICAL.

## Trước live test

Chủ dự án chọn budget và đồng ý riêng cho từng provider. Chỉ synthetic text/audio/account. Công cụ `scripts/smoke_providers.py` đòi cả `--live --ack-billing`, mỗi lần chạy đúng **một** API request, không in nội dung response; lỗi chỉ in tên exception. Chạy từ `backend` với env bí mật riêng trên máy kiểm thử, không đưa key vào shell command hoặc log:

```powershell
uv run --locked python ../scripts/smoke_providers.py --provider openai --live --ack-billing
uv run --locked python ../scripts/smoke_providers.py --provider voyage --live --ack-billing
uv run --locked python ../scripts/smoke_providers.py --provider stt --live --ack-billing
```

Dự toán tối đa cho ba lệnh là 1 text response ngắn, 1 Voyage embedding cho một câu synthetic, 1 OpenAI transcription của 1 giây WAV synthetic, cộng phí tối thiểu/token rounding theo biểu giá lúc chạy. Không chạy tự động trong CI. Lệnh `backend/evals/voyage_live.py` và scenario live hiện có gửi nhiều request, **không** thay thế lệnh smoke một request khi chưa được duyệt budget. Kiểm tra Usage/Billing ở provider sau từng lệnh.

## Ma trận smoke sau khi duyệt

| Hạng mục | Offline trước | Live/staging sau |
| --- | --- | --- |
| OpenAI | SDK adapter, timeout/error, consent và no-content logs qua pytest | 1 request synthetic kiểm chứng auth/kết nối; thêm 1 lượt agent UI synthetic để kiểm response và SSE nếu budget cho phép. Kiểm lỗi 401/timeout bằng mock thay vì cố ý tạo live phí. |
| Voyage | Vector validation, lease/consent/isolation/revoke/delete qua `test_embeddings.py`, `test_memory.py` | 1 synthetic embedding; tạo 2 tài khoản synthetic trong staging và kiểm approved memory chỉ thuộc owner, không retrieval cross-user, disabled mode, invalidation sau xóa. Các truy vấn retrieval có thể gọi Voyage tiếp; ước lượng và duyệt số request riêng. |
| STT | `test_voice.py`, audio validator, WAV mono/PCM16/30 giây/3 MB, content-type, lỗi/timeout mock | 1 giây audio tổng hợp in-memory; sau đó một lượt UI synthetic nếu model được xác nhận. Không lưu/log raw audio. |

`backend/.env.example` hiện đặt `STT_MODEL=gpt-transcribe`, nhưng [OpenAI transcription API reference](https://platform.openai.com/docs/api-reference/audio) hiện liệt kê `gpt-4o-transcribe` và các model khác, **không xác nhận** tên `gpt-transcribe`. Trước khi bật `STT_ENABLED`, chủ dự án phải chọn model có quyền truy cập và chạy smoke riêng; template staging để trống model và tắt STT. Không suy ra live PASS từ checker cấu hình.

## Quyền riêng tư provider

OpenAI [Data controls](https://developers.openai.com/api/docs/guides/your-data) nói abuse monitoring có thể giữ customer content đến 30 ngày mặc định và ZDR là chế độ cấp tổ chức; `store=false` hoặc tắt tracing **không đồng nghĩa ZDR**. Voyage [FAQ](https://docs.voyageai.com/docs/faq) nêu opt-out lưu/training qua dashboard organization, yêu cầu điều kiện tài khoản; cần kiểm trạng thái thực trước khi gửi dữ liệu người dùng. Xác minh processing region, DPA và retention áp dụng cho chính tài khoản/provider trước bất kỳ test với dữ liệu thật. Chỉ memories đã được người dùng duyệt và query hiện tại được gửi khi tùy chọn tương ứng bật; không mở rộng consent.
