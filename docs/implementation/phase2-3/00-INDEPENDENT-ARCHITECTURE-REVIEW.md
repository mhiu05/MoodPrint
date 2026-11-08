# 00 — Independent Architecture Review (Phase 2 / Phase 3)

> **Trạng thái:** audit lịch sử của Claude; kết quả thực thi PB và các hiệu chỉnh ở `15-PRE-BRANCH-EXECUTION-REPORT.md`. Không dùng nhãn VERIFIED lịch sử làm bằng chứng cho baseline mới. **Ngày audit:** 2026-11-08. **Người audit:** Principal Architect (phiên planning, chỉ đọc).
> **Phạm vi:** đánh giá độc lập baseline Phase 0/1 để quyết định Phase 2 (Knowledge Base, Grok 4.7) và Phase 3 (AI Companion, Claude Opus 5.5) có thể chạy song song rồi tích hợp tự động vào `mhiu05/feat-refactor` hay không.
> **Quy ước nhãn:** `VERIFIED` (đã kiểm chứng trong phiên này) · `REUSABLE` (dùng lại nguyên trạng) · `EXTEND` (mở rộng, không phá) · `NEEDS_FIX` (lỗi thật hoặc khoảng trống chặn kế hoạch) · `BLOCKED` (cần điều kiện bên ngoài) · `DEFER` (cố ý hoãn). Mức ưu tiên P0 = chặn việc rẽ nhánh hoặc chặn merge.
> Sản phẩm **chưa** được duyệt cho học sinh thật. Mọi dữ liệu phát triển, test, demo, eval là dữ liệu tổng hợp (`docs/implementation/00-ARCHITECTURE-DECISIONS.md` §6 vẫn áp dụng).

## 1. Kết luận ngắn

1. **Kiến trúc Phase 0/1 đủ để mang cả hai phase.** Modular monolith, `AuthContext` → `UnitOfWork` → RLS, Agents SDK runtime có approval resume (S-03), memory ba lớp, contract `KnowledgeRetriever` và fixture đều tồn tại và chạy.
2. **Scaffold G2 chưa đủ để hai agent làm song song mà không chạm file đóng băng.** Audit tìm thấy **11 khoảng trống P0** (mục 5, `B-01…B-11`). Ví dụ: CI bỏ qua âm thầm nhánh `feat/knowledge-base`; `frontend/src/services/ports.ts` đóng băng nhưng không có chỗ cắm adapter thật; `IncidentService` từ chối mọi provenance khác `user_entered` nên tool của Agent không thể lưu sự kiện đã xác nhận; pgTAP hard-code số bảng nên bất kỳ migration `ag_*` nào cũng làm gãy test của người khác.
3. **Vì vậy kế hoạch được chia thành ba phần:** Pre-Branch Readiness (do integrator làm trên `mhiu05/feat-refactor`, tạo tag mới `baseline/phase-2-3-start`), hai kế hoạch feature độc lập, và runbook tích hợp tự động.
4. **Kết luận sẵn sàng: `CONDITIONALLY_READY`.** Hai kế hoạch feature và runbook đã đủ chi tiết để triển khai. Điều kiện duy nhất: hoàn thành và xác minh `01-PRE-BRANCH-READINESS-PLAN.md` (PB-01…PB-09) trước khi owner tạo hai worktree.

## 2. Phương pháp và bằng chứng

