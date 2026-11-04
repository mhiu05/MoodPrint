# Nhật ký thông minh, bỏ giao diện tìm bạn — Kế hoạch triển khai

> **Cho agent thực thi:** BẮT BUỘC dùng `superpowers:subagent-driven-development` (khuyến nghị) hoặc `superpowers:executing-plans` để làm từng task. Bước dùng checkbox `- [ ]`. Mọi kết quả lệnh ghi vào [08-execution-ledger.md](08-execution-ledger.md); không ghi "đã đạt" khi chưa chạy.

**Mục tiêu:** Bật mặc định mọi cờ tính năng mà app vẫn khởi động khi thiếu bí mật, xóa toàn bộ giao diện tìm bạn/kết nối/chat người–người, và làm Nhật ký thông minh hơn bằng embedding nhật ký, truy xuất lai có trích dẫn, memory tự động và skill mới.

**Kiến trúc:** Giữ modular monolith hiện có. Embedding nhật ký và memory tự động là dữ liệu dẫn xuất có khóa ngoại `ON DELETE CASCADE` về `journal_entries` (xóa đúng–sai bằng cấu trúc, không chỉ bằng code), được một worker có lease/fence sinh ra ngoài lượt chat. Truy xuất lai (ngữ nghĩa + từ khóa + gần nhất) thay phần thân `search_for_ai` nhưng giữ nguyên hợp đồng `journal-evidence-v1`. Backend matching/social giữ nguyên trong đợt này.

**Tech stack:** FastAPI + SQLAlchemy async, PostgreSQL 17 + pgvector (`extensions.vector`), Alembic, OpenAI Agents SDK 0.24.0, Voyage `voyage-4-lite`/1024, React 19 + Vite + TS, Vitest, Playwright.

**Spec:** yêu cầu chủ dự án trong phiên lập kế hoạch ngày 04/11/2026 (5 mục: cờ mặc định true, xóa UI matching, giữ Hoạt động, embedding + memory tự động, skill mới). Các mâu thuẫn và quyết định mở nằm ở [07](07-decisions-risks-unknowns.md).

## Global Constraints

- Thực thi trực tiếp trong `E:\MoodPrint`, nhánh `feat/journal-intelligence` (gốc `origin/main@565f5a74`, đã push lên origin). Mọi đường dẫn/số dòng trong kế hoạch là của `565f5a74`. Lúc viết kế hoạch, `test/04-11-26` và `main` local chậm 132 commit; `main` local đã được pull lên `565f5a74` ngày 04/11, nên bảng "Kiểm chứng giả định" bên dưới chỉ còn là ghi chép lịch sử. `E:\MoodPrint\backend\.env` trỏ tới DB hosted và chứa key thật: xem quy tắc ở [09-codex-prompt.md](09-codex-prompt.md) mục 2.
- Không sửa `.gitignore`. Không đưa secret, URL có mật khẩu, ID tài khoản thật hay nội dung nhật ký vào tài liệu, log hay test.
- Chuỗi hiển thị cho người dùng bằng tiếng Việt. Môi trường dev là Windows + PowerShell; lệnh trong tài liệu dùng cú pháp PowerShell.
- Migration mới duy nhất là `0029_journal_intelligence`, `down_revision = "0028_collaboration_defaults"`, chỉ thêm (expand-only). Không viết migration drop bảng social/matching trong đợt này.
- Mọi thay đổi API đi qua chuỗi `Pydantic/FastAPI → scripts/export_openapi.py → backend/openapi.json → npm run contracts:generate → frontend/src/api/generated/schema.d.ts`; CI kiểm `git diff --exit-code` trên hai file sinh.
- Bảng mới phải có trong `docs/supabase/schema.md`, setting mới trong `docs/backend/configuration.md`, endpoint mới trong `docs/backend/api-reference.md`. `scripts/check_docs.py` fail nếu thiếu.
- Không chạy migration hosted, không deploy, không push trong lúc thực thi task. JI-51 chỉ chạy khi chủ dự án duyệt rõ ràng.
- Bất biến giữ nguyên: mood scope theo lượt (`MoodReadScope`, chỉ Nhật ký/Nhịp, lượt hiện tại); `journal-evidence-v1` (ID nguồn ⊆ ID đã trả về trong lượt, kiểm revision dưới owner lock); context là projection có `data_version`/policy; receipts/idempotency; age gate 18+ qua `is_adult_eligible`; không có provider call nào giữ owner lock.
- Test viết trước (TDD): mỗi task có bước "chạy để thấy đỏ" trước khi viết code.

## Review Focus

Năm điều kiện mà test của từng task dễ bỏ sót nhất nhưng dễ làm hại người dùng thật. Mỗi dòng đã có test tương ứng trong task chủ quản.

