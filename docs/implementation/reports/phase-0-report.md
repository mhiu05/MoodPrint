# Phase 0 — Implementation report

Ngày: 2026-11-07. Nhánh: `feat/phase-0-foundation`. Implementation baseline: `3db6c7a7`.

**Trạng thái tổng thể: PARTIALLY_VERIFIED. G0: BLOCKED.** Backend và agent foundation chạy được trên Supabase local. Chưa đạt G0 tổng thể vì hosted configuration, migration apply, S-05 và hosted smoke chưa được xác minh. Không bắt đầu Phase 1 integration, không merge và không tạo baseline tag.

## Phạm vi đã triển khai

| Task | Trạng thái | Kết quả |
|---|---|---|
| F0-01.1–01.3 | VERIFIED | uv workspace Python 3.12, lockfile; Ruff, Pyright, pytest, import-linter. Negative boundary experiment thực sự bị chặn và probe đã xóa |
| F0-02.1–02.2 | VERIFIED | Typed settings, test không đọc owner dotenv, remote test DB bị từ chối; secret masking và structured logging, gồm handler Uvicorn |
| F0-03.1–03.2 | VERIFIED local | App factory/lifespan, health/readiness, CORS/request ID/error envelope, async engine và transaction-local verified claims |
| F0-04.1–04.3 | VERIFIED local | JWT ES256/JWKS cache/refetch, lỗi 503 khi JWKS outage, anonymous/invalid token bị chặn, live-user check, lazy profile seed/PATCH, secret boundaries |
| F0-05.1–05.4 | VERIFIED local | 10 CLI SQL migrations, private schemas/role/grants/RLS/composite FKs/triggers/indexes; handwritten ORM + drift test; reset từ DB trống |
| F0-06.1–06.2 | VERIFIED local / PARTIALLY_VERIFIED hosted | Private gateway, random keys, signed TUS/download; 20 MiB interruption/resume, expiry renewal, immutable original. Hosted bucket config đọc được; chưa hosted upload smoke |
| F0-07.1–07.3 | VERIFIED local | Official SDK Companion, diagnostic tool, policies/budgets/timeouts/cancel, persistent sessions, translated SSE, transcript/run/usage persistence, disconnect recovery |
| F0-07.4–07.5 | VERIFIED local | Persisted approval, approve/reject, restart/resume, expiry recovery và narrow reconciler `SKIP LOCKED` |
| F0-08.1–08.4 | VERIFIED local | Explicit consent, candidate lifecycle, memory CRUD/dedupe/supersede/hard delete, lexical search không dấu, Context Builder budget/provenance/dropped/degraded behavior |
| F0-09.1–09.2 | VERIFIED local | DTO/Protocol contracts, synthetic fixture retriever + reusable contract suite, 12 JSON Schema snapshots; OpenAPI typed REST/SSE và cursor pagination |
| F0-10.1 | VERIFIED local | `verify_phase0.py` thực thi quality/reset/bootstrap/pgTAP/integration/frontend. Receipt chỉ chứng minh prerequisite local, không tự coi hosted G0 đạt |
| F0-10.2 | VERIFIED | GitHub Actions trên commit `ab9d4397`: offline và integration jobs đều success |
| F0-10.3 | PARTIALLY_VERIFIED / BLOCKED apply | Dry-run hosted exit 0, liệt kê đúng 10 migrations, không history drift; chưa apply/provision/smoke |
| F0-11.1 | PARTIALLY_VERIFIED | Hosted Auth settings/JWKS/bucket đã GET-only verify; chưa đọc/đổi các mục Dashboard còn lại |

Manifest file: [phase-0-files.txt](phase-0-files.txt). Không sửa frontend hoặc `.gitignore`. Ba file MCP của owner vẫn giữ ngoài commit: `.claude/settings.local.json`, `.cursor/mcp.json`, `.mcp.json`.

## Bằng chứng chạy thực tế

