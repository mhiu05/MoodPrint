# WS-05 — Knowledge base, pipeline thu thập và RAG

Ưu tiên P1. Độ phức tạp XL: pipeline, parser luật, 50 thẻ, phụ thuộc người duyệt. Nhánh `mhiu05/feat-refactor-ws05-kb`. Thiết kế ở [07](../07-knowledge-base-design.md).

## 1. Mục tiêu và giá trị

Câu trả lời về luật, quy trình, cách báo cáo chỉ đến từ nội dung đã duyệt. Không chắc thì nói chưa biết và chỉ tới người thật.

## 2. Hiện trạng đã xác minh

`VoyageProvider`, `validate_vector`, `Vector`, mẫu `journal_entry_embeddings`, `Citation`, `source_backed`. Không có `pyyaml`, `trafilatura`, `pypdf` trong `uv.lock`. Hosted có `vector`, chưa bật `pg_trgm`, `unaccent`.

## 3. Khoảng trống

Toàn bộ pipeline, thẻ, bảng, retrieval, verifier.

## 4. Kiến trúc đề xuất

Theo [07](../07-knowledge-base-design.md). Offline trong `scripts/kb/`; runtime trong `backend/app/knowledge/`, đọc `content/cards.json`.

## 5. Phạm vi

Trong: pipeline, 40–60 thẻ, retrieval, verifier, tool, eval, bản public cho Tìm hỗ trợ. Ngoài: reranker, web search, tự động duyệt.

**Phân bổ thẻ MVP**

| `action` | Số thẻ | Ví dụ |
| --- | --- | --- |
| `understand` | 8 | Bị anti là gì, cô lập, bạo lực trên mạng, tống tiền |
| `safety` | 8 | Đi học an toàn, khi bị đe dọa |
| `evidence` | 5 | Chụp màn hình, lưu trước khi chặn, hash nói gì |
| `report` | 9 | Facebook, YouTube, TikTok × báo cáo, chặn, lưu bằng chứng |
| `rights` | 8 | Trường phải làm gì, tư vấn học đường, kỷ luật |
| `support` | 9 | 111 hoạt động thế nào, nói với người lớn, người chứng kiến |

## 6. File và symbol bị ảnh hưởng

`backend/pyproject.toml`, `uv.lock` (group `kb`); `.github/workflows/verify.yml` (thêm bước); `backend/app/main.py` (worker sync trong lifespan); `ai/assistant/tools.py`.

## 7. File mới

`scripts/kb/{fetch,normalize,diff,validate,build,evaluate}.py`; `scripts/kb/legal_parser.py`; `kb/sources/registry.yaml`, `manifest.jsonl`, `normalized/`; `kb/cards/**`; `kb/eval/queries.jsonl`; `backend/app/knowledge/{__init__,models,sync,retrieval,verifier,tool}.py`; `backend/app/knowledge/content/cards.json`; `backend/alembic/versions/0033_knowledge_base.py`; `frontend/src/features/school/support/public-cards.generated.json`.

## 8. API contract

```python
class SearchKnowledgeInput(BaseModel):
    query: str = Field(min_length=2, max_length=160)
    action: Literal["understand", "safety", "evidence", "report", "rights", "support"] | None = None

class RetrievedCard(BaseModel):
    card_id: str
    title: str
    body: str
    limitations: str
    claims: list[str]

class ClaimVerdict(BaseModel):
    supported: bool
    unsupported_indexes: list[int] = Field(default_factory=list, max_length=8)
```

| Route | Mô tả |
| --- | --- |
| `GET /api/v1/knowledge/cards/{cardId}` | Mở thẻ nguồn từ citation; lọc `approved`, còn hạn, nhóm tuổi |

## 9. Dữ liệu và migration