| Việc | Cách làm | Kết quả |
|---|---|---|
| Git/tag | `git rev-parse`, `git ls-remote --tags origin`, `git rev-list --count` | ✅ VERIFIED. `baseline/phase-1-verified` là tag annotated (`8e0dc922…`) trỏ `763dcdd66ba8dbbfd691ad8541db21062ac06772`, đã push. `HEAD = origin/mhiu05/feat-refactor = 1aec4078f2852720479e183d10c7cc086b6d6a3f` (chỉ thêm commit tài liệu sau tag). `origin/main = 8b329980…` là merge-base, **0 commit** `main` mà nhánh này chưa có. `main` không bị đụng. |
| Test chạy lại trong phiên | `uv run pytest shared/tests scripts/tests/test_ownership.py scripts/db/tests -q` | ✅ **166 passed** (53 + 98 + 15). |
| Test nặng (Docker) | Không chạy lại. Dựa vào `g1-g2-closure-report.md`: `check.py` 265 pass/67 deselect, pgTAP 13 file/194 assertion, integration 67, Vitest 94, Playwright demo 13, real 11 + urgent 1; CI `offline` + `integration` SUCCESS trên `d779a243`. | 🟡 UNVERIFIED trong phiên này, nhưng có bằng chứng CI. Pre-branch gate (PB-09) chạy lại toàn bộ. |
| Hosted | MCP `list_migrations`, `list_extensions` (chỉ đọc) | ✅ 17 migration `f0_*`/`f1_*`, đúng khớp repo. `vector 0.8.2`, `unaccent 1.1`, `pg_trgm 1.6` **đã cài** trong schema `extensions`. |
| Máy dev | `docker info`, `gh api` | Docker engine có **8.17 GB RAM, 12 CPU**. `gh` đăng nhập `mhiu05` với quyền admin. **`mhiu05/feat-refactor` không có branch protection** (HTTP 404) nên không có "required check" do GitHub áp đặt. |
| Checker ownership | Chạy thật trên cây hiện tại với `--base baseline/phase-1-verified` | ✅ hoạt động. Báo `.claude/settings.local.json`, `.cursor/mcp.json`, `.mcp.json` là vi phạm vì chúng là file đã track nhưng owner sửa cục bộ (xem `B-03`). |
| Nghiên cứu ngoài | Voyage docs, pgvector/Supabase docs, OpenAI model page, UNICEF/WHO legal pages | Xem `03` và `04`. Hai nguồn **không đọc được** (HTTP 403): `stopbullying.gov`, `thuvienphapluat.vn` → `BLOCKED` ở mục 6, xử lý bằng task P2-01. |

Không có file nào ngoài `docs/implementation/phase2-3/` bị sửa. Không tạo branch, worktree, tag; không áp migration; không gọi model trả phí.

## 3. Những gì đã được xác minh và dùng lại nguyên trạng

| ID | Hạng mục | Nhãn | Bằng chứng |
|---|---|---|---|
| V-01 | `AuthContext` không chứa JWT, `claims_json` chỉ để `set_config`; UoW `SET LOCAL ROLE authenticated` | REUSABLE | `shared/.../contracts/auth.py`, `backend/app/core/uow.py`, `04` §4, `test_rls_context` |
| V-02 | Dependency boundary `shared ← agent ← app` bằng `.importlinter` (agent cấm import `app`, `fastapi`) | REUSABLE | `.importlinter` |
| V-03 | `KnowledgeRetriever` Protocol, DTO, `KnowledgeRetrieverContract`, `FixtureKnowledgeRetriever` | REUSABLE | `contracts/knowledge.py`, `testing/knowledge_contract.py`; 53 test shared pass |
| V-04 | `CompanionRuntime`: `Runner.run_streamed`, timeout, cancel, budget, usage cộng dồn qua resume, `store=False`, tracing tắt | REUSABLE | `runtime.py`, `test_runtime.py` (309 dòng), S-03 |
| V-05 | `ToolRegistry`: từ chối write không approval, từ chối tham số `user_id`/`owner_id`, wrapper budget, `version()` hash chính sách | REUSABLE | `tools/registry.py` |
| V-06 | Approval qua `app.tool_approvals` + `RunState` serialize **không** có context; resume sau restart process | REUSABLE | S-03, `test_approval_process.py` |
| V-07 | SDK session trong `agent_store` với `schema_translate_map`, `ensure_ascii=False` | REUSABLE | S-02, `memory/session.py` |
| V-08 | Memory: candidate → duyệt → active, hard delete, lexical retrieval không fallback "tất cả" | REUSABLE | `modules/memory/service.py`, `07_memory_rules.sql` |
| V-09 | Dịch vụ cụ thể khớp Protocol: `IncidentService.add_event`, `EvidenceService.open_read_url/add_derivative`, `ActionPlanService.upsert/set_item_status` | REUSABLE | `modules/{incidents,evidence,plans}/service.py` |
| V-10 | `EvidenceService.open_read_url(purpose="evidence_analysis")` ghi `audit_events`; `add_derivative` ghi `evidence_derivatives` tách khỏi bản gốc, kiểm `storage_key` | REUSABLE | `evidence/service.py:290-420` |
| V-11 | Dựng ID stream SSE `v1` (frozen) và `StreamEvent` TS tương ứng | REUSABLE | `contracts/streaming.py`, `http/stream-events.ts` |
| V-12 | `scripts/db/push_hosted.py` kiểm project ref, lịch sử migration, commit sạch, receipt local | REUSABLE (cần mở rộng, `B-11`) | `scripts/db/safety.py` |
| V-13 | Hosted extension `vector`, `unaccent`, `pg_trgm` đã bật; migration `kb_*` **không** phải xin bật extension | REUSABLE | MCP `list_extensions` |
| V-14 | `agent_runs_owner_started(owner_id, started_at desc)` đủ cho tổng hợp token theo ngày/user | REUSABLE | `f0_conversations.sql:45` |
| V-15 | DB cho phép `case_events.provenance IN ('user_entered','ai_extracted','user_confirmed')` | REUSABLE | `f1_cases.sql:42` |
| V-17 | Ranh giới DB/transaction: login `moodprint_api` (NOBYPASSRLS), mỗi transaction `SET LOCAL ROLE authenticated` + claims; không giữ transaction qua lời gọi LLM/Storage; `statement_timeout` của `authenticated` 8 s; `DB_URL` pooler; `knowledge` sẽ truy cập bằng cùng cơ chế không claims | REUSABLE | `04` §4, AD-04, `core/uow.py` |
| V-16 | Mô hình dữ liệu 24 bài Knowledge tĩnh (VN, tự biên soạn) + 4 nguồn trích dẫn trong mock | REUSABLE làm hạt giống corpus | `frontend/src/mocks/data/knowledge.ts`, `sources.ts` |