1. **Sửa entry liên tục vài giây sau khi lưu.** Chỉ revision mới nhất được embed/trích memory; vector của revision cũ không bao giờ được dùng làm nguồn. Test: `test_rapid_edits_index_only_latest_revision` (JI-22).
2. **Voyage chậm (>3 s), 429 hoặc thiếu key giữa lượt chat.** Công cụ `search_journal_entries` vẫn trả kết quả từ khóa + gần nhất trong ngân sách thời gian, lượt không fail, `coverage.retrieval.reason` ghi lý do. Test: `test_query_embedding_timeout_falls_back_within_budget` (JI-23).
3. **Người dùng nói "đừng đọc nhật ký" trong lượt có chọn skill Nhìn lại tuần.** Không đọc nhật ký, skill vẫn trả lời không có dữ liệu, không có citation. Test: `test_skill_turn_respects_journal_refusal` (JI-40).
4. **Entry bị xóa (route, retention, xóa theo phạm vi, xóa tài khoản, guest hết hạn) khi job embed/trích đang chạy.** Không còn vector, job hay memory tự động mồ côi; publication bị fence. Test: `test_every_journal_delete_path_removes_derivatives` và `test_delete_during_lease_never_publishes` (JI-22, JI-30).
5. **Production thiếu `OPENAI_API_KEY`/`VOYAGE_API_KEY`/budget với mặc định mới.** App khởi động, `/health/ready` 200, session báo `aiStatus="configuration_missing"`, tìm kiếm ngữ nghĩa báo không khả dụng. Test: `test_production_defaults_boot_without_optional_secrets` (JI-02).

## Kiểm chứng giả định ban đầu (đã đọc code / tài liệu)

| Giả định trong yêu cầu | Thực tế | Bằng chứng |
| --- | --- | --- |
| Repo `E:\MoodPrint` là cơ sở | **Sai cơ sở.** HEAD `test/04-11-26` = `main` local = `5d2b3845` (30/10), chậm **132 commit** so với `origin/main@565f5a74` (04/11). Bản local chỉ tới migration 0019, không có `ai/skills`, `ai/proactive`, `ai/groups`, `ai/orchestration`, `ai/search` (chỉ còn `__pycache__`) | `git rev-list --left-right --count main...origin/main` → `0 132`; `git ls-tree origin/main backend/alembic/versions/` tới `0028_collaboration_defaults.py` |
| Working tree có thay đổi frontend chưa commit | Trong `E:\MoodPrint` chỉ `.gitignore` bị sửa. 5 file auth/landing chưa commit nằm trong `stash@{0}` ("workspace before test/04-11-26"): `AgeFields.tsx`, `GuestEntry.tsx`, `LoginPage.tsx`, `landing.css`, `Auth.tsx`, kèm báo cáo `11-live-release.md` | `git stash show --stat stash@{0}` |
| Hosted ở 0020, 0021–0028 chưa áp | **Mâu thuẫn tài liệu.** Bản commit của `docs/implementation-plans/agent-search-and-skills/11-live-release.md` ghi trạng thái khởi đầu hosted là `0024_three_agent_groups`. Bản chưa commit trong `stash@{0}` ghi đã áp SQL đã review lên **0028**, deploy `669c7a8d` lúc 17:37 UTC 03/11 rồi `565f5a74` ngày 04/11, runtime SSM version 24 mở các capability với cohort rỗng. Ghi chép bộ nhớ "0020 ngày 01/11" đã cũ. **Chưa xác minh trực tiếp DB** | `git show stash@{0}:docs/implementation-plans/agent-search-and-skills/11-live-release.md`, mục "First deployed acceptance" và "Final deployment" |
| Cờ đang chắn "schema chưa migrate" | Phần lớn **không**. `READY_REVISIONS = ("0028_collaboration_defaults",)` và ORM luôn map cột của 0021–0028 bất kể cờ. Image hiện tại không bao giờ ready trên schema < 0028, nên cờ không phải lớp chắn schema | `backend/app/core/revisions.py`; docstring cùng file |
| Bật mọi cờ trên hosted gây 500 vì schema | Với hosted 0028 thì không. Rủi ro thật là **validator production làm app không khởi động** khi thiếu key/budget, và `PROACTIVE_WORKER_ENABLED` mặc định true làm container `proactive` crash-loop nếu `AI_DAILY_BUDGET_USD=0` | `backend/app/core/config.py:194-235` |
| Journal search chỉ icontains, 5 entry, 90 ngày | Đúng. Nhưng **90 ngày là chính sách lưu giữ**, không chỉ giới hạn tìm kiếm: retention xóa cứng entry cũ hơn 89 ngày, và ghi/đọc entry đều kẹp 90 ngày. Nới 90 ngày là quyết định chính sách dữ liệu, không phải tối ưu truy xuất | `backend/app/jobs/retention.py:112-125`, `backend/app/modules/journal/service.py:15-41`, `backend/app/modules/journal/ai.py:34-41` |
| Có thêm đường đọc nhật ký khác | Có, ba đường: tool trực tiếp của Nhật ký (`runtime.py:507-543`), consult của Điều phối (`orchestration/workflow.py:163-183`, ≤5 entry trong ≤14 ngày, 600 ký tự), check-in buổi sáng (`proactive/context.py`, entry hôm qua). Kế hoạch đổi đường 1, đường 2 tùy chọn (JI-25), không đụng đường 3 | như cột trái |
| Embedding chỉ cho memory đã duyệt | Đúng, nhưng **thực tế không chạy với người dùng thật**: preference `semantic_memory_enabled` mặc định `False`, và frontend không còn control nào bật nó | `backend/app/ai/models.py:33`; `rg semanticMemory frontend/src` không có component nào |
| "Agent Settings ở frontend gán skill cho agent" | Không có cơ chế gán. Hai skill hiện có áp cho **mọi** agent V3 (`resolve_skill` chỉ kiểm `agent in V3_IDS`) và xuất hiện qua menu "+" của composer | `backend/app/ai/skills/resolver.py:6-8`, `frontend/src/features/real/composer/ComposerOptions.tsx` |
| Có màn "Privacy" chứa MATCH | Không còn màn Privacy riêng. Account chỉ còn `AdultEligibility` + `AccountActions`. MATCH chỉ còn ở luồng social và trong validator session (`api/session.ts:32`) | `frontend/src/features/real/RealApp.tsx:2270-2279` |
| Hoạt động/challenges/proactive phụ thuộc `modules/activities` | **Không.** Không file nào trong `backend/app/ai` import `modules.activities` hay đọc `activities_enabled`. Phụ thuộc social duy nhất là đường Cầu Nối cũ (`proactive/context.py:163-178` đọc `modules.social.models`, `proactive/policy.py:63-77`), và đường này đã bị bỏ qua khi V3 mở (`v3_reason` → `legacy_companion`) | `rg "modules.activities\|activities_enabled\|modules.social" backend/app/ai` |
| Memory tự động "liên kết entry nguồn" | `memories.proposal_id` hiện **NOT NULL UNIQUE** và context dán nhãn mọi memory là "Approved memory data". Memory tự động cần đổi schema (0029) và đổi nhãn context | `backend/app/infrastructure/database/models.py:152-161`, `backend/app/ai/context.py:118-120` |
| Prompt `journal_instructions` | Hiện cấm rõ "embeddings or automatic memories". Đây là bất biến prompt phải đổi có chủ đích | `backend/app/ai/journal.py:85-104` |

