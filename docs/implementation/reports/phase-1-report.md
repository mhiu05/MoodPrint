# Phase 1 — Implementation report

Trạng thái ngày 2026-11-08: **local G1 VERIFIED** trên `ddf970dc62f8baae5c1ab97e36ea14e069984a0b`. Hosted schema và API smoke đã chạy. **G1 chưa đóng hết** vì Security/Performance Advisor và hosted UI smoke chưa có bằng chứng trong phiên này. **G2 chưa đạt.** Không có tag `baseline/phase-1-verified`. Không tạo worktree Phase 2/3. Sản phẩm **chưa** sẵn sàng cho học sinh thật; các điều kiện `00` §6 vẫn mở.

## Acceptance đã chạy trên cây này

Lệnh cổng, exit 0, khoảng 26 phút, receipt `.local/phase1-gate.json` (`scope=local_phase1`, `passed=true`, commit trùng HEAD lúc chạy):

`uv run python scripts/verify_phase1.py`

Cổng đó gọi `verify_phase0.py --regression` rồi typecheck, lint, format, Vitest `--maxWorkers=2`, build, `check:boundaries`, E2E demo và E2E real. Chín bước đều return code 0. Receipt không được commit.

Bên trong regression:

| Kiểm tra | Kết quả |
|---|---|
| `scripts/check.py` | Ruff, Pyright 0, import boundary 3 kept, **264 passed**, 67 integration deselected |
| Contract schema và OpenAPI `--check` | Pass, không diff |
| `supabase db reset` rồi bootstrap | Pass. Bootstrap có thể đổi password local; cổng đọc lại `.local/test.env` |
| pgTAP | **13 files, 194 assertions, PASS** |
| `pytest -m integration` | **67 passed**, 264 deselected |
| Vitest trong cổng | Pass sau khi unit test không còn nhận biến `VITE_PUBLIC_*` của E2E và `testTimeout` là 15 giây |

Trước cổng gộp, các suite riêng cũng xanh trên cùng working tree: Vitest **94 passed / 23 files**; demo Playwright **13 passed**; real Playwright **11 passed** cộng `E-URG-01` **1 passed** khi process API đã dừng. Vertical slice “confirmed account” đi hết wizard, upload 20 MB, resume offset 6 MiB, plan, User B nhận 404, rồi quay lại demo “Chào An”. Local còn **0** user, object, profile, case sau các suite.

Các lỗi thật đã sửa, không nới assertion:

- Welcome 8 bề rộng vượt timeout 30 giây của Playwright; budget nâng lên 180 giây, assertion hình học giữ nguyên. Suite demo sau đó 13/13.
- Deep link E-AUTH-03: `DELETE /v1/me` đặt `deletion_started_at` trong lúc trang reload còn GET hồ sơ, nên console 409 và UI “Tài khoản đang được xóa”. Test chờ heading sau reload rồi mới xóa tài khoản.
- Vitest trong cổng nhận cấu hình Auth local nên hai test trang đầy đủ vượt 5 giây. Unit check xóa ba biến `VITE_PUBLIC_*`; E2E vẫn tự gắn lại.
- Responsive real 14 route × 8 bề rộng vượt 180 giây khi máy vừa chạy cả cổng. Budget 360 giây. Lần cổng cuối test này nằm trong real suite xanh.

Fixture console chỉ bỏ qua 404 khi response đúng `GET /v1/cases/{id}/plan`, JSON `not_found` và message đúng `Hồ sơ chưa có kế hoạch.`. 409 version conflict của E-CASE-03 vẫn là assertion có chủ đích.

## Hosted `db-school-violence`

Project ref `xhlshihobyxrgfqrdafh`. Dry-run liệt kê đúng sáu file `f1_*`, không file lạ. `push_hosted.py --apply` exit 0 trên commit đã có receipt. Dry-run ngay sau đó không còn pending. Lịch sử kết thúc ở `20261107140312`. Mọi bảng `app` có RLS (`tables_without_rls=0`).

`uv run python scripts/smoke_hosted.py --phase 1` exit 0: readiness, profile, memory, cô lập user B, upload/download ký, hồ sơ, evidence 1 MiB, plan và tick, user B 404, xóa evidence và hồ sơ, xóa hai user Auth. Sau smoke: **0** user, **0** object, **0** profile, **0** case.

MCP `school-violence-supabase` không có trong phiên này nên **chưa chạy** `get_advisors`. Không lấy advisor bằng DDL hay API key in ra log.

