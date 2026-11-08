# Phase 0 + Phase 1 — Báo cáo tổng kết

Ngày chốt vòng 1: 2026-11-08. Workspace `mhiu05-feat-refactor`. Nhánh `feat/phase-1-backend`. HEAD khi viết báo cáo: `82d9463cc023d0b71826925f5b5bed4e1a118b05`.

## 1. Kết luận

**G1 VERIFIED, G2 PARTIALLY_VERIFIED.**

G0 đã merge. G1 có CI trên `d779a243`, hosted API smoke exit 0 trong vòng 2, và hosted UI trong cửa sổ Chrome tách biệt. G2 chưa gắn tag vì Docker không lên nên hai script cổng chưa chạy trên commit merge. Chi tiết: `g1-g2-closure-report.md`.

Sản phẩm **chưa** sẵn sàng cho học sinh thật. Các điều kiện pháp lý, đồng ý, vận hành và an toàn ở `00` §6 vẫn nằm ngoài Phase 0/1.

## 2. Phạm vi đã hoàn thành

| Nhóm | Task | Trạng thái |
|---|---|---|
| Phase 0 | F0-01 … F0-11 | VERIFIED, merge PR #46 tại `d5c36ac0` |
| Phase 1 backend | F1-02, F1-03.1, F1-04.1, F1-05, F1-06.1, F1-06.2, F1-07.5, F1-07.6 | VERIFIED bởi integration, pgTAP và OpenAPI |
| Phase 1 frontend | F1-01, F1-03.2, F1-04.2, F1-07.1–07.4 | VERIFIED trên local E2E và Vitest |
| Phase 1 cổng local | F1-08.1, F1-08.2 | VERIFIED trên `ddf970dc` |
| Phase 1 hosted API | F1-08.3 phần schema, history, smoke API, cleanup | VERIFIED |
| Phase 1 hosted UI | F1-08.3 phần Chrome | VERIFIED ở vòng 2, cửa sổ Chrome tách biệt |
| G2 | `06` §8 | PARTIALLY_VERIFIED. Chưa tag |

Không triển khai RAG, Companion tools Phase 2/3, hay worktree song song.

## 3. Bảng tiêu chí

| Tiêu chí | Bằng chứng | Trạng thái | Mốc |
|---|---|---|---|
| G0 local + hosted | `phase-0-report.md`, PR #46 | VERIFIED | `d5c36ac0` |
| Auth ES256, RLS, role `moodprint_api` | integration `test_rls_context`, `test_me` | VERIFIED | Phase 0, regression trong cổng |
| Cases, timeline, version 409 | `test_cases`, E-CASE-01, E-CASE-03 | VERIFIED | local |
| Evidence TUS resume 20 MB | vertical slice, offset 6 MiB | VERIFIED | local E2E |
| Plans, Home checkbox | E-PLAN-02, Vitest plan | VERIFIED | local |
| Contacts, support drafts | E-SUP-01, integration | VERIFIED | local |
| Sharing staff không đọc `cases` | pgTAP `04_school_scope`, integration | VERIFIED | local |
| Demo không trộn real | E-DEMO-02, journey 13/13 | VERIFIED | local |
| `/support/urgent` khi API tắt | E-URG-01 | VERIFIED | local |
| User B 404 | vertical slice và hosted smoke | VERIFIED | local và hosted API |
| Hosted 6 migration `f1_*` | dry-run rồi apply, dry-run sau đó rỗng | VERIFIED | hosted |
| Hosted API case/evidence 1 MiB/plan | `smoke_hosted.py --phase 1` exit 0 | VERIFIED | `82d9463c` có script; lần chạy trước commit báo cáo |
| Security Advisor 0, 2 WARN SELECT | Nguồn policy trong `f1_sharing.sql`; MCP không gọi lại được trong vòng này | Chấp nhận WARN, không phải lỗi bảo mật | vòng 1 |
| Hosted UI đăng ký/hồ sơ/reload | Cửa sổ Chrome mới trong process đang chạy | VERIFIED vòng 2 | `g1-g2-closure-report.md` |
| Receipt đúng SHA của HEAD | Receipt local vẫn `ddf970dc`; CI đã chạy lại trên `d779a243` | CI khớp HEAD; wrapper local chưa chạy lại | Docker không lên |
| CI PR #47 | offline + integration SUCCESS trên `d779a243` | VERIFIED | runs `42440492063` và `42440494924` |
| Pre-commit cài trên máy | `core.hooksPath` trống; không sửa config dùng chung | Chưa cài | vòng 1 |
| Tag baseline | Không tạo | Chưa đạt G2 | — |

