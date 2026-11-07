# Phase 0 — Implementation report

Ngày: 2026-11-07. Branch: `feat/phase-0-foundation`. Implementation SHA: `b3ce86d0f4730841486285ab435a9b7433b80f05`.

**VERIFIED — G0 đạt.** Các P0 trong `07` §3 đã được kiểm chứng local và hosted. Approval/recovery P1 cần cho G2 cũng có deterministic tests. Không coi đây là chứng nhận vận hành cho học sinh thật.

## Tasks và files

| Task IDs | Trạng thái | Kết quả |
|---|---|---|
| F0-01.1–01.3 | VERIFIED | Python 3.12 uv workspace, lockfile, Ruff/Pyright/Pytest, 3 import contracts và negative boundary check |
| F0-02.1–02.2 | VERIFIED | Typed settings/config riêng; test không đọc owner dotenv, từ chối remote DB; structured logging/redaction, cả Uvicorn |
| F0-03.1–03.2 | VERIFIED | Factory/lifespan, health/ready, CORS/request ID/errors, async UoW với transaction-local verified claims |
| F0-04.1–04.3 | VERIFIED | ES256/JWKS/cache/outage handling; token expired/invalid/anonymous/deleted-user; profile lazy seed/PATCH; infrastructure boundaries |
| F0-05.1–05.4 | VERIFIED | 11 CLI migrations, private schemas/role/RLS/composite FKs/triggers/indexes; ORM drift, clean reset |
| F0-06.1–06.2 | VERIFIED cho G0 | Private gateway, safe keys, signed TUS/download, immutable original; giới hạn S-01 bên dưới |
| F0-07.1–07.3 | VERIFIED | Một official SDK Companion, diagnostic tool, policies/budgets/timeouts/cancel, persistent sessions, SSE/run/usage, disconnect recovery |
| F0-07.4–07.5 | VERIFIED | Persisted approve/reject, restart/resume, expiry và narrow reconciler SKIP LOCKED |
| F0-08.1–08.4 | VERIFIED | Explicit candidate consent/edit/reject, CRUD/dedupe/supersede/delete, lexical retrieval, Context Builder budget/provenance/dropped/degraded |
| F0-09.1–09.2 | VERIFIED | Shared contracts, synthetic fixture/reusable retriever suite, 12 snapshots, typed OpenAPI REST/SSE/cursor paging |
| F0-10.1–10.2 | VERIFIED | Full local gate và GitHub Actions offline/integration |
| F0-10.3 | VERIFIED | Hosted dry-run/apply/history/provisioning/S-05/advisors/smoke/cleanup |
| F0-11.1 | VERIFIED qua owner handoff | Dashboard report có PDF; agent kiểm lại Auth API. Maximum upload khi giữ spend cap còn PARTIALLY_VERIFIED |

Manifest: [phase-0-files.txt](phase-0-files.txt). Frontend và `.gitignore` không đổi so với `1a3c81fc`. Ba owner MCP configs nằm ngoài commit: `.claude/settings.local.json`, `.cursor/mcp.json`, `.mcp.json`.

## Tests đã chạy

| Lệnh / kiểm tra | Kết quả |
|---|---|
| `uv sync --all-packages` | Exit 0; Python 3.12.13; SDK 0.24.0, SQLAlchemy 2.1.8, FastAPI 0.162.0 khóa trong uv.lock |
| `uv run python scripts/check.py` | Exit 0; Ruff lint/format sạch, Pyright 0 errors, 3 contracts kept; **150 offline passed**, 45 integration deselected |
| Contract/OpenAPI exports `--check` | Cả hai exit 0 |
| `uv run python scripts/verify_phase0.py` trên `b3ce86d0` | **Exit 0**, đủ 8 checkpoints, receipt scope local khớp SHA |
| Local reset/bootstrap và `supabase@2.122.1 test db` | **10 files, 104 assertions PASS** |
| Integration trong full gate | **45 passed**, 150 offline deselected; không integration nào skip |
| Concurrent-user isolation | PASS: 50 requests, pool hai connections; claims/owner đúng trước và sau yield |
| Commit/rollback cleanup, UTF-8 SDK session/engine restart/schema drift | PASS |
| Memory conversation A vào context B | PASS; private memory không bị chép vào SDK replay |
| Approval/process restart/resume | PASS; **19 tokens, 2 requests, 1 tool call**, không double-count cumulative usage |
| Frontend local gate | **54/54**, 13 files, `--maxWorkers=2` |
| Frontend CI | Typecheck/lint/unit/build/boundaries pass; source không đổi |
| `git diff 1a3c81fc -- frontend .gitignore` | Rỗng |
| `check_hosted_auth_settings.py` | Exit 0; signup/confirmation bật, anonymous tắt |
| S-05 sau migration cuối | Exit 0; session_pooler, 2 users, 50 requests, 2 connections, cleanup completed |
| `smoke_hosted.py --phase 0` sau migration cuối | Exit 0; readiness/profile/memory/cross-user 404/private signed upload-download/cleanup |
| Hosted cleanup count-only SELECT | **0 synthetic users, 0 evidence objects, 0 profiles, 0 memories** |

