# WS-06 — Hồ sơ sự việc

Ưu tiên P1. Độ phức tạp L: bất biến ở tầng DB, tải về để băm, PDF tiếng Việt. Nhánh `mhiu05/feat-refactor-ws06-cases`.

## 1. Mục tiêu và giá trị

Em ghi lại nhiều lần xảy ra, giữ ảnh và video nguyên vẹn, và có một bản PDF để đưa cho người lớn khi em muốn.

## 2. Hiện trạng đã xác minh

Xem [01 §6](../01-codebase-audit.md#6-journal-so-với-incident-case-o6). Upload trực tiếp lên Storage: server không thấy byte. Giới hạn 65.536 byte cho body API và 3 MB ở Caddy nên không proxy ảnh qua API được nếu không đổi Caddyfile trên host. Docs Supabase xác nhận mặc định không ghi đè (`Asset Already Exists`). Không có thư viện PDF trong `uv.lock`.

## 3. Khoảng trống

Toàn bộ schema, API, hash, PDF, PIN.

## 4. Kiến trúc đề xuất

**Upload bằng chứng**: tái dùng luồng trực tiếp. Sau khi client upload xong, `complete` **tải object về bằng khóa server**, băm SHA-256 theo luồng (video tới 50 MiB, không đọc hết vào RAM), kiểm tra magic bytes và kích thước, rồi ghi `sha256` và `uploaded_at = clock_timestamp()`.

**Vì sao không proxy qua API**: cần đổi Caddyfile trên EC2, tăng tải cho một worker. **Vì sao không để client tự băm**: yêu cầu là server ghi.

**Sửa không phá hủy**: `incident_event_revisions` append-only, trigger chặn UPDATE. `case_evidence` có trigger chặn sửa trường đã niêm phong.

**PDF**: `reportlab` + `pillow`, font Noto Sans (giấy phép OFL) đóng gói trong `backend/app/modules/cases/fonts/`. Chạy trong `asyncio.to_thread`, semaphore 1, tối đa 20 ảnh. Đặt `Image.MAX_IMAGE_PIXELS = 40_000_000`. Xuất ra `BytesIO`, không ghi đĩa (container read-only). `/tmp` chỉ 64 MB.

**PIN**: `hashlib.scrypt` (stdlib). Mở khóa tạo token RAM theo session, 15 phút, gửi qua header `X-Case-Unlock`.

## 5. Phạm vi

Trong: case, sự việc, phiên bản, ảnh, video, tóm tắt nháp, PDF, PIN, bí danh, xóa case, hồ sơ mẫu. Ngoài: chia sẻ qua link, audio, đọc nội dung ảnh hoặc video.

## 6. File và symbol bị ảnh hưởng

`modules/journal/storage.py` (tách `SupabaseObjectStorage`, giữ `SupabaseJournalStorage` là subclass; thêm `download`); `modules/users/export.py`, `lifecycle.py`; `jobs/retention.py`; `main.py`; `backend/pyproject.toml`, `uv.lock`.

## 7. File mới

`backend/app/modules/cases/{__init__,models,schemas,service,routes,evidence,pin,summary,pdf}.py`; `modules/cases/fonts/`; `backend/alembic/versions/0034_case_workspace.py`.

## 8. API contract

```python
class EvidenceReserve(DTO):
    mime_type: Literal["image/jpeg", "image/png", "image/webp", "image/gif",
                       "video/mp4", "video/webm", "video/quicktime"]
    size_bytes: int = Field(gt=0, le=50 * 1024**2)   # ảnh ≤ 10 MiB
    source_kind: Literal["self_screenshot", "self_photo", "friend_provided", "other"]
    source_note: str | None = Field(default=None, max_length=200)
    event_id: UUID | None = None

class EvidenceView(DTO):
    id: UUID
    status: Literal["pending", "ready"]
    mime_type: str
    size_bytes: int
    sha256: str | None
    uploaded_at: datetime | None
    source_kind: str
    event_id: UUID | None
```

| Route | Mô tả | Lỗi |
| --- | --- | --- |
| `GET /api/v1/cases`, `POST /api/v1/cases` | Danh sách, tạo | `CASE_LOCKED` |
| `GET/PATCH/DELETE /api/v1/cases/{id}` | Xem, sửa tiêu đề, xóa | `STALE_VERSION` |
| `POST /api/v1/cases/{id}/events` | Thêm sự việc | |
| `GET /api/v1/cases/{id}/events/{eventId}` | Có danh sách revision | |
| `POST /api/v1/cases/{id}/events/{eventId}/revisions` | Sửa bằng bản mới | |
| `POST /api/v1/cases/{id}/evidence` | Trả upload capability | `MEDIA_LIMIT` |
| `POST /api/v1/cases/{id}/evidence/{eId}/complete` | Băm, niêm phong | `UPLOAD_INCOMPLETE`, `MEDIA_MISMATCH` |
| `GET /api/v1/cases/{id}/evidence/{eId}/access` | Signed URL 60 giây | |
| `POST /api/v1/cases/{id}/summaries` | Tạo nháp bằng agent | |
| `POST /api/v1/cases/{id}/summaries/{sId}/confirm` | Duyệt | |
| `POST /api/v1/cases/{id}/exports` | Trả PDF, `Content-Disposition: attachment` | `EXPORT_BUSY` |
| `PUT /api/v1/cases/pin`, `POST /api/v1/cases/pin/unlock`, `DELETE /api/v1/cases/pin` | PIN | `PIN_LOCKED`, `PIN_INVALID` |

Mọi route: owner check, CSRF, 404 khi không phải chủ, `Idempotency-Key` khi ghi. Khách dùng được mọi route.

## 9. Dữ liệu và migration

`0034_case_workspace`, xem [05 §6](../05-data-model-and-migrations.md#6-hồ-sơ-sự-việc).

## 10. Task

| ID | Ưu tiên | Phụ thuộc | Thay đổi, ở đâu | Hành vi mong đợi | Lệnh test | Pass / fail |
| --- | --- | --- | --- | --- | --- | --- |
| WS-06-T01 | P0 | WS-04-T01 | Migration 0034, ORM, hai trigger | `alembic check` sạch; UPDATE revision raise; đổi `sha256` đã niêm phong raise; `status` pending→ready được | `pytest -q tests/test_case_migration.py` | Pass: test bằng SQL trực tiếp |
| WS-06-T02 | P0 | T01 | `service.py`, routes case, sự việc | Thời điểm `unknown` hợp lệ; nhiều sự việc; bí danh mặc định | `pytest -q tests/test_cases_api.py` | Pass: người khác 404 |
| WS-06-T03 | P0 | T02 | Routes revision | Sửa tạo bản mới; bản đầu còn nguyên; `current_revision` tăng | `pytest -q tests/test_case_revisions.py` | Pass |
| WS-06-T04 | P0 | T01 | `SupabaseObjectStorage`, `download(path, max_bytes)` streaming | `SupabaseJournalStorage` không đổi hành vi, test journal pass; quá `max_bytes` dừng | `pytest -q tests/test_journal_storage*.py tests/test_object_storage.py` | Pass |
| WS-06-T05 | P0 | T04 | `evidence.py`: reserve, complete; path `cases/{user_id}/{case_id}/{id}.{ext}` | Hash đúng trên byte thật; magic bytes sai → xóa, 422; size sai → xóa, 422; complete hai lần idempotent; `uploaded_at` từ DB | `pytest -q tests/test_case_evidence.py` | Pass với Storage giả |
| WS-06-T06 | P0 | T05 | Video: magic bytes mp4, webm, mov; băm tới 50 MiB; dòng nhắc cố định trả về từ API để UI hiện | Nhận mọi file đúng định dạng và kích thước, không phân loại nội dung; ảnh, video không tới model | `pytest -q tests/test_case_evidence_video.py` | Pass: assert không có đường nào gửi file tới provider |
| WS-06-T07 | P0 | T05 | Access, abandon cleanup, thêm vào `journal_storage_deletions` khi xóa case | Đọc 60 giây; pending quá 24 giờ bị dọn | `pytest -q tests/test_case_storage_cleanup.py` | Pass |
| WS-06-T08 | P0 | T02 | `pin.py`, dependency `require_case_unlock` | 5 lần sai khóa 5 phút; restart phải nhập lại; quên PIN qua `/auth/reauthenticate` | `pytest -q tests/test_case_pin.py` | Pass |
| WS-06-T09 | P0 | WS-04-T07, T02 | `register_proposal` cho `case_create`, `event_add`, `event_revise`; tool `propose_case`, `propose_event`, `list_my_cases` | Confirm mới ghi; bí danh được áp | `pytest -q tests/test_case_proposals.py` | Pass |
| WS-06-T10 | P1 | T09 | `summary.py`: lượt agent không tool, input chỉ từ dữ liệu đã lưu của case | Nháp ở `draft`; duyệt mới vào PDF | `pytest -q tests/test_case_summary.py` | Pass |
| WS-06-T11 | P0 | T05 | `reportlab`, `pillow`, font; `pdf.py` | Ba phần nhãn rõ; tiếng Việt đúng dấu; ảnh được nhúng, video chỉ ghi tên, thời điểm, hash; dòng hash và câu giới hạn; ảnh tải lại và băm lại trước khi nhúng, sai thì đánh dấu; không ghi đĩa | `pytest -q tests/test_case_pdf.py` (đọc lại bằng `pypdf` từ group `kb`) | Pass: text trích ra chứa đủ nhãn tiếng Việt |
| WS-06-T12 | P1 | T01 | Export, purge, retention | Export có case; xóa tài khoản xóa hết và xếp hàng xóa object | `pytest -q tests/test_data_lifecycle.py tests/test_case_lifecycle.py` | Pass |
| WS-06-T13 | P1 | T09 | `POST /api/v1/school/samples/{id}/apply`: tạo hồ sơ mẫu trong tài khoản hiện tại từ `school/seed/samples.json` | Dữ liệu hư cấu, tự xóa theo khách; gọi lại không nhân đôi | `pytest -q tests/test_school_samples.py` | Pass |

## 11. An toàn và bảo mật

- Không tuyên bố hash chứng minh sự việc đã xảy ra: câu cố định trong UI và PDF.
- Không tự sao chép hội thoại.
- Người được nêu tên: bí danh mặc định; không có tính năng công khai.
- `Pillow` chỉ mở ảnh đã qua magic bytes, có giới hạn pixel, bắt lỗi giải nén.
- Ảnh không gửi tới model.
- Signed URL không vào log.

## 12. Test và dataset

Ảnh test tổng hợp. Hosted smoke với object thử nghiệm rồi xóa đúng object đó.

## 13. Acceptance criteria

- Hash khớp `sha256sum` trên file gốc.
- Không có đường nào sửa bằng chứng đã niêm phong.
- PDF đọc được, đúng dấu tiếng Việt.
- SC-08 chạy được.

## 14. Phụ thuộc và blocker

`JOURNAL_STORAGE_KEY` phải có trên staging (UNKNOWN, OD-12).

**TO_VERIFY**: endpoint tải object bằng khóa server (`GET /storage/v1/object/{bucket}/{path}`); token upload không cho upsert khi ký không có `x-upsert` (test trên hosted với object thử).

## 15. Rollback

Tắt route qua profile. Không xóa dữ liệu.

## 16. Definition of Done

G2 phần hồ sơ đạt.

## 17. Ghi chú cho Grok

`review_upgrade_artifact` từ chối từ khóa `DROP` và `TRUNCATE`. Trigger viết bằng `CREATE FUNCTION`, không dùng `%` trong `RAISE`. Reportlab cần `UnicodeCIDFont` không phù hợp tiếng Việt: dùng `TTFont`.