Hosted UI smoke F1-08.3: **BLOCKED**. Phiên không có công cụ điều khiển Chrome đang mở, và yêu cầu là không tự mở Chrome mới. Không có bằng chứng đăng ký giao diện trên hosted.

## G2 và chiến lược IT-01..IT-09

Chưa đặt tag. `core.hooksPath` đang trống; file `.githooks/pre-commit` có trong repo nhưng không cài, vì không sửa git config của owner. CI đã có check ownership trên `feat/knowledge-ingestion-rag` và `feat/agent-companion`, cùng job E2E, nhưng chưa có run xanh trên commit này.

Scaffold `06` §3.3 đã có: `create_retriever` fixture, router Knowledge rỗng, `agent/ingestion`, test/eval knowledge, composition chat/analysis/roleplay/knowledge, package `tools`/`roleplay`/`evidence`. Checker đọc `docs/implementation/ownership.yaml`.

Khi có nhánh `integration/phase-2-3`, integrator chạy đúng các test sau, chưa thực hiện trong nhiệm vụ này:

| Test | Việc sẽ kiểm |
|---|---|
| IT-01 | Migration `kb_*` và `ag_*` trên DB trống, cả hai thứ tự |
| IT-02 | `KnowledgeRetrieverContract` với adapter thật |
| IT-03 | `knowledge_search` trả citation có `source_id` trong `knowledge.sources` |
| IT-04 | Không có kết quả thì Companion không bịa URL |
| IT-05 | Timeout retriever không treo và không trả citation một phần |
| IT-06 | Toàn bộ test hai nhánh, frontend demo và real |
| IT-07 | pgTAP RLS cho `knowledge.*` và bảng `ag_*` |
| IT-08 | `check_ownership.py` từng nhánh so với baseline |
| IT-09 | Eval knowledge và companion bằng `gpt-6-luna`, rubric do coding agent chấm theo AD-20. Không chạy khi chưa có trần chi phí |

## Giới hạn còn lại

Signed TUS capability đã cấp vẫn dùng được tới TTL sau khi xóa Auth. Chưa có tombstone sweep. Không tuyên bố thu hồi tức thì.

S-01 chưa đo wall-clock hơn hai giờ. A-06 live model không chạy vì chưa có trần chi phí; model vẫn `gpt-6-luna`. Local advisor từng còn 2 WARN multiple permissive SELECT trên share owner/staff; phiên này không đọc lại advisor hosted.

Các checkpoint bên dưới là lịch sử trước acceptance này, không thay cho bảng ở trên.