## 4. Những gì cần mở rộng (không phải lỗi)

| ID | Hạng mục | Nhãn | Ghi chú |
|---|---|---|---|
| E-01 | Registry chỉ có `get_server_time` → bộ tool đầy đủ | EXTEND | Phase 3, `06` |
| E-02 | Prompt `companion_v1.md` (10 dòng) → prompt có version, theo tuổi, quy tắc citation | EXTEND | Phase 3 |
| E-03 | `MemoryContextBuilder` chưa nạp domain (case) | EXTEND | Phase 3, P3-08 |
| E-04 | `OpenAIResponsesCompactionSession` đã bọc nhưng chưa bật | EXTEND | Phase 3, P3-08 |
| E-05 | Adapter frontend `chat/analysis/roleplay/knowledge` đang là mô phỏng/local | EXTEND | Sau CC-001 |
| E-06 | `ContextBundle` có phần `knowledge` nhưng không auto-inject | EXTEND | Giữ tool-only (AD-P23-12) |
| E-07 | `agent/evals/` mới có khung + rubric R-01…R-08 | EXTEND | Phase 3 |

## 5. Lỗi thật và khoảng trống chặn kế hoạch (`NEEDS_FIX`)

Mỗi mục ghi bằng chứng, hậu quả nếu bỏ qua, và nơi xử lý. **B-01…B-11 chặn việc rẽ nhánh (P0).** B-12 trở đi được sửa trong feature branch tương ứng.