## 4. Kiến trúc và chức năng thực

Một process FastAPI import `moodprint_agent`. Dữ liệu nghiệp vụ ở schema `app`, không expose PostgREST. Backend đăng nhập bằng `moodprint_api` và `SET LOCAL ROLE authenticated` cùng claims đã verify. Frontend dùng supabase-js chỉ cho Auth. File đi qua signed upload vào bucket private `incident-evidence`.

Workspace `real` gọi port HTTP. Workspace `demo` giữ mock và `moodprint-demo`. Lỗi API hiện lỗi, không thay bằng dữ liệu mẫu. Chat, phân tích, roleplay và voice trong workspace thật vẫn có nhãn mô phỏng. Model OpenAI giữ `gpt-6-luna`. `store=False`, tracing tắt.

Companion Phase 0 có session SDK, memory có duyệt, Context Builder và SSE. Phase 1 không thêm tool ghi hồ sơ cho agent.

## 5. Tests đã chạy

Không cộng dồn các lần thất bại vào số pass.

| Lệnh | SHA liên quan | Thời điểm | Kết quả |
|---|---|---|---|
| `uv run python scripts/verify_phase1.py` | `ddf970dc` | 2026-11-07 20:51 UTC | exit 0. Receipt `.local/phase1-gate.json` |
| Bên trong cổng: `verify_phase0.py --regression` | cùng SHA | cùng lần | check.py 264 pass / 67 deselect; pgTAP 13 file, 194 assertion; integration 67 pass |
| Vitest, build, boundaries, demo E2E, real E2E | cùng SHA | cùng lần | cả chín checkpoint return code 0 |
| CI offline + integration | `82d9463c` | 2026-11-07 21:18–21:24 UTC | SUCCESS, run `42415259412` |
| `smoke_hosted.py --phase 1` | script có từ `82d9463c`; chạy trước commit báo cáo | 2026-11-07 | exit 0, cleanup 0 user/object/profile/case |

Lần cổng trước đó, cùng ngày, exit 1 vì Vitest nhận biến Auth của E2E. Đã sửa bằng cách xóa `VITE_PUBLIC_*` khỏi unit check và tăng `testTimeout` lên 15 giây. Không chạy lại cổng full sau khi chỉ đổi báo cáo và smoke script.

Các sửa assertion-giữ-nguyên trước cổng xanh: timeout welcome 180 giây, deep link chờ heading sau reload rồi mới xóa tài khoản, timeout responsive real 360 giây. Fixture 404 chỉ khớp plan chưa tồn tại với message `Hồ sơ chưa có kế hoạch.`

## 6. Vertical slice

**Local.** Một bài Playwright: đăng ký, xác nhận email local, wizard 6 bước, lưu nháp, reload, upload 20 MB, pause/resume, HEAD offset `6291456`, timeline sửa, plan, checkbox Home còn sau reload, context thứ hai thấy cùng dữ liệu, User B không thấy tiêu đề và API 404, rồi demo `Chào An` không chứa hồ sơ đó.

**Hosted.** Chỉ API, không phải UI. User tổng hợp, hồ sơ, upload 1 MiB, download khớp byte, plan và tick, user kia 404, xóa evidence và hồ sơ, xóa Auth. Sau đó đếm 0 user, 0 object, 0 profile, 0 case. Migration cuối `20261107140312`. 17 migration, 0 bảng `app` thiếu RLS.

## 7. Database và hosted

Project `db-school-violence`, ref `xhlshihobyxrgfqrdafh`, URL `https://xhlshihobyxrgfqrdafh.supabase.co`. Không dùng database MoodPrint cũ.

