# Knowledge ingestion

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

Chỉ chạy khi có khóa do owner cấp và sổ chi phí `.local/voyage-ledger.json` (trần USD 1.00, mô hình `voyage-4`). Tiến trình test không tự nạp khóa. Không dùng mô hình khác hay rerank khi chưa có phê duyệt riêng.

## Đánh giá

`agent/evals/knowledge/`: benchmark v2 đã khóa (`cases/`), `tune_dev.py` chỉ đọc split dev, `run_v2.py` chạy một cấu hình đã đăng ký. Split test chỉ chạy một lần cho cấu hình đã khóa.