| ID | Mô tả | Bằng chứng | Hậu quả nếu bỏ qua | Xử lý |
|---|---|---|---|---|
| **B-01** | CI chỉ chạy ownership cho `feat/knowledge-ingestion-rag`/`feat/agent-companion`; `case` không có nhánh mặc định | `.github/workflows/ci.yml:25-31`; `.githooks/pre-commit:4-7` | Branch `feat/knowledge-base` **xanh giả**: bước ownership không chạy. Hook cũng bỏ qua. | PB-06 |
| **B-02** | Với `pull_request`, `actions/checkout` mặc định checkout **merge commit** với base; `check_ownership.py` so với tag nên mọi commit mới của `mhiu05/feat-refactor` bị tính vào feature. Sau khi merge compat tag, `--base` cũ cũng sai. | `ci.yml`, `check_ownership.py:212-227` | Dương tính giả hoặc âm tính giả khi target tiến lên. | PB-06 (checkout đúng `head.sha`, phân giải base theo tag tổ tiên gần nhất) |
| **B-03** | `.claude/settings.local.json`, `.cursor/mcp.json`, `.mcp.json` là file đã track mà owner sửa cục bộ; checker tính thay đổi chưa commit | Chạy checker: 3 vi phạm | Hook chặn mọi commit của agent trong worktree có cấu hình cục bộ | PB-06 (`local_overrides`) |
| **B-04** | Allow-list thiếu: `backend/tests/**`, `frontend/e2e/**`, router/module mới (`analyses`, `roleplay`), test hiện có thuộc Phase 3 | `ownership.yaml` | Mỗi phase **không thể** thêm test backend/E2E hợp lệ nếu không vi phạm ownership; hoặc ép sửa file chung | PB-06, `11` |
| **B-05** | `ports.ts` (🔒): `SimulatedPort` có literal `simulated: true`; `Services.knowledgeCatalog.list()` đồng bộ; `composition/*.ts` xuất **giá trị tĩnh**, không nhận `ApiClient`; `ApiClient` chỉ trả JSON, không có đường stream | `frontend/src/services/{ports,composition,http/client}.ts` | Phase 2 và 3 **không thể** viết adapter thật mà không sửa file đóng băng → vi phạm ngay | PB-02 (CC-001) |
| **B-06** | `main.py` dựng `CompanionRuntime(cfg, openai_client)` không có registry (mặc định chỉ `get_server_time`); `agent_gateway/wiring.py` hard-code `DeferredDomainServices` + `FixtureKnowledgeRetriever()`; không có `app.state.knowledge`; không có router `analyses`/`roleplay` | `backend/app/main.py:56-61`, `wiring.py:55-84` | Phase 3 phải sửa `main.py` (integrator-only); Phase 2 không có đường nạp retriever thật | PB-03 (CC-002) |
| **B-07** | `IncidentService._save_event` ném `403 fixture_not_allowed` với mọi provenance khác `user_entered` | `incidents/service.py:359-366` | Tool `save_confirmed_event` **không thể** lưu sự kiện do AI đề xuất đã được người dùng xác nhận với provenance trung thực; hoặc phải nói dối là `user_entered` | PB-04 (CC-003) |
| **B-08** | pgTAP: `00_rls_coverage.sql` đòi đúng **22** bảng `app` và **2** bảng `agent_store`, chỉ duyệt RLS cho `app`,`agent_store` (**không** `knowledge`); `05_grants.sql` hard-code danh sách schema | `supabase/tests/00_*.sql:7-8`, `05_grants.sql:5` | Mọi migration `ag_*` làm test 00 đỏ; schema `knowledge` **không được kiểm RLS** dù IT-07 yêu cầu | PB-05 (CC-004) |
| **B-09** | Harness E2E dùng cổng cố định: Vite `5178`, API `8008`, mail `54324`; `playwright.config.ts` mặc định `5178`; `responsive-real.spec.ts:66` khẳng định nhãn `AI mô phỏng` ở workspace thật | `scripts/e2e_stack.py:30-31,157-161`, `frontend/e2e/responsive-real.spec.ts:66` | Hai agent **không** chạy E2E real song song được trên một máy; Phase 3 làm đỏ test của người khác khi bật chat thật | PB-07 (CC-005) |
| **B-10** | `uv sync --all-packages --locked` **không** cài extras; `backend` không phụ thuộc extras; `knowledge = []`, `companion = []` | `ci.yml`, `agent/pyproject.toml` | Import thư viện trong extras làm CI offline đỏ; `uv.lock` xung đột liên tục | PB-08 (CC-007) |
| **B-11** | `push_hosted.py` chỉ nhận receipt `phase0`/`phase1`; không có `--include-all`; `check_history` lập `dict` theo version nên **hai migration trùng timestamp che nhau âm thầm** | `scripts/db/push_hosted.py:56-62`, `safety.py:check_history` | Không thể áp `kb_*`/`ag_*` lên hosted theo AD-19; va chạm timestamp giữa hai branch không bị phát hiện | PB-04 (CC-008 công cụ migration hosted); INT-08 (áp dụng) |
| B-12 | `produce()` không lưu citation vào `app.messages.citations` (`TurnResult` hoàn tất không truyền citations); nhánh replay trả `citations: []` | `agent_gateway/sse.py:70-85`, `api/v1/conversations.py:154-166` | Reload làm mất citation; replay `clientMessageId` trả câu trả lời không nguồn | P3-04 |
| B-13 | `agent/ingestion/` không nằm trong wheel `moodprint_agent` (hatch chỉ gói `src/moodprint_agent`) nên `import ingestion` không chạy từ repo root | `agent/pyproject.toml` | CLI ingest không import được, pyright strict không phủ | P2-03: logic đặt trong `moodprint_agent.knowledge.ingest`, `agent/ingestion/` chỉ chứa dữ liệu corpus + shim |
| B-14 | `create_retriever(cfg: AppConfig)` (chữ ký 🔒) không nhận engine hoặc khóa Voyage; agent không được đọc secret | `knowledge/__init__.py`, `.importlinter` | Retriever thật không có đường nhận kết nối | PB-03 (nạp qua `app.state.knowledge` + factory phía backend), P2-08 |
| B-15 | `KnowledgeRetrieverContract` yêu cầu corpus tổng hợp có nội dung `vi`, VN, tuổi 11–13, topic `support`, không có `zz`; adapter thật cần embedder tất định để chạy offline | `knowledge_contract.py` docstring | Adapter thật không qua contract test trong CI (không có khóa Voyage) | P2-08 (`HashingEmbedder` tất định + seed corpus tổng hợp) |
| B-16 | `KnowledgeFilters.age_band` là `"11-13"` (gạch ngang) còn frontend dùng `"11–13"` (gạch nối dài) | `contracts/base.py` vs `types/index.ts` | Lọc tuổi sai âm thầm ở Knowledge Hub | P2-11/12 (mapper + test) |

