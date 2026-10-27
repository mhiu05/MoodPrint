# Retrieval, scoring và ranking

## 1. Input hợp lệ

Public profile có interests, values, style, goal, languages, activities, availability, strictGoal. Multi-select nhận tag duy nhất thuộc taxonomy. Draft áp dụng maximum; publish áp dụng minimum. Taxonomy là dữ liệu versioned, không do model suy luận từ nội dung riêng tư.

[taxonomy.py](../../backend/app/modules/profiles/taxonomy.py) validate categories/labels/limits và similarity ranges khi import. Unknown tag không được im lặng đưa vào similarity matrix. V1-shaped profiles thiếu v2 optional facets vẫn được hỗ trợ theo defaults.

## 2. SQL eligibility retrieval

[eligible_peers](../../backend/app/modules/social/retrieval.py) chỉ lấy user khác viewer, active adult, không deletion pending/social restriction, có published profile valid/current và MATCH consent enabled/version khớp. Cần ít nhất một ngôn ngữ chung; strictGoal ở một trong hai phía yêu cầu goal bằng nhau.

Loại peer nếu có block hai chiều, cooldown pair, room open hoặc pending request theo điều kiện service/retrieval. Profile quá 180 ngày bị ẩn đến khi xác nhận lại. Last seen quá 30 ngày bị loại; `NULL` có grace đến hằng `LAST_SEEN_ENFORCED_FROM = 2026-12-31T00:00:00Z` trong mã hiện tại. Đây là mốc code cần xem lại khi vận hành, không phải retention policy.

Scan tối đa **1.000** peer theo user ID; shortlist tối đa **10**, response tối đa **5**. Hệ thống không rank toàn bộ database ngoài cap này. Sau ranking, route lấy canonical account gates và chạy lại exclusions/version dưới lock trước cấp ref.

## 3. V1 rollback

`MATCHING_SCORER=v1` dùng `scoring_compat` (`rules-v1.1`): exact overlap trên taxonomy hiện hành, hard goal equality, score nguyên tối thiểu 30. Rank giảm theo điểm, tie theo peer UUID. Nó không dùng v2 soft-goal similarity, cold start hoặc MMR. `scoring.py` giữ frozen v1 oracle; phân biệt hai file khi so sánh benchmark.

## 4. Rules-v2

Gọi `w` là trọng số, `x` là component, `C` là tổng trọng số component có mặt:

```text
raw = sum(w[k] * x[k]) / C
score = raw * (0.9 + 0.1 * C)
```

| Component | Weight | Cách tính |
| --- | --- | --- |
| I: interests | 0,30 | Trung bình hai chiều best-match taxonomy similarity |
| V: values | 0,20 | Số tag chung / min(số tag mỗi bên); thiếu thì 0 |
| G: goal | 0,15 | Curated goal compatibility; same goal = 1 |
| P: activities | 0,15 | Overlap / min; bỏ component nếu một bên không chọn |
| S: style | 0,10 | Curated style compatibility; same style = 1 |
| T: availability | 0,10 | Overlap / min; bỏ component nếu một bên không chọn |

Interest similarity: exact tag 1; curated override nếu có; cùng category mặc định 0,5; ngoài category 0. Với A/B là tập interests:

```text
I = (sum_a max_b sim(a,b) + sum_b max_a sim(b,a)) / (len(A)+len(B))
```

Đây là hàm đối xứng. Component I/V/G/S luôn nằm trong coverage; P/T optional. Ví dụ hai profile giống nhau ở I/V/G/S và không chọn activity/availability: C=0,75, raw=1, score=0,975. Bỏ optional data không cho điểm hoàn hảo 1 và không bị coi là overlap sai.

Candidate cần score **≥0,30** và ít nhất một **exact shared item** thuộc interests/values/activities để có lý do trung thực. Cùng category hoặc availability một mình không đủ. Label `many` khi score ≥0,60, còn lại `some`. API không trả số score.

## 5. Ranking và diversity

`rank_score = score + cold_start_boost - load_penalty`:

- Boost 0,03 nếu first publication trong 7 ngày gần nhất.
- Penalty 0,05 × max(0, pending incoming − 2).
- Prefilter pool tối đa `limit × 5`, sau đó MMR với λ=0,85.
- Redundancy là interest component lớn nhất với candidate đã chọn.
- Tie dùng SHA256(viewer ID, peer ID, ngày local của viewer), ổn định trong ngày và thay đổi theo viewer/ngày.

Các biện pháp này điều chỉnh exposure trong tập đã retrieval, không chứng minh fairness toàn dân số. Không log IDs/tags/scores để đo shadow overlap.

## 6. Giải thích

[explain.reasons](../../backend/app/modules/matching/explain.py) tối đa ba lý do, ưu tiên nhóm activity → interest → value → same style → availability; lấy một lý do mỗi nhóm trước, rồi thêm interest/value nếu còn chỗ. Chỉ nhắc shared published items hoặc component style thật. `sharedActivities` trên card là lựa chọn hỗ trợ trải nghiệm, không cho phép tự mở activity/room.

Test: `test_scoring_v2.py`, `test_ranking.py`, `test_explain.py`, `test_matching_retrieval_v2.py`, `test_matching_privacy.py`, `test_matching_compatibility.py`. Xem [evaluation](evaluation.md) trước quyết định đổi scorer production.
