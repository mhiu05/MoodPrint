# Đánh giá matching và rollout

## Offline synthetic benchmark

[evals/matching](../../backend/evals/matching/README.md) so sánh frozen rollback scorer và v2, không gọi network/provider, không dùng dữ liệu thật. Dataset hiện tại có **60 persona** tổng hợp và **300 pair labels**. Có 12 persona v1-shaped, 6 sparse, 42 full v2.

Labels do **ba rule-based proxy raters**, có seeded disagreement; không phải ba người đã đánh giá. Một số tín hiệu proxy trùng input scorer nên gate đạt không chứng minh sản phẩm tìm bạn tốt hơn cho người thật.

Từ `backend/`, ghi report mới ra ngoài tracked fixture:

```powershell
uv run --locked python -m evals.matching.benchmark --out "$env:TEMP\moodprint-matching-report.json"
```

`evals.matching.generate` ghi lại dataset/labels; chỉ chạy khi chủ đích cập nhật fixture và review diff. Không regenerate để làm score đạt.

## Metrics và gates hiện tại

| Metric | Cách hiểu / target của harness |
| --- | --- |
| NDCG@5 | V2 ≥ V1 + 0,05 trên labels có sẵn |
| Precision@5 | Pair mean label ≥1,5 là relevant; đọc cùng coverage |
| Coverage | Viewer có ≥1 candidate; V2 không giảm so V1 |
| Exposure Gini | V2 không cao hơn V1 trong dataset |
| Reason faithfulness | 100% theo shared published item checks |
| Symmetry | 0 vi phạm scoring symmetry |
| Ranking p95 | Tại 600 synthetic personas <50 ms trong benchmark |
| Rater agreement | Krippendorff alpha trên proxy labels; không biến thành human agreement |

Benchmark 600 tạo bản sao/mutation từ 60 persona; không phải production load test 600 user. Timing phụ thuộc máy và contention; ghi môi trường/thời điểm, không sửa threshold sau khi thấy kết quả.

## Rollout và rollback

1. Giữ deterministic unit/API/privacy tests xanh.
2. Chạy benchmark với frozen dataset, lưu exact scorer/taxonomy/config và report.
3. Cần human labels/đánh giá thật trước quyết định chất lượng production; không dùng proxy gate làm approval duy nhất.
4. Có thể dùng `shadow`: phục vụ v1, log overlap@5/count tổng hợp với v2; không log IDs, tags hoặc private content.
5. Bật v2 bằng cấu hình được quản lý sau approval phù hợp, theo dõi failure/empty/exposure/request/accept metrics; rollback cấu hình về v1 khi cần.

`matching_stats_daily` chỉ lưu aggregate impressions/requests/accepts theo day/scoring version trong transaction. `scripts/report_beta_metrics.py` là công cụ đọc báo cáo; xem phạm vi script trước dùng database thật. Counter acceptance không tự chứng minh satisfaction, safety hoặc long-term friendship.

## Test lựa chọn

`test_matching_eval.py` dùng slice nhỏ cho harness CI. `test_scoring_v2.py`, `test_ranking.py`, `test_explain.py`, `test_matching_retrieval_v2.py`, `test_matching_stats.py` bảo vệ behavior. [Fullstack matching spec](../../frontend/tests/fullstack/matching-v2.spec.ts) xác minh HTTP/browser integration với synthetic actors.

Fullstack mặc định phục vụ v1. Để kiểm tra nhánh v2, đặt `E2E_MATCHING_SCORER=v2` cho cả harness/server và browser, rồi từ backend chạy `uv run --locked python ../scripts/test_fullstack.py matching-v2.spec.ts`; vẫn cần `TEST_DATABASE_URL` riêng như development runbook. Không dùng tên file `matching-v2.spec.ts` để suy ra v2 đã được chọn.