## Bản đồ tài liệu

- [01-flags.md](01-flags.md): kiểm kê 31 cờ boolean, mặc định mới, validator degrade-không-crash, nền test (JI-01, JI-02)
- [02-matching-ui-removal.md](02-matching-ui-removal.md): xóa UI tìm bạn/tin nhắn/hoạt động hai người, dọn copy, spec e2e (JI-10…JI-13)
- [03-journal-embedding.md](03-journal-embedding.md): migration 0029, worker embed, truy xuất lai, công tắc người dùng, đo chất lượng (JI-20…JI-25)
- [04-auto-memory.md](04-auto-memory.md): memory tự động từ nhật ký (JI-30, JI-31)
- [05-skills.md](05-skills.md): 4 skill mới cho Nhật ký/Điều phối (JI-40)
- [06-verification-and-release.md](06-verification-and-release.md): cổng kiểm tra, SQL review 0029, thứ tự migrate/deploy, checklist demo, dự phòng (JI-50, JI-51)
- [07-decisions-risks-unknowns.md](07-decisions-risks-unknowns.md): quyết định mở, mâu thuẫn, rủi ro, điều không xác minh được
- [08-execution-ledger.md](08-execution-ledger.md): sổ thực thi (điền khi chạy)
- [09-codex-prompt.md](09-codex-prompt.md): prompt bàn giao cho agent triển khai (Codex)

## Thứ tự theo giá trị demo, phụ thuộc và cut line

