# Knowledge ingestion

Xem [kiến trúc kho tri thức](../../README.md#kiến-trúc-hệ-thống),
[cài đặt](../../README.md#cài-đặt-và-chạy-local) và [kiểm thử](../../README.md#kiểm-thử)
trước khi chọn corpus và môi trường. Ingestion là CLI quản trị, không tự chạy khi backend khởi động.

Chạy từ gốc repo. Mọi lệnh có `--target test-env` chỉ nhận database loopback; không có đích hosted.

## Cấu trúc

| Thư mục | Nội dung |
|---|---|
| `authored/*.md` | Thẻ biên soạn của MoodPrint (`licence_class = authored`). Mỗi thẻ có front matter TOML và các mục `##`. |
| `legal/*.md` | Chữ của văn bản quy phạm pháp luật, chép từ bản chính thức (`open_reuse`). Bản gốc nằm trong `legal/original/`. |
| `corpus/sources/*.toml` | Sổ đăng ký nguồn và bằng chứng giấy phép. |
| `corpus/manifest.toml` | **Sinh ra**, không sửa tay: `uv run python agent/ingestion/make_manifest.py`. |
| `synthetic/` | Corpus tổng hợp cho CI và E2E (HashingEmbedder). |

## Quy trình

Các lệnh dưới mô tả pipeline; bước `embed --embedder voyage` gọi dịch vụ có phí và
cần khóa/ngân sách nêu ở mục Voyage. Có thể dùng `--embedder hashing` cho corpus kiểm thử
tổng hợp; vector hashing không thay thế chất lượng semantic embedding thật.

```powershell
uv run python agent/ingestion/make_manifest.py
uv run python -m moodprint_agent.knowledge.ingest plan --manifest agent/ingestion/corpus/manifest.toml
uv run python -m moodprint_agent.knowledge.ingest build --manifest agent/ingestion/corpus/manifest.toml --out .local/corpus/build-1
uv run python -m moodprint_agent.knowledge.ingest embed --build .local/corpus/build-1 --embedder voyage --budget-tokens 60000
uv run python -m moodprint_agent.knowledge.ingest store --build .local/corpus/build-1 --manifest agent/ingestion/corpus/manifest.toml --target test-env --version kb-YYYYMMDD-NN
uv run python -m moodprint_agent.knowledge.ingest validate --target test-env --version kb-YYYYMMDD-NN
uv run python -m moodprint_agent.knowledge.ingest verify-citations --target test-env --version kb-YYYYMMDD-NN --manifest agent/ingestion/corpus/manifest.toml
uv run python -m moodprint_agent.knowledge.ingest publish --target test-env --version kb-YYYYMMDD-NN
```

Mỗi phiên bản là bất biến: sửa nội dung thì tạo số phiên bản mới. `rollback --to <version>` chỉ đưa lại một phiên bản đã `retired`.
`seed-synthetic` xuất bản corpus tổng hợp và **thay** phiên bản đang xuất bản; sau khi chạy E2E hãy `rollback` về corpus thật.

## Quy tắc nội dung

- Không đệm chữ để đủ số chunk. Mỗi thẻ trả lời một nhu cầu thông tin riêng; một bài test chặn câu dài lặp lại ở quá hai thẻ.
- `derived_from` chỉ ghi nguồn mà thẻ thực sự dùng, kèm vị trí. Thẻ không tự nhận đã "đối chiếu" với nguồn nào nếu chưa làm.
- Văn bản pháp luật: chỉ chép từ bản chính thức, ghi số trang và nói rõ ai đã đọc soát. Chưa đọc soát thì nêu "chưa có người đọc soát".
- `reference_only` và `unverified` không bao giờ vào chunk.

## Voyage

Chỉ chạy khi có khóa được phép dùng và cả sổ chi phí `.local/voyage-ledger.json` lẫn log `.local/voyage-ledger.jsonl` đã tồn tại. Guard hiện gắn với trần USD 1.00 của quy trình phát triển trước đây và mô hình `voyage-4`, chưa có CLI onboarding ngân sách mới. Thiếu file, embed dừng với `BudgetBlocked`; không xóa/tạo lại ledger để đặt lại chi tiêu. Tiến trình test không tự nạp khóa. Không dùng mô hình khác hay rerank khi chưa có phê duyệt riêng.

Đích `test-env` ưu tiên `TEST_ADMIN_DATABASE_URL`/`TEST_DATABASE_URL` trong environment. Nếu thiếu, nó tìm stack `kb` trước `.local/test.env`. Khi dùng foundation, thêm `--env-file .local/test.env` sau `uv run` cho các lệnh DB ở trên; xem [cài đặt provider](../../README.md#cài-đặt-và-chạy-local) để tránh nạp nhầm database local.

## Đánh giá

[Retrieval benchmark](../evals/knowledge/README.md): benchmark v2 có split dev/test,
`tune_dev.py` chỉ đọc dev, `run_v2.py` chạy cấu hình được chọn. Split test dành cho lượt
đã đăng ký trước, không dùng để điều chỉnh ngưỡng. Kết quả đánh giá cũ phải được đọc
cùng corpus, embedding model và cấu hình đã ghi trong artifact.