| Lệnh / kiểm tra | Kết quả |
|---|---|
| `uv sync --all-packages` | Exit 0; Python 3.12.13, SDK 0.24.0, SQLAlchemy 2.1.8, FastAPI 0.162.0 được khóa trong `uv.lock` |
| `uv run python scripts/check.py` trên code cuối | Exit 0; Ruff lint/format sạch, Pyright 0 errors, 3 import contracts kept; **140 offline tests passed**, 43 integration deselected |
| Negative import boundary | Import thử `shared -> app` bị reject; probe được xóa trong `finally`; linter sạch sau khôi phục |
| `uv run python scripts/export_contract_schemas.py --check` | Exit 0 |
| `uv run python scripts/export_openapi.py --check` | Exit 0 |
| `uv run python scripts/verify_phase0.py` trên commit `3db6c7a7` | Exit 0; **140 offline tests, 43 integration tests, 84 pgTAP assertions, 54 frontend tests**. Local receipt khớp full SHA `3db6c7a72f56ae501bb17dc11b0bf44e023c5708`; không coi đây là hosted G0 |
| `npx --yes supabase@2.122.1 test db` trong gate | **9 files, 84 assertions PASS** |
| `uv run pytest -m integration -q -ra` trên code cuối | **43 passed**, 140 offline deselected; không integration nào skip |
| `test_concurrent_users_never_share_claims` | PASS: 50 identity đồng thời, pool 2 connections; owner rows/claims đúng trước và sau yield |
| Commit/rollback cleanup, engine restart, SDK metadata drift | PASS |
| Memory từ conversation A vào context conversation B | PASS; không chép private memory vào SDK replay |
| Approval pause + runtime mới + resume | PASS; 7+12 = **19 tokens, 2 requests, 1 tool call** |
| `npx --yes supabase@2.122.1 db advisors --local --type all --level warn --fail-on error` | Exit 0, **No issues found** ở mức WARN/ERROR |
| Frontend baseline và regression | Typecheck/lint/build/boundary checks exit 0; **54/54 Vitest**, 13 files pass |
| `git diff 1a3c81fc -- frontend .gitignore` | Rỗng |
| Staged secret scan | PASS; không stage `.env`, local keys/cache, MCP config hoặc runtime credentials |

Raw local logs ở `.local/verification/`, không commit vì CLI có thể ghi credentials local. Không in secret ra báo cáo. Test data chỉ synthetic; Storage suite cleanup xác nhận 0 evidence objects và 0 synthetic Auth users sau suite.

Cleanup count-only sau full gate: **0 Auth users, 0 evidence objects, 0 SDK sessions** trên local stack.

## Database và security

- `app`, `app_private`, `agent_store`; không expose schema ứng dụng qua Data API.
- `moodprint_api`: NOINHERIT/NOBYPASSRLS; runtime từ chối role `postgres`. UoW dùng `SET LOCAL ROLE authenticated` và parameterized `set_config(..., true)` từ JWT đã verify.
- Tất cả app/SDK tables có RLS và policy. Owner được kiểm ở service lẫn DB; composite FKs chống liên kết chéo owner. Audit append-only, reconciler không có quyền đọc content trực tiếp.
- Không giữ transaction qua model/Storage HTTP calls. SDK replay riêng với transcript và long-term memory.
- Private bucket, không public/user Storage policies; original keys không chứa filename, không upsert. Quota/upload domain APIs thuộc Phase 1, chưa được giả lập thành tính năng thật.
- Privacy defaults: `store=False`, tracing disabled, sensitive trace data disabled. Production registry chỉ `get_server_time`.
- Không paid live OpenAI evaluation. `gpt-6-luna` giữ nguyên; SDK/provider compatibility offline đã kiểm, live model access chưa kiểm vì chưa có cost ceiling O-09.

## Sai khác đã quyết định và lý do

1. **Không sửa `.gitignore`** theo chỉ dẫn trực tiếp của owner. Hệ quả: cache/local artifacts có thể xuất hiện untracked; stage theo đường dẫn cụ thể.
2. Dùng linked worktree hiện có vì writable root giới hạn; tạo đúng nhánh feature. Không hard-reset và không tạo worktree Phase 2/3.
3. CLI pin `2.122.1` do CLI v3 có breaking changes. Local dùng `[local_smtp]`, ES256 JWK có `key_ops`; không cần HS256 fallback.
4. Signed TUS endpoint thực tế là `/upload/resumable/sign`. Endpoint không có `/sign` trả RLS error khi chỉ có signed token; đã sửa theo request thực, không thêm broad policies.
5. SDK 0.24.0 dùng `function_tool(timeout=...)`; compaction class ở `agents.memory`; resume dùng async `RunState.from_string` với context mới. Không đổi SDK/model để né lỗi.
6. SDK usage sau resume là cumulative; lưu replacement counters thay vì cộng lại.
7. Thêm internal `memory_candidates.approved_memory_id` composite FK để mọi approved candidate, kể cả dedupe/edit, được xóa cùng canonical memory. Canonical dedupe nối hai supersede chains dưới owner-scoped transaction lock, không làm mất chain cũ.
8. Retrieval-only metadata không bump content timestamp/version. Tránh memory cũ tự thành mới khi đọc.
9. Local `postgres` không có quyền grant tiếp USAGE trên schema `auth` cho base role. Cleanup test kiểm base `current_user` và GUC rỗng, rồi switch role được phép trên **cùng connection** và xác nhận `auth.uid() IS NULL`. Không mở rộng quyền schema `auth` để vượt lỗi test.
10. ContextRequest thêm optional identity/profile/summary fields; không email/raw claims. `AgentSession` dùng item boundary không phụ thuộc SDK. `AUTH_TEST_JWT_SECRET` là optional test-only field; dotenv example không bắt buộc chứa secret test này.
11. Tool budget được enforced trong registry wrapper để mỗi execution chỉ đếm một lần; runtime chặn tổng configured limit, có deterministic tests.

