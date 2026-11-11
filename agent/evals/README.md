# Companion evaluations

Xem [kiểm thử hệ thống](../../README.md#kiểm-thử) và
[kiến trúc runtime](../../README.md#kiến-trúc-hệ-thống). Các bộ đánh giá dùng dữ liệu tổng hợp;
không đưa dữ liệu học sinh thật vào fixtures hoặc kết quả public.

Tên sản phẩm trong các output lưu trữ đã được chuẩn hóa thành SafeVoice. Hash,
commit và provenance lịch sử vẫn mô tả lần chạy trước khi đổi tên; các tệp này
không phải bằng chứng đánh giá cho mã nguồn hoặc prompt hiện tại. Cần chạy lại
eval để tạo bộ kết quả và hash nhất quán cho phiên bản SafeVoice.

## Đường chạy offline

Unit tests trong `agent/tests` dùng official SDK `ScriptedModel`, không cần API key.
`run.py --suite deterministic` kiểm tra inventory/manifest và bộ quy tắc safety;
nó không tự chạy mọi case live bằng mô hình giả.

Product scenarios có entrypoint riêng chạy runtime SDK và công cụ thật với model
scripted, domain in-memory và HTTP fake cho phần cần response có cấu trúc:

```powershell
uv run python agent/evals/run.py --suite deterministic
uv run python agent/evals/product.py --out agent/evals/results/<new-product-offline-run>
```

`product.py` ghi kết quả hành động và hash prompt/source cho 20 kịch bản tiếng Việt
trong [product_cases.json](product_cases.json). Câu trả lời scripted không nhận điểm
chất lượng ngữ nghĩa; phần live chưa chạy được giữ `NOT_RUN`.

## Live eval và cách đọc kết quả

[run.py](run.py) hỗ trợ `--suite live`; đường này cần API key và tệp ngân sách do owner
cấp, đặt chỗ chi phí trước từng request và dừng khi chạm giới hạn. Mọi lời gọi dùng
`safevoice_shared.config.OPENAI_MODEL`, gồm compaction và smoke test. Không tự nâng
trần ngân sách để hoàn thành một bộ đánh giá.

Case nằm trong `cases/*.jsonl`. Kết quả ở `results/<run-id>/` gồm output, assertion
xác định và metadata về model, SDK, commit, prompt/tools version, corpus cùng hash
nguồn. Live harness mặc định vẫn dùng domain in-memory và fixture knowledge;
[real_knowledge.py](real_knowledge.py) là adapter pgvector được chọn riêng, có ngân sách
Voyage và chỉ chấp nhận DB loopback. Vì vậy “live” chỉ xác nhận đã gọi mô hình thật,
không mặc định xác nhận toàn bộ hệ thống hay retrieval là thật.

Coding agent đọc output và ghi `grades.jsonl` theo [rubric 0–3](rubric.md), không gọi
judge model. Chưa chấm không có nghĩa là đạt. Mỗi output thuộc các case nguy cơ cao
SC-04, SC-07, SC-09, SC-24 phải được đọc riêng, không lấy mẫu. Có thể đối chiếu
[provenance.py](provenance.py), [assertions.py](assertions.py) và
[harness.py](harness.py) để biết dữ kiện nào được thu thập.

[MANIFEST-RECONCILIATION.md](MANIFEST-RECONCILIATION.md) là bản ghi lịch sử của một đợt
đánh giá, không phải trạng thái ngân sách hay chứng nhận prompt hiện tại. Các kết quả
cũ cần được đọc theo phiên bản ghi trong chúng. Kho tri thức có
[benchmark và quy trình riêng](knowledge/README.md).