```text
JI-00 baseline
  ├─ JI-01 cờ + nền test ─ JI-02 validator degrade ───────────────┐
  ├─ JI-10 xóa route/nav/polling ─ JI-11 dọn copy ─ JI-13 spec      │
  │        JI-12 backend: bỏ card discovery khỏi V3 + SKILL hangout │
  └─ JI-20 migration 0029 + ORM                                     │
        ├─ JI-21 công tắc + thông báo + API journal-ai              │
        ├─ JI-22 job embed, hủy hiệu lực, backfill                  │
        │     └─ JI-23 truy xuất lai + tool + prompt ─ JI-24 đo     │
        │                                                           │
════════ CUT LINE A (bắt buộc cho demo ở trên) ═════════════════════╡
        ├─ JI-40 skill mới (tối thiểu weekly-review + mood-patterns)│
════════ CUT LINE B ════════════════════════════════════════════════╡
        ├─ JI-30 worker memory tự động ─ JI-31 UI/label memory      │
        └─ JI-25 truy xuất lai cho consult của Điều phối            │
JI-50 cổng kiểm tra (sau mọi task đã làm) ─ JI-51 rollout/demo ◄────┘
```

| Task | Nội dung | Phụ thuộc | Công sức | Nhóm |
| --- | --- | --- | --- | --- |
| JI-00 | Baseline, DB disposable, ledger | — | 0,25 ngày | Bắt buộc |
| JI-01 | Mặc định true + nền test `ALL_FEATURES_OFF` | JI-00 | 0,75 | Bắt buộc |
| JI-02 | Validator degrade, worker idle, test khởi động | JI-01 | 0,75 | Bắt buộc |
| JI-10 | Xóa `social/`, `activities/`, `Safety.tsx`, route, nav, polling | JI-00 | 0,75 | Bắt buộc |
| JI-11 | Dọn copy MATCH/tìm bạn, fallback card `discovery` | JI-10 | 0,5 | Bắt buộc |
| JI-12 | Backend: V3 không còn được mời trả card `discovery`; SKILL hangout v2 | JI-00 | 0,5 | Bắt buộc |
| JI-13 | Xóa/viết lại spec e2e/fullstack | JI-10, JI-11 | 1 | Bắt buộc |
| JI-20 | Migration 0029 + ORM + test migration | JI-00 | 1 | Bắt buộc |
| JI-21 | `journal_ai_settings` API + thông báo + công tắc trong Tài khoản | JI-20 | 1 | Bắt buộc |
| JI-22 | Enqueue/hủy hiệu lực trong route nhật ký, worker embed, reconcile/backfill | JI-20 | 1,5 | Bắt buộc |
| JI-23 | Truy xuất lai trong `search_journal_entries` + prompt | JI-22 | 1,5 | Bắt buộc |
| JI-24 | Bộ đo chất lượng truy xuất + metric demo | JI-23 | 0,5 | Bắt buộc |
| JI-40 | Registry có allowlist agent + 4 skill + resolver + chip | JI-23 (để skill Nhật ký dùng truy xuất mới) | 1,5 | Cắt được (A) |
| JI-30 | Worker trích memory tự động, validator an toàn, accounting | JI-20, JI-22 | 2 | Cắt được (B) |
| JI-31 | MemoryDTO/UI nhãn "tự động", link entry, nhãn context | JI-30 | 1 | Cắt được (B) |
| JI-25 | Hybrid cho `journal_excerpts` của Điều phối | JI-23 | 0,5 | Cắt được (B) |
| JI-50 | Contract, docs inventory, SQL review 0029, cổng đầy đủ | mọi task đã làm | 1 | Bắt buộc |
| JI-51 | Rollout hosted + checklist demo | JI-50 + duyệt chủ dự án | 0,5 + cửa sổ bảo trì | Bắt buộc nếu demo trên hosted |

Tổng phần bắt buộc ≈ 11,5 ngày công; thêm A ≈ 1,5; thêm B ≈ 3,5. **Schema 0029 gồm cả phần memory tự động ngay từ đầu**, kể cả khi B bị cắt, để chỉ phải review/áp SQL hosted một lần. Cột thừa là expand-only, vô hại.

**Việc để sau demo (không làm trong đợt này):** xóa nhánh code "cờ tắt" và các cờ thành hằng; gỡ `include_router` của social/matching/profiles/activities/notifications cùng test backend tương ứng; migration drop bảng 0011–0013 sau backup; xóa `sandbox_enabled` (không có nơi dùng); bỏ purpose MATCH khỏi session DTO và `api/session.ts`; xét chunking embedding cho entry > 7.000 ký tự; xét HNSW khi số entry/người dùng lớn; xét chính sách lưu giữ > 90 ngày (OD-05).

## Trạng thái

2026-11-04: kế hoạch viết xong; code được đọc và kiểm chứng trên `origin/main@565f5a74`. Nhánh `feat/journal-intelligence` đã push lên origin. Triển khai làm trong `E:\MoodPrint` theo [09-codex-prompt.md](09-codex-prompt.md).
