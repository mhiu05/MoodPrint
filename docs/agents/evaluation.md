# Đánh giá và kiểm thử AI

## Phạm vi bằng chứng

| Lớp | Cách chạy | Chứng minh được |
| --- | --- | --- |
| Unit/contract | `uv run --locked pytest -q` | Policy, DTO, context, tools, lỗi và adapter với test doubles |
| PostgreSQL/API | Cùng pytest, có `TEST_DATABASE_URL` local `_test` | Transaction, ownership, consent, races, persistence |
| Synthetic fullstack | `uv run --locked python ../scripts/test_fullstack.py` từ backend | Browser → HTTP thật → FastAPI → PostgreSQL, SDK fake model |
| Offline result checker | `python -m evals.evaluate ...` | Định dạng kết quả, ID/version/coverage và một số canary |
| Live provider/eval | Opt-in, target/model/budget được cho phép | Kết nối/model/output thực tế cho dataset được chạy |

Pytest chủ động xóa cấu hình provider trong process test, không đọc `.env` để vô tình gọi model thật. PostgreSQL tests skip nếu không có URL; skipped không phải pass cho tích hợp.

## Dataset và cách đọc kết quả

[evals/dataset.py](../../backend/evals/dataset.py) chứa 60 tình huống tiếng Việt tổng hợp, 12/bot; chia calibration/development/heldout. Dataset và prompt variants là tài sản đánh giá có version. Không dùng tin nhắn thật hoặc context có định danh làm fixture.

[evals/README.md](../../backend/evals/README.md) mô tả offline A/B/C ablation và live A/B prompt comparison: đây là hai thí nghiệm khác nhau. A/B/C không cấp thêm quyền cho bot; Cầu Nối không được private memory để tăng điểm. Heldout đã sử dụng để đánh giá phải giữ evaluation-only, không tiếp tục tuning trên đó.

Ví dụ kiểm tra kết quả **đã có sẵn**, từ `backend/`:

```powershell
uv run --locked python -m evals.evaluate synthetic-results.jsonl --output offline-report.json
```

Đầu vào phải theo envelope trong README eval: `caseId`, `variant`, `synthetic`, `output`, metadata model/SDK/prompt/tool/context version. Không tạo output giả để lấp missing coverage. Checker không phải language judge, privacy certification hoặc bằng chứng release readiness.

## Live gate

Live runner trong [evals/live.py](../../backend/evals/live.py) yêu cầu opt-in; không dùng fake fallback hoặc ghi đè output. Trước khi chạy cần target/model được phép, giới hạn concurrency/cost, dataset synthetic, chỗ lưu kết quả và người chịu trách nhiệm đọc failures. Nhiệm vụ tài liệu này không tự cấp budget live.

Đánh giá người thật cần chấm role, relevance, source accuracy, factual calibration, tool choice, memory consent, context leakage, transitions và usefulness; ghi disagreement/adjudication. Trễ, usage và chi phí là số đo riêng; không suy ra từ câu trả lời. Leak, unauthorized action hoặc false success là lỗi phải chặn phát hành dù điểm trung bình tốt.

## Khi sửa agent

1. Đóng băng trường hợp tái hiện tổng hợp và expected authorization/source behavior.
2. Kiểm tra contract/runtime regression trước, sau đó fullstack với SDK fake model.
3. Lưu prompt/tool/context/evidence policy version đi kèm kết quả.
4. Chỉ chạy live comparison khi đã có budget/target approval; giữ model và limits nhất quán giữa variants.
5. Báo riêng deterministic tests, proxy checks, live result và các phần chưa kiểm chứng.

Matching không dùng model judge trong benchmark hiện tại; xem [matching evaluation](../matching/evaluation.md).
