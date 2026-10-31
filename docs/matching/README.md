# Matching và kết nối người thật

Matching dùng quy tắc xác định trên **published public profiles**, không dùng embedding, LLM, mood, AI memories hay chat history. Tìm được candidate không tự tạo lời mời; người dùng chủ động xem thẻ, gửi/nhận lời mời rồi mới có room nhắn tin.

```text
Public profile draft
  -> preview + digest + expiry
  -> publish snapshot + consent/version
  -> SQL eligibility retrieval
  -> deterministic scoring + ranking
  -> locked recheck + opaque candidate ref
  -> request -> accept -> open connection
```

| Thành phần | Nguồn |
| --- | --- |
| Public DTO/validation | [social/schemas.py](../../backend/app/modules/social/schemas.py) |
| Taxonomy và similarity | [taxonomy.py](../../backend/app/modules/profiles/taxonomy.py), [taxonomy_v2.json](../../backend/app/modules/profiles/taxonomy_v2.json) |
| Retrieval/exclusions | [social/retrieval.py](../../backend/app/modules/social/retrieval.py) |
| V1 rollback | [scoring_compat.py](../../backend/app/modules/matching/scoring_compat.py) |
| V2 score/diversity | [scoring_v2.py](../../backend/app/modules/matching/scoring_v2.py), [ranking.py](../../backend/app/modules/matching/ranking.py) |
| Reasons | [explain.py](../../backend/app/modules/matching/explain.py) |
| API và pair policy | [social/routes.py](../../backend/app/modules/social/routes.py), [service.py](../../backend/app/modules/social/service.py) |

`MATCHING_SCORER=v1` là mặc định trong Settings; `v2` bật rules-v2, `shadow` vẫn phục vụ v1 và chỉ ghi aggregate overlap với v2. Tên scoring version trên card có thể là `rules-v1.1` vì rollback scorer dùng vocabulary hiện hành; frozen `scoring.py` vẫn giữ oracle cũ cho compatibility/eval.

Đọc [thuật toán](algorithm.md), [lifecycle/privacy](lifecycle.md), [đánh giá](evaluation.md). Không diễn giải score như xác suất hợp nhau hoặc kết luận tâm lý.