### 5.1 Những điều **không** phải lỗi (tránh sửa thừa)

- `DeferredDomainServices` trong `wiring.py` là placeholder có chủ ý của Phase 0; thay bằng dịch vụ thật là việc của Phase 3 (không phải sửa lỗi).
- Contract `IncidentService` Protocol chỉ có `list_cases/get_case/add_event` nên tool **không** gọi được `update_event`. Chấp nhận. Sửa sự kiện đã có là hành động của người dùng trên UI. Mở rộng Protocol chỉ khi eval chứng minh cần (DEFER).
- `output_type=None` ở `build_companion`: quyết định định dạng đầu ra có cấu trúc là spike S-06 của Phase 3, không phải lỗi.
- Hai WARN performance advisor `multiple_permissive_policies` đã được chấp nhận ở G1.

## 6. Điều bị chặn bởi yếu tố ngoài (`BLOCKED`)

| ID | Điều kiện | Ảnh hưởng | Cách mở khóa |
|---|---|---|---|
| BL-01 | `stopbullying.gov` và `thuvienphapluat.vn` trả **HTTP 403** cho công cụ fetch của phiên này; chưa xác minh được nội dung, ngày, hiệu lực pháp lý, giấy phép tái sử dụng | Hai nhóm nguồn quan trọng chưa được xếp hạng chắc chắn | P2-01: agent Phase 2 xác minh bằng trình duyệt thật (Claude in Chrome) hoặc `vbpl.vn`/Công báo; cho tới khi `verified_at` có giá trị, nguồn ở trạng thái `unverified` và **không** vào corpus đã publish |
| BL-02 | UNICEF: "UNICEF reserves all copyrights" và dịch/tái bản cần giấy phép viết; WHO: CC BY-NC-SA 3.0 IGO (phi thương mại, share-alike, phạm vi "publications") | Không được nhúng nguyên văn UNICEF; WHO chỉ khi owner xác nhận dự án phi thương mại và chấp nhận SA | Mặc định: UNICEF/WHO ở hạng `reference_only` (siêu dữ liệu + bài tóm tắt tự biên soạn có trích dẫn). Quyết định cấp phép → owner (O-05) |
| BL-03 | Đã xác minh lại ngày 2026-11-08: [model](https://developers.openai.com/api/docs/models/gpt-6-luna) và [pricing](https://developers.openai.com/api/docs/pricing) công bố Standard short-context ≤272K: input $0.10, cached input $0.01, output $0.50 / 1M token. Chưa có ngân sách owner | Giá không phải quyền chi tiền; quyền truy cập tài khoản chưa được gọi thử trong PB | Owner đặt max_usd, max_tokens_total, max_calls, scope và expiry; P3-00 kiểm live có giới hạn sau đó. Kiểm lại giá/tier/long context trước mỗi run |
| BL-04 | Chưa có `OPENAI_API_KEY`/`VOYAGE_API_KEY` trong worktree feature | Không chạy được live smoke, eval, embedding thật | Owner cấp khóa (O-04) |
| BL-05 | Docker Desktop chỉ 8.17 GB RAM | Không chạy được 3 stack Supabase đầy đủ cùng lúc | PB-07 thêm `--lite` (tắt Studio); khuyến nghị tăng RAM Docker ≥ 12 GB; tối đa 2 stack chạy đồng thời |

## 7. Quyết định kiến trúc mới (`AD-P23-xx`)

Bổ sung cho `00-ARCHITECTURE-DECISIONS.md` (AD-01…AD-20). Khi mâu thuẫn, tài liệu này thắng đối với Phase 2/3.

| ID | Quyết định | Lý do | Nơi thực thi |
|---|---|---|---|
| AD-P23-01 | Tag mới `baseline/phase-2-3-start` do integrator tạo sau Pre-Branch Readiness. Cả hai branch rẽ **đúng** từ commit này. Tag cũ `baseline/phase-1-verified` giữ nguyên. | Không thể sửa tag cũ; scaffold và policy mới phải nằm trong baseline mà checker đọc | 01 |
| AD-P23-02 | Ownership policy v2: thêm bản đồ `branches`, `local_overrides`, mở rộng allow-list (test, e2e, router, module). CI và hook gọi **script Python có test** (`scripts/ci_ownership.py`), không dùng `case` trong YAML. Base = tag `baseline/phase-2-3-start*` gần nhất là tổ tiên của HEAD. | B-01…B-04 | 01, 11 |
| AD-P23-03 | Frontend: thêm hai slot cộng thêm vào `Services` (`knowledgeSearch`, `companion`), composition là **factory** nhận `ApiClient` có `stream()`; kiểu cụ thể nằm trong file do phase sở hữu | B-05 | 01 (CC-001) |
| AD-P23-04 | Retriever thật được nạp qua `app.state.knowledge`, dựng bởi `backend/app/modules/knowledge/factory.py` (Phase 2 sở hữu). `create_retriever(cfg)` giữ nguyên chữ ký và vẫn chỉ trả fixture. Agent không đọc secret. | B-06, B-14 | 01, 02 |
| AD-P23-05 | Gọi Voyage bằng `httpx` REST (`/v1/embeddings`), không dùng SDK `voyageai`. Model mặc định `voyage-4`, 1024 chiều (`vector(1024)`), `input_type` `document`/`query`. Rerank mặc định **tắt**, chỉ bật nếu benchmark chứng minh. | Ít phụ thuộc, kiểm soát timeout/retry, tránh churn `uv.lock` | 04 |
| AD-P23-06 | Corpus theo hạng giấy phép: `open_reuse`, `authored`, `reference_only`, `unverified`. Chỉ `open_reuse` và `authored` được publish dưới dạng chunk. | BL-01, BL-02 | 03 |
| AD-P23-07 | Corpus **bất biến theo phiên bản**; chỉ một phiên bản `published`; publish/rollback là đổi con trỏ trong một transaction; `RetrievalScope.corpus_version` ghim phiên bản. | Tái lập eval, rollback an toàn | 03 |
| AD-P23-08 | Truy hồi lai: nhánh vector + nhánh từ khóa không dấu, hợp nhất RRF (`k` mặc định 50, chọn theo dev split). Ngưỡng `no_results` hiệu chỉnh trên dev split, khóa trên test split. | Vector thuần luôn trả "gần nhất"; cần ngưỡng để thỏa `no_results` | 04 |
| AD-P23-09 | Câu truy vấn của học sinh là dữ liệu nhạy cảm gửi cho Voyage: che email/điện thoại/URL, cắt 300 ký tự, **không log nguyên văn**, đề xuất owner opt-out huấn luyện của Voyage. | G-04 | 04, O-06 |
| AD-P23-10 | Đường ghi của Agent: tool `propose_*` lưu bản đề xuất bất biến vào `app.agent_proposals`; tool `save_*` chỉ nhận `proposal_id`, có `needs_approval=True`; ghi qua dịch vụ hiện có (sự kiện qua `IncidentService.add_confirmed_event`, CC-003). | Người dùng duyệt đúng nội dung đã xem; model không sửa payload sau khi duyệt | 06 |
| AD-P23-11 | Phân tích ảnh bằng **scoped multimodal service/tool**, không Agent riêng, không session/tool registry độc lập, `store=False`, sau consent rõ ràng; ảnh được tải về bằng URL ký có kiểm host, giải mã lại, xóa EXIF, tối đa 2048 px; kết quả là derivative `ai_analysis` bất biến; chỉnh sửa của người dùng nằm ở `user_edited_text`. | Ảnh không vào session replay; giữ nguyên bản gốc; không thêm independent Agent state | 06 |
| AD-P23-12 | Citation đi qua **sổ cái citation theo run**: `knowledge_search` trả mã `S1..Sn`; chỉ marker `[S#]` khớp sổ cái mới thành `SourceCitation`; marker lạ bị gỡ; không có kết quả thì không có citation. Citation được lưu vào `app.messages.citations` và phát lại khi replay. | B-12, IT-04 | 06 |
| AD-P23-13 | Đầu ra có cấu trúc (`urgency`, tách fact/inference) quyết định bằng spike S-06 với tiêu chí đo được; mặc định dự phòng: stream text + tool đánh giá cuối lượt. | Giữ streaming mượt | 05 |
| AD-P23-14 | Kiểm tra khẩn cấp tất định (tiếng Việt có/không dấu) chạy **trước và sau** model; luôn gắn khối hỗ trợ khẩn cấp (111, `/support/urgent`) khi trúng, bất kể câu trả lời của model. | An toàn không phụ thuộc model | 05 |
| AD-P23-15 | Roleplay là **chế độ** của một Companion duy nhất, không phải agent người dùng nhìn thấy: dùng cùng endpoint tin nhắn, prompt đối tác riêng, bước coach tạo phản hồi có cấu trúc. | Giữ "một AI Companion" | 05 |
| AD-P23-16 | **Không** tạo embedding cho ký ức cá nhân ở giai đoạn này (quyết định owner O-07, mặc định "không"). Ký ức chọn lọc bằng lexical + ý định + độ mới. | AD-10 | 06 |
| AD-P23-17 | Eval: assertion tất định bằng code + rubric do coding agent tự chấm (AD-20); harness từ chối chạy live nếu không có file ngân sách; kịch bản live ngẫu nhiên chạy 3 lần với chính sách pass công bố trước. | BL-03, trung thực | 07 |
| AD-P23-18 | Tích hợp: tạo `integration/phase-2-3` từ tag baseline, merge Phase 2, merge Phase 3, rồi hòa giải tip hiện tại của target; áp hosted **một lần** cho cả hai bộ migration; merge PR bằng `--merge --match-head-commit`; tag chỉ sau khi xác minh post-merge trên bản sao sạch của target. | Không viết lại lịch sử | 10 |
| AD-P23-19 | Hạ tầng song song: Supabase offset `+100` (Phase 2), `+200` (Phase 3), `+300` (integrator); cổng ứng dụng theo cùng offset; tối đa 2 stack cùng lúc; `--lite` tắt Studio. | S-04, BL-05 | 01, 08 |
| AD-P23-20 | Tên migration dùng timestamp thật; test chặn trùng version; integrator đổi tên (chưa áp hosted nên an toàn) khi va chạm. | B-11 | 01, 08 |

## 8. Tính đúng đắn của kết luận trước khi viết kế hoạch

| Câu hỏi | Trả lời |
|---|---|
| Phase 0/1 có hỗ trợ cả hai phase không? | Có, sau PB-01…PB-09. Không cần đổi kiến trúc, không cần dịch vụ mới (không Redis, Celery, Kafka, Kubernetes). |
| Hai phase có chạm file chung không? | Chỉ qua: `config.py` (hai class tách), `.env.example` (hai khối), `agent/pyproject.toml` (hai extra), các file generated, và chữ ký `create_retriever`. Tất cả có cơ chế kiểm tự động. |
| Có khả năng migration xung đột âm thầm không? | Có nguy cơ: trùng timestamp (B-11) và test pgTAP đếm cứng (B-08). Cả hai được vá trước khi rẽ nhánh. |
| Agent phát triển được với fixture retriever không? | Có. `knowledge_search` chỉ phụ thuộc Protocol; test luôn truyền `KnowledgeConfig(retriever="fixture")` tường minh (R-P3-03). |
| Có đo được chất lượng retrieval và Agent không? | Có: `04` (benchmark 180 truy vấn, 8 chỉ số, ngưỡng đề xuất) và `07` (bộ assertion tất định + rubric R-01…R-08). Ngưỡng là **mục tiêu đề xuất**, chưa có số đo. |
| Có yêu cầu live model không? | Có: P3-00 chạy smoke live sớm, P3-17 eval live, INT-05/06/08 chạy lại với retriever thật. Tất cả bị chặn bởi file ngân sách. |
| Có đường hợp nhất tự động an toàn không? | Có, `10`. Điều kiện nghiêm ngặt, không merge `main`, không force push, hosted áp một lần có dry-run và advisor. |