Review độc lập phát hiện các vấn đề memory deletion, cumulative usage, stale timestamps và OpenAPI response schemas; đều có regression RED→GREEN. Một test recovery ban đầu nhầm integer return của reconciler là tổng approval+heartbeat; đã chỉnh để kiểm recovery state thực, không sửa production semantics cho test.

## Spikes

| Spike | Trạng thái | Kết luận |
|---|---|---|
| [S-01](../spikes/S-01.md) | VERIFIED local expiry path; PARTIALLY_VERIFIED wall-clock >2h | 20 MiB resume, renewal cùng URL; expiry test dùng valid local capability TTL 15s. Không tuyên bố đã đợi hơn hai giờ |
| [S-02](../spikes/S-02.md) | VERIFIED local | Schema translation và UTF-8 session tồn tại sau engine restart |
| [S-03](../spikes/S-03.md) | VERIFIED offline/local | Hai process/runtime mới resume được; không serialize AuthContext |
| [S-04](../spikes/S-04.md) | VERIFIED | Hai stack port/data/ES256 keys riêng; chỉ stack spike đã dừng |
| [S-05](../spikes/S-05.md) | BLOCKED | Chưa hosted runtime role/pooler isolation proof |

## Hosted evidence và Dashboard

Project identity: URL `https://xhlshihobyxrgfqrdafh.supabase.co`, ref trong privileged DB URL khớp; không truy cập database MoodPrint cũ.

- Hosted `GET /auth/v1/settings`: signup bật, email confirmation bật, `external.anonymous_users=false`.
- Hosted JWKS: HTTP 200, ES256.
- Hosted bucket GET: HTTP 200, `incident-evidence`, private, `file_size_limit=null`, `allowed_mime_types=null`.
- `push_hosted.py --dry-run`: exit 0; cả 10 migrations còn pending, không có migration lạ trong hosted history. **Chưa apply DDL**, chưa đặt password role, chưa hosted smoke/advisors sau apply.
- Owner đã đổi tên privileged connection từ `DATABASE_URL` sang `SUPABASE_DB_URL`; không ghi đè giá trị secret. Runtime `DATABASE_URL` chỉ được sinh bằng script provisioning sau khi điều kiện đủ.
- CUA đã inventory đúng Chrome profile và tab Supabase hiện có. Những lần đọc snapshot/screenshot/CDP bị lỗi `Cannot read properties of undefined (reading 'timeoutMs')` hoặc deadline trước command dispatch. Owner mở lại tab mới, lỗi đọc vẫn tái diễn. Không kết luận owner chưa đăng nhập từ lỗi này.
- Một Chrome mới được mở trong lần thử fallback đầu rồi đã đóng theo yêu cầu owner. Chỉ dùng Chrome hiện có sau chỉ dẫn đó.

Các mục Dashboard chưa có bằng chứng: plan/region/compute, global file limit, Site URL/redirect allow-list, password policy, JWT expiry, Data API exposed schemas và pooler host/mode. Không có thay đổi Dashboard nào được tuyên bố đã thực hiện. Hosted apply vẫn chờ prerequisite F0-11.1.

## Git, PR, gates và phần còn lại

Implementation commits:

- `cb3ed5a8`: workspace + shared contracts.
- `6acd76fb`: private database/RLS/UoW/local tooling.
- `ca3958b9`: Agent runtime/session/context.
- `3db6c7a7`: authenticated API, consent memory, SSE, tests, OpenAPI, CI.

- Branch đã push tới `origin/feat/phase-0-foundation`.
- [Draft PR #46](https://github.com/mhiu05/MoodPrint/pull/46), base `mhiu05/feat-refactor`, OPEN/draft.
- [CI run 42366869339](https://github.com/mhiu05/MoodPrint/actions/runs/42366869339) trên full SHA `ab9d4397ce84d38c99d1b5dd4c6f2ec6844d62fa`: **success**, cả offline và integration. Remote run bao gồm frontend typecheck/lint/unit/build/boundaries và Supabase local thật.
- Không merge vào `mhiu05/feat-refactor` hoặc `main` khi G0 chưa đạt. Không tạo `baseline/phase-1-verified` tag.

- **G0 BLOCKED**: còn F0-11.1 Dashboard proof, hosted apply/history/advisors/smoke và S-05.
- **G1 NOT_STARTED**: Phase 1 chưa đủ điều kiện bắt đầu; chưa chứng minh product vertical slice.
- **G2 NOT_STARTED**: snapshots/fixture có sẵn nhưng chưa freeze integration baseline, ownership rules/CI evidence và frontend composition.
- Owner/tool actions còn mở: khôi phục browser-control tab hiện có; xác minh các Dashboard settings còn thiếu. Nếu Free plan thì cần đặt application evidence limit tương ứng; không tự nâng gói.
- Live model smoke A-06 là P1, cần cost ceiling rõ ràng trước khi chạy.

**Chưa sẵn sàng cho dữ liệu học sinh thật.** Các safety/privacy/legal/operational gates ở `00` §6 là điều kiện riêng, chưa được thực hiện trong Phase 0/1.
