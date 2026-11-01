# Eval lời hỏi thăm (P1-19) và tách bubble (P1-08) — model thật

Ngày 31/10/2026. Chỉ dữ liệu tổng hợp ([backend/evals/proactive/cases.py](../../../../backend/evals/proactive/cases.py): 62 case tuning = 5 trợ lý × 2 buổi × ≥ 6 tình huống, 8 case held-out không dùng để chỉnh prompt; 3 chuỗi 7 ngày đo lặp lại). Sinh qua đúng `SdkProvider.run_proactive` + validator nghiệp vụ của ứng dụng; chấm bằng rubric 8 tiêu chí bắt buộc. Giá chuẩn đã kiểm trên trang pricing chính thức (per 1M token: gpt-6-luna 0,10/0,01/0,50; gpt-6.1-terra 1/0,05/5; gpt-6.1-sol 2/0,10/10; gpt-6-astra 10/1/50). Lệnh: `python -m evals.proactive --live --confirm-live --max-usd 10 --streaks --generator gpt-6-luna --judge gpt-6-astra --output …`.

| Vòng | Prompt | Generator | Judge | Rubric bắt buộc (tất cả / held-out) | Bịa (tổng / nhật ký) | Chất lượng TB | Model p50 / p95 | Chi phí |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | a1 | gpt-6-luna (effort mặc định) | gpt-6-astra | 75,7 % / 62,5 % | 0 / 0 | 4,59 | 2,69 / 4,23 s | 1,17 USD |
| 2 | a2 | gpt-6-luna | gpt-6-astra (rubric hiệu chỉnh theo đặc tả) | 92,9 % / 87,5 % | 2 / 2 | 4,90 | 2,91 / 6,12 s | 1,15 USD |
| 3 | a3 (+effort `low`) | gpt-6-luna | gpt-6-astra | 95,7 % / 100 % | 1 / 0 | 4,90 | 1,90 / 2,57 s | 1,17 USD |
| 3' | a3 | gpt-6.1-terra | gpt-6-astra | 85,7 % / 75 % | 0 / 0 | 4,79 | 2,06 / 3,07 s | 1,27 USD |
| 4 | a4 | gpt-6-luna | gpt-6-astra | 94,3 % / 100 % | 1 / 1 | 4,90 | 1,78 / 2,74 s | 1,19 USD |
| 5a/5b | a5 | gpt-6-luna | gpt-6-astra | 92,9 % / 87,5 % · 92,9 % / 100 % | 0 / 0 · 0 / 0 | 4,84 · 4,96 | 1,79 / 2,70 s | 2,32 USD |
| **6a/6b** | **a6** (eval sinh lại 1 lần như production) | gpt-6-luna | gpt-6-astra | **100 % / 100 % · 100 % / 100 %** | **0 / 0 · 0 / 0** | 5,00 · 4,97 | 1,84 / 2,86 s | 2,44 USD |
| 6c | a6 | gpt-6-luna | **gpt-6.1-sol** (judge độc lập) | 98,6 % / 100 % | 0 / 0 | 4,99 | — | 0,25 USD |

Tách bubble (20 case P1-08, gpt-6-luna, 4 lần): hợp lệ 100/100/95/100 %, câu ngắn 1 bubble 100 % cả 4 lần, danh sách không bị tách 100/100/83/100 %; 2/80 lời gọi chat bị `response.incomplete (max_output_tokens)` (cả hai là yêu cầu liệt kê) → rủi ro R-15.

**Vòng 7–8 (sau chỉ đạo của owner: trần thêm ~3 USD, chỉ gpt-6-luna sinh, Claude Code tự chấm, bỏ câu đệm):**

| Vòng | Prompt | Validator | Sinh lại | Câu đệm | Đánh giá của Claude Code (8 tiêu chí, đọc toàn bộ 91 output) | Trùng 4-gram 7 ngày (Mây / Rủ Rê / Gương) | p50 / p95 | Chi phí |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 7 | a7 (bỏ câu đệm) | 70/70 | 0 | 0 | 68/70: `nhip-e-monday` bubble 2 lặp bubble 1; `hold-nhip-m-two` trích nguyên văn cả câu. Lỗi hệ thống: lặp nội dung giữa các ngày | 0,093 / 0,037 / 0,202 | 1,64 / 3,79 s | 0,020 USD |
| **8** | **a8** (`angle` xoay vòng) | **70/70** | 0 | **0** | **70/70**; ghi chú nhỏ: Nhịp đôi khi trích ngắn nguyên văn, một câu "một ngụm nước trong 10 phút tới" hơi gượng, Mây thường mở bằng "Chào buổi sáng" (tự nhiên) | **0,001 / 0,000 / 0,011** | 1,79 / 2,81 s | 0,020 USD |

**Tổng chi tiêu API: 11,06 USD / trần 100 USD** (sau chỉ đạo mới: 0,04 USD / 3 USD) (1.665 lời gọi, 11 lỗi/timeout của provider đã tính vào số liệu). Không có dữ liệu thật.

Phân tích → sửa (không sửa test để xanh): vòng 1 phần lớn lỗi là judge áp quy tắc ngoài đặc tả (ví dụ câu mẫu của Mây trong [07 §5](../phase-1/07-persona-behaviors-and-prompts.md) bị chấm "hai gợi ý") → hiệu chỉnh rubric bám đặc tả; lỗi thật được sửa ở prompt/validator: hai hành động nối bằng "và", trích nguyên văn dài, mở đầu lặp tên thứ (a2); **gán điều đã ghi hôm qua thành "sáng nay"** → luật validator `wrong_day` + prompt (a3); effort `low` giảm p95 4,2 → 2,6 s và token output 61 %; giả định đồ vật "trước mặt" (a4); nối cảm xúc với sự việc bằng "vì" = suy diễn nguyên nhân (a5); **Rủ Rê gắn nhãn sai để né `avoidChallengeKinds`** (bắt được nhờ held-out) → định nghĩa từng loại trong prompt + kiểm nội dung trong validator (a6). gpt-6.1-terra kém hơn gpt-6-luna trên cùng bộ case với chi phí sinh gấp 10 ⇒ giữ `OPENAI_MODEL` (OD-12), không nâng model.

Đã xử lý ở a7–a8: câu đệm "không cần trả lời đâu" (0 lần ở vòng 7–8, validator chặn nếu tái xuất hiện) và lặp nội dung giữa các ngày. Timeout 30 s không token của API xuất hiện ~1–3 % lời gọi ở concurrency 4 — production tự retry theo backoff.