Baseline G0: `d5c36ac0a1eae81fbe61fe1c6efd2a3a4203606e`, merge [PR #46](https://github.com/mhiu05/MoodPrint/pull/46) vào `mhiu05/feat-refactor` ngày 2026-11-07. Final Phase 0 feature SHA `4a9ad38d`; cả hai final CI runs đã xanh sau retry bước start Supabase. Branch hiện tại: `feat/phase-1-backend`.

## Ownership và execution ledger

- Root: toàn bộ f1 SQL migrations/SQL tests; incidents/plans; router registration/exports; UI incidents/plans/home/support/knowledge/AI; integration/E2E/gates/reports.
- frontend_foundation: frontend services/types/store/Auth/profile/onboarding/layout/router/tooling. Đã đọc đủ 9 specs và actual source; đang triển khai.
- backend_domains: evidence/contacts/support/sharing/article state, related API/tests, purge worker, account deletion. Đã đọc đủ 9 specs và actual source; đang triển khai.
- Một người tạo migrations: root. Chưa apply Phase 1 hosted; không DDL qua MCP.

## Preflight rulings

| Task/interface | Quyết định và lý do |
|---|---|
| F1-03 quota / immutable completed byte_size | Thêm expected_byte_size cho reservations, giữ byte_size là verified completion metadata; owner lock chống concurrent quota oversubscription |
| F1-03 purge / stale upload | Thêm purge_claimed_at/purged_at cho lease/retry; expired pending chuyển failed và giữ metadata sau object cleanup; permanent deletion mới xóa row |
| F1-06 staff / evidence RLS | Narrow DEFINER shared_evidence_key chỉ trả key khi member, visible share, selected uploaded evidence; staff không có quyền đọc private evidence table |
| F1-07 legacy UI / real data | Ports trả canonical UI models, cache chỉ update sau server success, optional version/demo fields; demo storage giữ riêng, không migrate lên server |
| F1-01 Root / urgent route | Auth hydration guard chỉ chặn protected routes; urgent và School Admin Demo luôn mở độc lập backend |

## Tests và blockers

Checkpoint backend local: **VERIFIED** cho F1-02.*, F1-03.1, F1-04.1, F1-05, F1-06.1/06.2, F1-07.5/07.6 trong phạm vi tests đã chạy. UI và full-stack acceptance vẫn PARTIALLY_VERIFIED; chưa G1/G2.

| Kiểm tra đã chạy | Kết quả |
|---|---|
| `uv run python scripts/check.py` | Exit 0; Ruff, Pyright 0 errors, 3 import boundaries; **154 offline passed**, 62 integration deselected |
| `uv run pytest -m integration -q --tb=short` | **62 passed**, 154 offline deselected, không skip |
| Full pgTAP | **13 files, 194 assertions PASS** |
| Strict ORM drift | PASS, đủ **22 app tables** đúng column/type/nullability |
| OpenAPI-derived cross-user matrix | PASS, **28 Phase 1 owner-ID operations**, route mới chưa có fixture làm test fail |
| Cases/plans | PASS idempotency, ownership, search không dấu, pagination, version409/latest, reorder, notes-only không ghi đè checkbox, timeline null time/cascade |
| Auth/Storage/account lifecycle thật local | PASS; synthetic JWT/Storage/SDK sessions/account deletion/retry, stale JWT bị chặn |
| Local advisors WARN/ERROR | Không security error; còn **2 performance WARN multiple permissive SELECT policies** cho owner/staff trên shares và selected evidence. Quyền là OR đúng scope, không unrestricted staff read |

OpenAPI đã được export từ routers thật. Chưa apply Phase 1 hosted, chưa merge Phase 1 hoặc tạo tag/worktrees Phase 2/3.

Sai khác có bằng chứng: Storage info thực dùng `content_type`/`etag`, gateway ban đầu chỉ map camelCase. Regression RED→GREEN đã sửa mapping; MIME không rõ dùng application/octet-stream, không tự tin metadata do client khai báo. Upload hourly budget dùng audit append-only và own-only count helper để init→delete không reset giới hạn.

Ruling về account delete: cleanup SDK sessions và own cases trước Auth delete cuối để retry không để orphan; không DB transaction nào mở qua Storage/Auth calls. Signed TUS capability đã cấp vẫn có thể dùng tới TTL sau Auth deletion — test đã chứng minh và cleanup. Chưa có tombstone sweep/capability revocation; không tuyên bố bảo đảm thu hồi tức thì. Privacy/operational gates cho người dùng thật vẫn riêng biệt.

Ruling về school tests: ephemeral fictional school tên Synthetic có thể dùng `verification_status=verified` để mô phỏng eligibility trong test, luôn cleanup; không seed vào committed seed.sql hoặc hosted. Production RLS không được nới; khi không có integration thật, UI hiển thị empty state.

Hosted UI smoke F1-08.3 có nguy cơ BLOCKED vì Chrome plugin đọc tab vẫn lỗi ở Phase 0; sẽ kiểm lại khi local E2E đủ. Không mở Chrome mới. Paid live model A-06 vẫn BLOCKED do thiếu cost ceiling, là P1 riêng.

## Review checkpoint

Fresh backend review phát hiện ba Important issues: concurrent account deletion có thể bỏ sót SDK/object mới; share→case lock đảo với case→share delete; foreign plan-item body UUID có thể gây unique violation 500. Đã sửa bằng durable profiles.deletion_started_at và account transaction lock/task-scoped cleanup bypass, parent-before-child share lock, conflict-safe item insert trả404 và rollback. Migration `20261107140312_f1_account_deletion_guard.sql` mới chỉ apply local qua CLI. Xóa đang dở tiếp tục chặn mutation sau lỗi và cho phép retry cleanup; tài khoản khác vẫn hoạt động.

Sau sửa: `scripts/check.py` **156 offline passed**, Pyright0errors, Ruff/import boundaries sạch; full integration **67 passed**, không skip. New deletion concurrency suite kiểm 15 targeted cases gồm running-agent guard, second-tab mutations, rollback/retry, liveAuth/Storage và drift. Cases/plans/sharing overlap subset **7 passed**. Public snapshots không đổi.

Frontend checkpoint: lint exit0; full Vitest **91 passed**,22files. Typecheck và incidents8tests pass. Build/boundary/E2E final chưa được ghi pass tại checkpoint này.
