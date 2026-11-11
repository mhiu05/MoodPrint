# Knowledge evaluations

Benchmark này đánh giá retriever/corpus, tách khỏi chất lượng hội thoại của Companion.
Xem [kiến trúc retrieval](../../../README.md#kiến-trúc-hệ-thống),
[ingestion](../../ingestion/README.md) và [hướng dẫn kiểm thử](../../../README.md#kiểm-thử).

| Thành phần | Mục đích |
|---|---|
| `cases/benchmark_v2.jsonl` | Case tổng hợp có split dev/test; đọc cùng các bản đăng ký và label review trong `cases/`. |
| `run_v2.py` | Chạy cấu hình lexical, vector hoặc hybrid trên corpus version được chỉ định; ghi metric và khoảng tin cậy. |
| `tune_dev.py` | Điều chỉnh trên dev; không dùng test để chọn tham số. |
| `run_closure.py` | Các lượt closure có case/freeze và artifact riêng; đọc [giao thức v4](cases/CLOSURE-V4-REGISTRATION.md) trước khi chạy. |
| `metrics.py` | Hit/recall, MRR, nDCG và percentile latency. |
| `results/` | Kết quả kèm cấu hình; một file kết quả cũ không xác nhận corpus hiện tại đã đạt. |

`run_v2.py` nhận DB admin loopback từ stack test, pin `scope.corpus_version` để có
thể đánh giá corpus mà không publish. Cache embedding trên đĩa chỉ dành cho query
tổng hợp của benchmark; ứng dụng không cache query người dùng theo cách này.

Sau khi đã dựng corpus và có query cache phù hợp, có thể chạy dev mà không gọi Voyage:

```powershell
uv run python agent/evals/knowledge/run_v2.py --split dev --config locked --version kb-YYYYMMDD-NN --no-live
```

`--no-live` thất bại nếu thiếu embedding trong cache; đây không phải lệnh tạo cache.
Bỏ cờ có thể gọi Voyage và cần khóa cùng sổ ngân sách được cấp trước. Split test chỉ
chạy theo cấu hình đã khóa và giao thức đăng ký; không lặp lại test để tối ưu kết quả.

Kiểm tra contract, scoring gate, normalization, quyền truy cập và CLI offline nằm
trong [agent/tests/knowledge](../../tests/knowledge/). PostgreSQL integration tests
cần stack local riêng. Các cảnh báo về khả năng trả lời/no-results trong cấu hình
và artifact phải được giữ khi báo cáo chất lượng.