`0033_knowledge_base`, xem [05 §5](../05-data-model-and-migrations.md#5-knowledge-base).

## 10. Task

| ID | Ưu tiên | Phụ thuộc | Thay đổi, ở đâu | Hành vi mong đợi | Lệnh test | Pass / fail |
| --- | --- | --- | --- | --- | --- | --- |
| WS-05-T01 | P1 | WS-04-T01 | Group `kb`, `registry.yaml` từ [kb-source-links](../kb-source-links.md); tra lại hiệu lực, đổi TO_VERIFY thành kết quả | Registry hợp lệ; mỗi nguồn có `jurisdiction`; nguồn hết hiệu lực hoặc link chết bị bỏ | `uv run --group kb python ../scripts/kb/validate.py --registry-only` | Pass |
| WS-05-T02 | P1 | T01 | `fetch.py`: allowlist, robots, rate limit, 3 lần thử, snapshot vào `.tmp/kb/raw`, `manifest.jsonl`, User-Agent không chứa email | Domain ngoài registry bị từ chối; robots chặn thì dừng; không theo redirect ra ngoài allowlist | `pytest -q tests/test_kb_fetch.py` với transport giả | Pass |
| WS-05-T03 | P1 | T02 | `normalize.py`, `legal_parser.py` | Giữ Điều, khoản, điểm; locator ổn định; bảng và chú thích không vỡ | `pytest -q tests/test_kb_legal_parser.py` với mẫu tổng hợp | Pass |
| WS-05-T04 | P1 | T03 | `diff.py` | sha đổi → thẻ phụ thuộc `needs_review` | `pytest -q tests/test_kb_diff.py` | Pass |
| WS-05-T05 | P0 | T03 | `validate.py`, bước CI | Tất cả điều kiện ở [07 §7](../07-knowledge-base-design.md#7-cli-kiểm-tra); `approved` không có `reviewed_by` fail | `pytest -q tests/test_kb_validate.py` | Pass: mỗi điều kiện có test âm |
| WS-05-T06 | P0 | T05 | `build.py` sinh `cards.json` và bản public | Chỉ thẻ approved, còn hạn; output ổn định theo byte; CI kiểm tra drift | `pytest -q tests/test_kb_build.py` | Pass |
| WS-05-T07 | P0 | WS-04-T01 | Migration 0033, ORM | `alembic check` sạch; GIN index có; `search_vector` sinh tự động | `pytest -q tests/test_kb_migration.py` | Pass |
| WS-05-T08 | P0 | T06, T07 | `sync.py` trong worker nền, embed theo lô nhỏ, không chặn readiness | Idempotent; chỉ embed khi sha đổi; thẻ bỏ thành `retired`; Voyage lỗi vẫn có keyword | `pytest -q tests/test_kb_sync.py` | Pass |
| WS-05-T09 | P0 | T08 | `retrieval.py` theo SQL ở [07 §8](../07-knowledge-base-design.md#8-index-và-truy-xuất) | Lọc trước khi xếp hạng; RRF k=60; thẻ hết hạn không xuất hiện; embed lỗi vẫn trả | `pytest -q tests/test_kb_retrieval.py` | Pass |
| WS-05-T10 | P0 | T09 | Tool `search_knowledge`, `get_platform_guide` thay stub; ghi `run.retrieved_cards` | `query` qua kiểm tra độ dài; `Citation` dựng từ thẻ, `start`/`end` tìm bằng vị trí `ClaimRef.sentence` trong bubble, không thấy thì coi là thiếu ref; `source_backed=true` | `pytest -q tests/test_assistant_kb.py` | Pass |
| WS-05-T11 | P0 | T10 | `verifier.py`, tích hợp `turn.py` | Thẻ không ủng hộ → câu dự phòng; ref tới thẻ chưa truy xuất → câu dự phòng; timeout → câu dự phòng; vẫn gắn nhãn | `pytest -q tests/test_kb_verifier.py` | Pass |
| WS-05-T12 | P1 | T05 | Soạn nháp 50 thẻ `draft`, chia PR theo `action`, kèm trích dẫn | Tất cả qua `validate.py` ở mức draft | `validate.py` | Pass: chờ người duyệt, không tự approve |
| WS-05-T13 | P1 | T12 | `evidence/content-review.md`: bảng duyệt mỗi thẻ một dòng, kèm nguồn. mhiu05 đánh dấu; Grok điền `reviewed_by: mhiu05` cho mục đã đánh dấu. Bước bấm trong thẻ `report` soạn từ [kb-source-links](../kb-source-links.md); mhiu05 kiểm tra trên app thật trước khi đánh dấu | ≥ 40 thẻ approved | `validate.py`; `build.py` | **Chặn G5**, không chặn phát triển |
| WS-05-T14 | P0 | T09 | `kb/eval/queries.jsonl` ≥ 100, `evaluate.py`, cờ `--include-draft` chỉ cho eval | Báo Recall@4, MRR | `python ../scripts/kb/evaluate.py --embedder fake` | Pass runner |
| WS-05-T15 | P0 | T12, T14 | Chạy với Voyage thật trên thẻ nháp, tối ưu theo thứ tự; chạy lại sau khi duyệt | Recall@4 ≥ 0,9 | `evaluate.py --live --include-draft --confirm-live --max-usd 0.05` | Pass: đạt. Fail: ghi lại từng biến đã đổi |
| WS-05-T16 | P1 | T06 | Thêm `image`, `image_alt` vào schema thẻ; `build.py` đọc [assets/kb-screenshots](../assets/kb-screenshots/README.md), bỏ qua ảnh trùng hash trong `placeholders.json`, chép ảnh thật sang `frontend/public/kb-guides/` | Thẻ có ảnh mẫu vẫn build, chỉ mất ảnh; ảnh mẫu không có trong output; có ảnh thì bắt buộc `image_alt` | `pytest -q tests/test_kb_build.py` | Pass |

## 11. An toàn và bảo mật

- Thẻ là dữ liệu, không phải chỉ dẫn; văn bản trong thẻ không thể đổi prompt.
- Query gửi Voyage là cụm trung tính do model viết, không phải nguyên văn lời em.
- Khách dùng KB như tài khoản đăng nhập. `kind_available` đóng `embed` của khách dưới cấu hình có trần; embedding truy vấn KB không đi qua cổng này, vì nằm trong phần miễn phí của Voyage và đã có nhánh lexical khi lỗi.
- Fetch không chạy trong image, không có đường SSRF ở runtime.
- Nguồn `foreign` không dùng cho `rights`.
- Không phát hành lại snapshot.

## 12. Test và dataset

Xem [10](../10-evaluation-and-quality-gates.md). Không dùng báo chí trong KB.

## 13. Acceptance criteria

- ≥ 40 thẻ approved trước G5; KB-A/B/C, SC-05 có đủ thẻ.
- Recall@4 ≥ 0,9.
- Không câu pháp lý nào hiện ra mà không có thẻ hợp lệ.

## 14. Phụ thuộc và blocker

OD-02 chặn G5 qua T13. OD-07. Tra lại hiệu lực văn bản cần truy cập cổng chính thức.

## 15. Rollback

Xóa nội dung `cards.json`: tool trả rỗng, agent nói chưa biết. Bảng giữ nguyên.

## 16. Definition of Done

G2 phần KB đạt.

## 17. Ghi chú cho Grok

Bắt đầu từ [kb-source-links](../kb-source-links.md). Không điền `reviewed_by` cho mục mhiu05 chưa đánh dấu, kể cả để test staging. Ảnh thật do mhiu05 đưa vào, đã che thông tin cá nhân vì repo công khai. Thẻ nháp chạy được trong eval local với `--include-draft`, nhưng `build.py` không có cờ này. Dùng thẻ fixture riêng cho test, đặt trong `backend/tests/fixtures/`, không trộn vào `kb/cards/`.
