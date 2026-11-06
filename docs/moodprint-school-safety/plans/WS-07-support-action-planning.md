# WS-07 — Hỗ trợ và hành động

Ưu tiên P1. Độ phức tạp M: dùng lại khung tool, nội dung nhiều hơn kỹ thuật. Nhánh `mhiu05/feat-refactor-ws07-support`.

## 1. Mục tiêu và giá trị

Em có một kế hoạch cụ thể và biết nói với ai, nói thế nào. Đây là bước đưa em tới người lớn thật, thước đo chính của sản phẩm.

## 2. Hiện trạng đã xác minh

Không có gì. Khung tool và proposal do WS-04 cung cấp.

## 3. Khoảng trống

Bảng người lớn tin cậy, kế hoạch, soạn tin, thẻ 111.

## 4. Kiến trúc đề xuất

Kế hoạch dựng từ **template xác định** (`modules/support/plans/*.json`), model chỉ gợi ý điền ô. Soạn tin là bản nháp, không có API gửi.

Thẻ 111 là cấu trúc cố định: em là ai (bí danh), chuyện gì, ở đâu, đã bao lâu, có nguy hiểm ngay không, em muốn gì.

## 5. Phạm vi

Trong: WF-03, WF-04, hỗ trợ người chứng kiến phần soạn tin. Ngoài: gửi tin, gọi điện tự động.

## 6. File và symbol bị ảnh hưởng

`ai/assistant/tools.py`, `main.py`, `modules/users/export.py`, `core/profile.py` (không cần thêm, route mới không bị chặn).

## 7. File mới

`backend/app/modules/support/{__init__,models,schemas,service,routes,plans}.py`; `modules/support/plans/{offline_safety,online_safety}.json`; `backend/alembic/versions/0035_support_practice.py` (cùng WS-08; WS-07 tạo trước, WS-08 thêm bảng vào migration riêng nếu thứ tự đổi; xem Ghi chú).

## 8. API contract

| Route | Mô tả |
| --- | --- |
| `GET/POST /api/v1/support/trusted-adults` | Danh sách, thêm |
| `PATCH/DELETE /api/v1/support/trusted-adults/{id}` | Sửa, xóa |
| `GET/POST /api/v1/support/plans` | Kế hoạch |
| `PATCH /api/v1/support/plans/{id}` | Sửa, `expectedVersion` |
| `GET/PATCH/DELETE /api/v1/support/drafts/{id}` | Bản nháp |

```python
class SafetyPlanStep(BaseModel):
    key: Literal["route", "companion", "safe_places", "contacts", "evidence_first", "report", "block"]
    text: str = Field(max_length=300)

class Card111(BaseModel):
    who: str = Field(max_length=120)
    what: str = Field(max_length=300)
    where: str = Field(max_length=120)
    since_when: str = Field(max_length=80)
    danger_now: bool
    ask: str = Field(max_length=200)
```

## 9. Dữ liệu và migration

`trusted_adults`, `support_drafts`, xem [05 §7](../05-data-model-and-migrations.md#7-hỗ-trợ-và-luyện-nói). `case_action_plans` có ở 0034.

## 10. Task

| ID | Ưu tiên | Phụ thuộc | Thay đổi, ở đâu | Hành vi mong đợi | Lệnh test | Pass / fail |
| --- | --- | --- | --- | --- | --- | --- |
| WS-07-T01 | P1 | WS-06-T01 | Migration 0035 phần support, ORM | `alembic check` sạch | `pytest -q tests/test_support_migration.py` | Pass |
| WS-07-T02 | P1 | T01 | CRUD người lớn tin cậy | Tối đa 10; `is_safe=false` không xuất hiện trong gợi ý | `pytest -q tests/test_support_adults.py` | Pass |
| WS-07-T03 | P1 | T01 | Template kế hoạch, `build_safety_plan` | Có bước "lưu bằng chứng trước khi chặn" trong kế hoạch trên mạng; template không có số ngoài allowlist; không có lời khuyên trả đũa | `pytest -q tests/test_support_plans.py` | Pass |
| WS-07-T04 | P1 | T03, WS-05-T10 | `get_platform_guide`, WF-03 hoàn chỉnh | Lấy từ thẻ `report`; thẻ thiếu thì nói chưa biết | `pytest -q tests/test_assistant_wf03.py` | Pass |
| WS-07-T05 | P1 | T02 | `list_trusted_adults`, `propose_trusted_adult`, nhánh `adult_unsafe`, `adult_perpetrator` | Người gây hại không được gợi ý; gợi ý người khác hoặc 111 | `pytest -q tests/test_assistant_wf04.py` | Pass |
| WS-07-T06 | P1 | T05 | `draft_message` | Bản nháp qua postcheck; không có route gửi | `pytest -q tests/test_support_drafts.py` | Pass: `rg` không có client gửi tin |
| WS-07-T07 | P1 | T05 | `build_111_card` từ dữ liệu đã lưu của case | Không tự thêm chi tiết; em sửa được | `pytest -q tests/test_support_card111.py` | Pass |
| WS-07-T08 | P2 | T06 | WF-05 thêm soạn tin không lộ mình | Không hứa ẩn danh tuyệt đối | `pytest -q tests/test_assistant_wf05.py` | Pass |
| WS-07-T09 | P1 | T01 | Export, purge, access matrix | Như WS-06 | `pytest -q tests/test_school_access_matrix.py` | Pass |

## 11. An toàn và bảo mật

Không xúi trả đũa, không hứa điều chưa xác minh, không ép đối mặt, không tự liên hệ bên thứ ba. Kế hoạch sửa được, thuộc về em. Người lớn không an toàn dẫn tới 111.

## 12. Test và dataset

Bổ sung eval WF-03, WF-04 trong `evals/assistant`.

## 13. Acceptance criteria

Bước KB-A 8, 11, KB-B 6, 8 và SC-04 chạy được.

## 14. Phụ thuộc và blocker

WS-05-T10, WS-06-T09.

## 15. Rollback

Route riêng, bảng riêng.

## 16. Definition of Done

G2 đạt cùng WS-05, WS-06.

## 17. Ghi chú cho Grok

Nếu WS-08 xong trước, đổi tên migration theo thứ tự thực tế nhưng giữ một artifact hosted duy nhất. Revision không được trùng. Cập nhật [05](../05-data-model-and-migrations.md) nếu đổi.