`DATABASE_URL` runtime là role `moodprint_api`. Frontend dev `127.0.0.1:5173` trỏ Supabase hosted và API `127.0.0.1:8000`.

Advisor chính thức không được gọi lại trong vòng này vì MCP `school-violence-supabase` không nằm trong phiên. Policy trong migration:

- `case_shares`: `owner_read` và `staff_read` đều là SELECT. Staff chỉ khi status đã gửi và `is_school_member`.
- `case_share_evidence`: `owner_all` cộng `staff_read` SELECT.

PostgreSQL OR các policy permissive. Tách policy để staff không có INSERT/UPDATE. Gộp chúng không đổi quyền nhưng phải thêm migration và apply hosted. Không làm trong vòng này. Không xóa index chưa dùng. WARN performance được ghi nhận, không phải security error.

## 8. G0, G1, G2

| Gate | Kết quả | Bằng chứng |
|---|---|---|
| G0 | VERIFIED | PR #46 merged `d5c36ac0`, `phase-0-report.md` |
| G1 | VERIFIED | CI offline + integration SUCCESS trên `d779a243`; UI hosted vòng 2; `smoke_hosted.py --phase 1` exit 0 vòng 2 |
| G2 | PARTIALLY_VERIFIED | Chưa merge/tag tại mục này. Docker không lên nên chưa có receipt wrapper mới. Ma trận đủ trong `g1-g2-closure-report.md` |

## 9. Git

- PR: https://github.com/mhiu05/MoodPrint/pull/47
- Base: `mhiu05/feat-refactor`
- Head: `feat/phase-1-backend`
- Trạng thái: OPEN, MERGEABLE, chưa merge
- CI: https://github.com/mhiu05/MoodPrint/actions/runs/42415259412
- Tag: không tạo
- Owner config không commit: `.claude/settings.local.json`, `.cursor/mcp.json`, `.mcp.json`

## 10. Nhật ký vòng

Giới hạn 3 vòng. Đã dùng **1**.

| Vòng | Việc còn | Sửa | Kiểm tra | Kết quả | Quyết định |
|---|---|---|---|---|---|
| 1 | UI hosted, advisor, hook, SHA receipt | Không sửa product. Không gộp RLS. Không đặt `core.hooksPath` dùng chung | Audit git/PR/CI; `orca computer` trên Chrome đang mở; đọc policy sharing; chạy hook tay | UI không vào được `/auth`; CI đã xanh; hook tay exit 0 | Dừng. Lặp lại cùng thao tác Chrome không có đường thành công mới |

## 11. Sai khác so với kế hoạch

- Receipt cổng không gắn vào HEAD vì commit sau cổng chỉ là báo cáo và smoke script.
- Hosted UI dùng Chrome có sẵn thay vì mở Chrome mới, và không điều hướng được omnibox.
- Hook pre-commit nằm trong repo và CI, chưa gắn `core.hooksPath` vì repo là worktree dùng chung `E:/MoodPrint/.git` và `worktreeConfig` đang tắt.
- A-06 không chạy. S-01 không đo quá hai giờ đồng hồ thật.

## 12. Giới hạn

Không chặn gate đã công bố. Vòng 1 từng chặn UI. Vòng 2 đã quan sát UI trong cửa sổ Chrome tách biệt. Docker engine không lên nên chưa có receipt `verify_phase1.py` mới; CI của đúng SHA vẫn là bằng chứng suite tự động.

- Signed upload đã cấp dùng được tới TTL sau khi xóa Auth. Chưa có tombstone. Không nói là đã thu hồi tức thì.
- S-01 mới có bài expiry/renewal có giới hạn thời gian, chưa đo wall-clock hơn hai giờ.
- A-06 chưa chạy vì không có trần chi phí. Không đổi `gpt-6-luna`.
- Hai WARN multiple permissive SELECT. Chấp nhận vì đúng tách owner/staff.
- `00` §6 cho học sinh thật vẫn mở.

## 13. Học sinh thật

Phase 0 và Phase 1 chỉ dùng dữ liệu tổng hợp và tài khoản test. Báo cáo này không phải quyết định cho người dùng thật vào sản phẩm.