Raw logs nằm ở `.local/verification/`, không commit. Dữ liệu chỉ synthetic. Secrets, local keys/cache và owner MCP config không được stage.

Một lượt gate trên `ee42ea90` có 3 frontend failures: hai timeout 5 giây và một lỗi tiếp theo ở Action Plan suite khi chạy 13 jsdom workers trên máy dùng chung. Cùng 54 tests pass với hai workers, giữ nguyên assertions/timeouts. Script gate được giới hạn workers; full gate `b3ce86d0` pass. Failed log giữ riêng tại `.local/verification/phase0-frontend-parallel-timeout.log`.

Một CI run `b3ce86d0` lỗi ở bước start Supabase trước tests; run độc lập cùng SHA pass đầy đủ. Đã yêu cầu rerun job hạ tầng lỗi; không coi lần lỗi đó là test pass.

## Hosted database và security

Project **db-school-violence / xhlshihobyxrgfqrdafh** được xác minh bằng MCP URL và privileged DB URL. Không truy cập MoodPrint database cũ.

- 10 migrations baseline: dry-run rồi apply trên `770dbcd3`, sau full local gate tương ứng.
- Hosted probe phát hiện SQLAlchemy asyncpg không nhận trực tiếp URL `sslmode`; hai regression tests RED → GREEN. Engine chuyển sang driver option `ssl`, giữ nguyên TLS mode, không in connection exception.
- Performance Advisor phát hiện ba composite FKs thiếu covering indexes. Migration forward-only `20261107121921_f0_covering_fk_indexes.sql` được CLI tạo, kiểm bằng reset/pgTAP/full gate, dry-run rồi apply trên `b3ce86d0`.
- MCP read-only xác nhận **11 versions/names khớp repo**. Không MCP apply_migration hoặc ad-hoc DDL.
- **Security Advisor: 0 findings**. Không WARN `rls_auto_enable` hoặc RLS-disabled findings.
- **Performance Advisor: không WARN/ERROR, không unindexed FKs**. Còn INFO unused indexes trên DB mới và Auth connection allocation absolute 10; không bỏ index cần thiết hoặc đổi tài nguyên ngoài phạm vi. Tham khảo [unused indexes](https://supabase.com/docs/guides/database/database-linter?lint=0005_unused_index), [connection strategy](https://supabase.com/docs/guides/deployment/going-into-prod).
- Runtime `moodprint_api` NOINHERIT/NOBYPASSRLS; backend từ chối postgres. UoW dùng SET LOCAL ROLE authenticated và parameterized set_config từ verified JWT. Owner kiểm ở service lẫn PostgreSQL; composite FKs ngăn liên kết chéo user; audit append-only.
- Không giữ DB transaction qua Auth/Storage/model HTTP. Script thêm generated DATABASE_URL riêng vào root `.env`, giữ nguyên privileged SUPABASE_DB_URL và các giá trị owner. Không in hoặc commit credentials.

## Dashboard

[Dashboard handoff và PDF](dashboard-handoff.md) là báo cáo ChatGPT Work do owner chuyển. Coding agent chưa trực tiếp đọc PDF hoặc thao tác Dashboard thành công.

| Mục | Giá trị ghi nhận |
|---|---|
| Organization/region/plan/compute | VDaAgent / ap-northeast-2 / Pro / Micro; Healthy |
| Global upload | 50 MB, spend cap giữ nguyên; maximum khi giữ cap PARTIALLY_VERIFIED |
| Bucket | incident-evidence private; size/MIME limits null; không đổi broad policies |
| Site URL | http://127.0.0.1:5173 |
| Redirects | HTTP 127.0.0.1:5173/**, 127.0.0.1:5178/**, localhost:5173/** |
| Auth | Signup/confirmation bật, anonymous tắt; minimum password 8, leaked password protection bật |
| JWT | 3600 giây, current ECC P-256/ES256; không rotate |
| Data API | public, graphql_public; không app/app_private/agent_store; auto-expose new public tables giữ nguyên |
| Session pooler | aws-0-ap-northeast-2.pooler.supabase.com:5432 |

Ruling: application evidence limit **50,000,000 bytes** để phù hợp cấu hình hiện có; không tắt spend cap hoặc mua tài nguyên. Đây là điều chỉnh từ mặc định lớn hơn của plan; bucket không bị đặt limit riêng.

## Spikes, quyết định và sai khác

| Spike | Trạng thái | Kết luận |
|---|---|---|
| [S-01](../spikes/S-01.md) | VERIFIED bounded expiry/resume; PARTIALLY_VERIFIED wall-clock >2h | 20 MiB, chunk 6 MiB, client restart, x-signature POST/HEAD/PATCH, renewal cùng URL. Expiry dùng valid local capability TTL 15s; chưa chờ thực tế hơn 2 giờ |
| [S-02](../spikes/S-02.md) | VERIFIED | SDK schema translation, UTF-8, engine restart |
| [S-03](../spikes/S-03.md) | VERIFIED | Hai process/runtime restart/resume; không serialize AuthContext |
| [S-04](../spikes/S-04.md) | VERIFIED | Hai stacks riêng port/data/ES256 keys; chỉ stack spike được dừng |
| [S-05](../spikes/S-05.md) | VERIFIED hosted | Session pooler role/claims isolation pass; không cần direct/transaction fallback |

1. Không sửa `.gitignore` theo owner; stage explicit paths. Dùng linked worktree hiện có do writable-root giới hạn; không reset hoặc tạo Phase 2/3 worktrees.
2. CLI pin 2.122.1 do v3 breaking changes; local dùng ES256; không thêm Alembic.
3. Signed TUS endpoint thực `/upload/resumable/sign`; endpoint thiếu `/sign` trả JWT/RLS 403. Sửa theo request thực, không mở quyền Storage. Object info NoSuchKey HTTP400/statusCode404 được normalize thành missing.
4. SDK actual timeout/compaction/async RunState interfaces được kiểm; resumed usage cumulative được lưu replacement counters.
5. Internal approved_memory_id composite FK bảo đảm hard-delete candidate kể cả dedupe/edit. Merge supersede chains dùng owner-scoped lock; retrieval metadata không bump content timestamp/version.
6. Không grant rộng USAGE auth cho base role. Cleanup test kiểm base role/GUC, rồi switch authenticated trên cùng connection để xác nhận auth.uid null.

Review độc lập foundation đã có regression fixes cho các Important findings; review hosted delta không phát hiện Critical/Important blocker.

## Git, gates, phần còn lại

Commits: `cb3ed5a8` workspace/contracts; `6acd76fb` DB/UoW; `ca3958b9` agent; `3db6c7a7` API/memory/SSE; `770dbcd3` hosted probe/upload cap; `ee42ea90` TLS/index fixes; `b3ce86d0` local worker limit. Docs/evidence commits trong Git history.

[PR #46](https://github.com/mhiu05/MoodPrint/pull/46), base `mhiu05/feat-refactor`. [CI 42372716790](https://github.com/mhiu05/MoodPrint/actions/runs/42372716790) trên `b3ce86d0`: **success**, offline và integration. Merge sẽ chỉ thực hiện khi final evidence commit qua CI; không merge main.

- **G0 VERIFIED**: P0/local/hosted/history/advisors/S-05/smoke/cleanup/Dashboard evidence đủ.
- **G1 NOT_STARTED**: chưa chứng minh business vertical slice; Phase 1 bắt đầu từ G0 baseline.
- **G2 NOT_STARTED**: chưa freeze integration baseline/tag hay tạo Phase 2/3 worktrees.
- **A-06 BLOCKED, P1**: thiếu cost ceiling O-09; chưa paid live OpenAI evaluation. Model giữ gpt-6-luna; offline SDK compatibility đã kiểm, live model access/identifier chưa xác minh.
- **S-01 wall-clock PARTIALLY_VERIFIED**: actual expiry/renewal path pass; không tuyên bố đã đo retention hơn hai giờ. G0 storage criteria dùng actual expiry và resume trong suite.
- Không còn owner action chặn Phase 0. Browser plugin đọc tab vẫn lỗi; Dashboard prerequisite được owner handoff, không mở Chrome mới hoặc sửa native host.

**Chưa sẵn sàng cho dữ liệu học sinh thật:** safety/privacy/legal/operational gates trong `00` §6 là điều kiện riêng.
