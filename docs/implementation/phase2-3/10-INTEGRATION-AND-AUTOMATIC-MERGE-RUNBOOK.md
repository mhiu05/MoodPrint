# 10 — Integration and Automatic Merge Runbook

> Bàn giao thực thi đủ bước: `14-INTEGRATION-AGENT-EXECUTION-HANDOFF.md`. Runbook này vẫn là nguồn lệnh. Không chạy integration feature trong phiên PB.

> **Người thực hiện:** Integration Agent, tự chủ, sau khi cả hai branch feature hoàn tất. Shell: PowerShell trên Windows (lệnh `uv`, `git`, `gh`, `npm`).
> **Đích:** `integration/phase-2-3` → `mhiu05/feat-refactor`. **Không bao giờ merge vào `main`.** Không `push --force`, không `reset` lịch sử đã chia sẻ, không `rebase` nhánh đã đẩy, không bỏ qua hook (`--no-verify`), không bypass branch protection nếu về sau có.
> Runbook này **không** được thực thi trong phiên planning. Khi thực thi, mọi bước ghi kết quả vào `docs/implementation/reports/integration-report.md` (cấu trúc ở §14). Quy tắc báo cáo: không nói "xong" nếu chưa chạy; ghi lệnh, mã thoát, SHA.

## 1. Nguyên tắc vận hành

1. **Không có gate "xanh giả":** CI xanh không đủ. Mọi gate ở §2, §6–§9 phải có bằng chứng riêng.
2. **Bất biến SHA:** sau khi áp hosted (INT-08), không thêm commit mã. Nếu cần sửa ⇒ quay lại bước bị ảnh hưởng, chạy lại tới hosted.
3. **Không che thất bại:** kịch bản fail được giữ trong báo cáo; không xóa/nới test; không `skip`.
4. **Hosted chỉ khi gate local xanh,** một lần cho cả hai bộ migration, forward-only. Không reset hosted. Không đụng database MoodPrint cũ. Không dùng MCP `apply_migration` cho DDL (AD-06/AD-19).
5. **Secret:** không in `.env`; không ghi khóa vào log/báo cáo/PR; không chụp trang API key.
6. **Mã thoát và dừng:** bất kỳ P0 `BLOCKED` ⇒ không tuyên bố `VERIFIED`; ghi blocker chính xác; giữ trạng thái khôi phục được.
7. **Không hỏi owner cho thao tác thường lệ,** nhưng **dừng** và báo owner khi: thiếu quyền/khóa/ngân sách, branch protection bắt buộc phê duyệt, thay đổi nghĩa sản phẩm, hoặc cần chi tiêu vượt trần.

## 2. Điều kiện tiên quyết (INT-00)

Chạy `scripts/integration/preflight.py` (tạo ở INT-00) hoặc thực hiện thủ công, và dán đầu ra tóm tắt (không bí mật) vào báo cáo.

```powershell
git fetch --all --tags --prune
$P2 = (git rev-parse origin/feat/knowledge-base);  $P3 = (git rev-parse origin/feat/agent-companion)
$BASE = (git rev-parse 'baseline/phase-2-3-start^{commit}')
git merge-base --is-ancestor $BASE $P2 ; if ($LASTEXITCODE) { throw "P2 không rẽ từ baseline" }
git merge-base --is-ancestor $BASE $P3 ; if ($LASTEXITCODE) { throw "P3 không rẽ từ baseline" }
gh run list --commit $P2 --json name,conclusion,status,url   # offline + integration phải SUCCESS
gh run list --commit $P3 --json name,conclusion,status,url
uv run python scripts/ci_ownership.py --branch feat/knowledge-base --head $P2   # exit 0
uv run python scripts/ci_ownership.py --branch feat/agent-companion --head $P3  # exit 0
git rev-parse origin/main                       # phải bằng 8b329980af4038f4c2a565a6472fd01472fbdfef
git rev-parse origin/mhiu05/feat-refactor       # ghi lại; so với tip dự kiến
gh api repos/mhiu05/MoodPrint/branches/mhiu05%2Ffeat-refactor/protection  # 404 = không bảo vệ; nếu có ⇒ đọc quy tắc
```

### 2.1 Checklist điều kiện

| Nhóm | Điều kiện (tất cả bắt buộc) | Bằng chứng |
|---|---|---|
| **Phase 2** | Hoàn thành, **đã commit và push**; test cục bộ xanh; ingest test xanh; retrieval contract test xanh; benchmark đạt ngưỡng đã chấp nhận (hoặc giải trình trung thực được `02` §6 D2-07 chấp nhận); RLS test xanh; ownership xanh; CI xanh trên SHA cuối; `phase-2-report.md` đã commit | báo cáo + run URL |
| **Phase 3** | Hoàn thành, đã commit và push; test cục bộ, agent, memory, approval xanh; **xác minh live model** đạt phạm vi P0 trong ngân sách (P3-00, eval live); frontend E2E xanh; ownership xanh; CI xanh; `phase-3-report.md` đã commit | báo cáo + run URL |
| **Cả hai** | Cùng rẽ từ `baseline/phase-2-3-start`; không sửa vùng đóng băng; không migration hosted đã chạy bởi feature; không secret trong git (`gitleaks`-tương đương: grep mẫu + `check:boundaries`) | `git diff --stat`, quét |
| **Môi trường** | Cây làm việc sạch (trừ 3 file cấu hình cục bộ), `.env` hosted có mặt, `OPENAI_API_KEY` + `VOYAGE_API_KEY` có, `.local/eval-budget.json` hợp lệ cho scope `integration-eval` và `hosted-smoke`, Docker chạy, hai stack feature đã dừng | kiểm tra không in giá trị |

**Nếu bất kỳ mục P0 bị chặn ⇒ KHÔNG đánh dấu VERIFIED; KHÔNG merge.** Việc "cả hai CI xanh" không phải điều kiện đủ.

## 3. Tạo nhánh integration và merge (INT-01)

```powershell
# 3.1 Tạo từ cơ sở thống nhất (commit của tag), KHÔNG từ tip target
git switch -c integration/phase-2-3 $BASE
git push -u origin integration/phase-2-3

# 3.2 Merge Phase 2 rồi Phase 3, giữ lịch sử, tạo merge commit tường minh
git merge --no-ff -m "merge: feat/knowledge-base ($P2) into integration/phase-2-3" $P2
# giải quyết xung đột (§4), chạy kiểm tra nhanh, commit nếu merge dừng vì xung đột
git merge --no-ff -m "merge: feat/agent-companion ($P3) into integration/phase-2-3" $P3

# 3.3 Hòa giải target đã tiến lên kể từ baseline (nếu có)
$TIP = (git rev-parse origin/mhiu05/feat-refactor)
git merge-base --is-ancestor $TIP HEAD ; if ($LASTEXITCODE) {
  git log --oneline "$BASE..$TIP"            # xem MỌI commit mới; ghi lý do trong báo cáo
  git merge --no-ff -m "merge: origin/mhiu05/feat-refactor ($TIP) into integration/phase-2-3" $TIP
}
git push origin integration/phase-2-3        # đẩy thường, không --force
```

Ghi vào báo cáo: `$BASE`, `$P2`, `$P3`, `$TIP`, SHA ba merge commit.

Sau khi hợp nhất, **trước mọi kiểm tra nặng**:

```powershell
uv sync --all-packages --all-extras --locked
uv run python scripts/check.py
uv run python scripts/export_contract_schemas.py --check
uv run python scripts/export_openapi.py --check
cd frontend; npm ci; npm run gen:api; git diff --exit-code src/services/http/schema.gen.ts; cd ..
```

## 4. Xử lý xung đột

| Tệp | Chiến lược | Kiểm sau |
|---|---|---|
| `uv.lock` | lấy bản bên nào cũng được → `uv lock` → commit | `uv sync --locked --all-extras` |
| `frontend/package-lock.json` | (kỳ vọng không xung đột) nếu có: `npm install --package-lock-only` | `npm ci` |
| `backend/openapi.json`, `frontend/src/services/http/schema.gen.ts` | không hợp nhất tay; sau khi hợp nhất router: `uv run python scripts/export_openapi.py` rồi `npm run gen:api` | `--check` và `git diff --exit-code` |
| `shared/src/moodprint_shared/config.py` | giữ **cả** `KnowledgeConfig` (P2) và `AgentConfig`/`MemoryConfig` (P3); tuyệt đối không xóa trường của bên nào | `shared/tests`, `test_settings`, import-linter |
| `.env.example` | giữ cả khối `knowledge` và `agent`, đúng tiêu đề `# --- … ---` | `scripts/tests/test_ownership.py` (mask) |
| `agent/pyproject.toml` | giữ cả hai extras | `uv lock` |
| `supabase/migrations/*` | không xung đột tên (tiền tố khác nhau); nếu **trùng version** ⇒ §5 | `migration_scope_check`, `migration_order_check` |
| `docs/implementation/reports/*` | hai báo cáo khác tên ⇒ không xung đột | — |
| Mã nguồn hai phase | vùng khác nhau ⇒ hiếm; nếu xung đột ngoài danh sách trên ⇒ **dừng**, đọc cả hai thay đổi, hỏi: có vi phạm ownership không? (nếu có, trả về feature owner) | test toàn bộ |

Cấm: `git checkout --ours/--theirs` hàng loạt, `-X ours/-X theirs`, xóa thay đổi một phase để "xanh". Mỗi xung đột thủ công ghi vào báo cáo (file, quyết định, test chứng minh).

## 5. Hòa giải migration (INT-02, IT-01)

```powershell
$env:MOODPRINT_STACK_NAME = "int"; $env:MOODPRINT_PORT_OFFSET = "300"
uv run python scripts/dev/supabase_worktree.py start --lite
# 5.1 Phạm vi và trùng version
uv run python scripts/dev/migration_scope_check.py --all
uv run pytest scripts/db/tests/test_migration_versions.py -q
Get-ChildItem supabase/migrations | Select-Object -ExpandProperty Name   # đối chiếu với hai báo cáo
# 5.2 Thứ tự thực + kiểm hai thứ tự
uv run python scripts/dev/supabase_worktree.py reset
uv run python scripts/dev/bootstrap_local_db.py --workdir .local/stacks/int
uv run python scripts/dev/supabase_worktree.py test
uv run python scripts/dev/migration_order_check.py          # in VERIFIED order=kb-first / order=ag-first
```

- **Trùng version** (hiếm): đổi tên file của **một** phía (chưa áp hosted nên an toàn) thành timestamp lớn hơn, commit `int: renumber migration <tên> to avoid version collision`, ghi lý do; không đổi nội dung SQL.
- **Chênh với hosted:** hosted cuối cùng là `20261107140312_f1_account_deletion_guard`. Mọi migration mới phải có version lớn hơn ⇒ không cần `--include-all`. Nếu có migration cũ hơn (không dự kiến) ⇒ chỉ dùng `--include-all` khi đã đọc lý do và ghi báo cáo.
- **Sửa lệch:** nếu hai bộ migration tương tác (ví dụ chỉ mục trùng tên) ⇒ thêm `supabase/migrations/<ts>_int_fix_<mô_tả>.sql` tiến-về-phía-trước (không sửa file đã có của feature), có pgTAP, chỉ chứa đối tượng cần sửa.
- **Kết quả bắt buộc:** `db reset` từ trống xanh; cả hai thứ tự xanh; pgTAP xanh gồm `00_rls_coverage` (nhận `knowledge`), `05_grants`, `kb_*`, `ag_*`; `knowledge` không nằm trong `[api] schemas`.
- **Tương thích backend đang chạy:** sau khi migration lên, API/backend bản đang deploy phải vẫn đọc/ghi được cho tới khi bản tích hợp được triển khai. Cột/bảng mới có default hoặc nullable trước; không rename/drop/đổi nghĩa cột mà backend cũ còn dùng. Apply xanh không đủ. Có một lần chạy backend cũ (hoặc contract test của nó) trên schema mới trước hosted apply.
- **History drift:** `push_hosted.py --apply` đọc lại history ngay trước CLI và từ chối nếu lệch receipt. Bước đó không khóa được CLI. Hậu kiểm vẫn bắt buộc và không thay thế lần từ chối trước mutation.
- **Parent attachment:** scope guard từ chối `INHERITS` và `PARTITION OF`. Không dùng inheritance để “thêm bảng” vào `app.cases` hoặc bảng baseline khác.

## 6. Nối retriever thật và kiểm tích hợp (INT-03, INT-05)

```powershell
# 6.1 Chuyển mặc định retriever (vùng integrator): KnowledgeConfig.retriever = "pgvector"
# 6.2 Nạp corpus
uv run python -m moodprint_agent.knowledge.ingest seed-synthetic --target test-env          # tất định (Hashing)
uv run python -m moodprint_agent.knowledge.ingest build  --manifest agent/ingestion/corpus/manifest.toml --out .local/corpus/int-1
uv run python -m moodprint_agent.knowledge.ingest embed  --build .local/corpus/int-1 --embedder voyage --budget-tokens 600000
uv run python -m moodprint_agent.knowledge.ingest store  --build .local/corpus/int-1 --target test-env
uv run python -m moodprint_agent.knowledge.ingest validate --target test-env --version <kb-…>
uv run python -m moodprint_agent.knowledge.ingest publish  --target test-env --version <kb-…>
uv run python -m moodprint_agent.knowledge.ingest verify-citations --target test-env --version <kb-…>
# 6.3 IT-02…05
uv run pytest -m integration agent/tests/integration/knowledge backend/tests/integration/test_p23_knowledge_tool.py -q
# 6.4 IT-09
uv run python agent/evals/knowledge/run.py --split test --config locked --embedder voyage --corpus <kb-…>
uv run python agent/evals/run.py --suite live --retriever real --repeat 3 --budget .local/eval-budget.json
uv run python agent/evals/summarize.py --run <run-id>
```

| IT | Kiểm chứng cụ thể |
|---|---|
| IT-02 | `KnowledgeRetrieverContract` pass với `PgVectorKnowledgeRetriever` trên DB `int` (corpus tổng hợp + `HashingEmbedder`); thêm chạy với Voyage thật trên corpus thật cho `status/ordering/filters` |
| IT-03 | Runtime thật + tool `knowledge_search` + retriever thật: mọi `source_id` trong citation của run ⊂ `select source_id from knowledge.sources`; `chunk_id` ⊂ `knowledge.chunks` của phiên bản đang publish; text trả về khớp DB |
| IT-04 | Câu hỏi ngoài phạm vi (thời tiết, bài tập) ⇒ `no_results` ⇒ `citations == []`, không URL trong nội dung (A-05, A-06); lặp ở chế độ live |
| IT-05 | Bốn lớp lỗi bơm vào retriever thật: DB tắt, embedder 500, embedder treo, truy vấn quá `timeout_s` ⇒ run kết thúc ≤ `timeout + 0.5 s`, `tool.completed ok=false`, `message.completed` không citation, không treo |
| IT-09 | Số liệu benchmark so với Phase 2 (sai khác ≤ 0.03 Recall@5 hoặc có giải thích); eval Companion Q3-01…05 (100%), Q3-10…21 theo `07`; chi tiêu ≤ trần; rubric do integrator chấm lại R-01/02/06/08 |

### 6.5 Hồi quy đầy đủ, RLS, ownership (INT-04, IT-06…IT-08, IT-18)

```powershell
uv run python scripts/verify_phase23.py          # tuần tự 12 checkpoint; ghi .local/phase23-gate.json; log ở .local/verification/
uv run python scripts/ci_ownership.py --branch feat/knowledge-base   --head $P2    # IT-08, mỗi branch so với baseline của nó
uv run python scripts/ci_ownership.py --branch feat/agent-companion  --head $P3
```

`verify_phase23.py` (12 checkpoint, mỗi cái ghi `command`, `returncode`, `log`): (1) `verify_phase0.py --regression`; (2) `verify_phase1.py`; (3) `check.py`; (4) `supabase test db`; (5) `pytest -m integration`; (6) Vitest + `build` + `check:boundaries`; (7) E2E `demo`; (8) E2E `real --agent scripted`; (9) `migration_order_check.py`; (10) `export_contract_schemas --check`, `export_openapi --check`, `gen:api` không drift; (11) `eval --suite deterministic`; (12) kiểm "số test không giảm": đếm test từng tầng so với `baseline` + `phase-2-report` + `phase-3-report` (265/67, pgTAP ≥ 194, integration 67, Vitest 94, demo 13, real 11+1 là **sàn**). Receipt chỉ hợp lệ nếu `commit == HEAD` và cây sạch. `IT-07`: pgTAP `kb_*`, `ag_*` + ma trận cô lập API (`test_phase3_isolation_matrix`, `test_knowledge_*`) + `00/05/14`. Không `skip`, không giảm assertion; so sánh `pytest --collect-only -q` trước/sau để phát hiện test biến mất.

## 7. Hành trình full-stack (INT-06, IT-10…IT-18)

Chạy hai chế độ trên stack `int`. `scripted`: `ScriptedModel` + retriever thật (Hashing hoặc Voyage) — xác định, bắt buộc xanh, chạy trong CI. `live`: `gpt-6-luna` + Voyage thật, n = 3 (chính sách `07` §5.4).

```powershell
uv run python scripts/e2e_stack.py --run --project real --agent scripted --grep "integration-vertical"
uv run python scripts/e2e_stack.py --run --project real --agent live --grep "integration-vertical-live"   # cần ngân sách
uv run python scripts/e2e_stack.py --run --project demo
```

| # | Bước | Kiểm chứng (tự động) |
|---|---|---|
| 1 | User tổng hợp A xác thực | JWT thật từ local Auth |
| 2 | Bắt đầu hội thoại AI | `POST /v1/conversations` 200; conversation thuộc A |
| 3 | Hỏi câu liên quan bắt nạt | stream `v1` có `message.delta` |
| 4 | Companion dùng KB thật | `tool.started knowledge_search`; DB `agent_runs.tool_call_count ≥ 1` |
| 5 | Citation hợp lệ | A-04: mọi citation ∈ `knowledge.sources/chunks` |
| 6 | Thảo luận sự việc tổng hợp | tin nhắn lưu trong `app.messages` |
| 7 | Lấy ngữ cảnh hồ sơ được phép | `get_case_context` của chính A |
| 8 | (tùy chọn) tải bằng chứng PNG tổng hợp | upload TUS/signed như E2E hiện có |
| 9 | Phân tích trong phạm vi đã duyệt | consent/approval; A-26; derivative `ai_analysis` |
| 10 | Agent đề xuất cập nhật sự việc | `agent_proposals` `proposed`; `ProposalCard` hiển thị |
| 11 | **Chưa ghi trước xác nhận** | A-01: đếm `case_events` không đổi; không `POST` ghi |
| 12 | Người dùng duyệt | `approve` ⇒ SSE tiếp tục |
| 13 | Cập nhật qua service backend | một dòng `case_events` `provenance=user_confirmed`; audit |
| 14 | Agent đề xuất kế hoạch | `agent_proposals(kind=action_plan)` |
| 15 | Người dùng duyệt | `upsert` |
| 16 | Kế hoạch sống sót reload | `GET /v1/cases/{id}/plan`; UI sau reload |
| 17 | Ký ức theo đồng ý | candidate → duyệt → conversation mới dùng; xóa ⇒ không dùng |
| 18 | User B không thấy dữ liệu A | 404 mọi tài nguyên; không rò trong stream |
| 19 | Workspace demo nguyên vẹn | 13 test demo xanh; không trộn dữ liệu |

Cấm thay dữ liệu mock khi dịch vụ thật lỗi. Kịch bản live ghi lại cả ba lần; thất bại bị giữ.

## 8. Rà soát bảo mật (INT-07)

| Hạng mục | Cách kiểm | Kết quả cần |
|---|---|---|
| Secret | grep mẫu (`sk-`, `pa-`, `sb_secret_`, `eyJhbGci…`) trên cây git, bundle `frontend/dist`, log test; `check:boundaries` | 0 |
| Log nội dung | canary `ZZ-CANARY-<uuid>` trong tin nhắn, truy vấn tri thức, ghi chú hồ sơ, ký ức, văn bản ảnh; quét mọi log và `agent_runs` | 0 xuất hiện |
| IDOR | ma trận route × user B (Phase 1 + Phase 3 + `knowledge`) | 100% 404/401/403 đúng |
| RLS/grant | pgTAP; `anon` không đọc `knowledge` và bảng `ag_*`; `authenticated` không ghi `knowledge` | xanh |
| Ghi không duyệt | A-01/A-02 trên toàn bộ tool ghi | 100% |
| SSRF | fetcher bằng chứng: host lạ, redirect, IP riêng | từ chối |
| Injection | `injection` suite + chunk bẫy + ảnh chữ chỉ dẫn | A-14, A-15, A-05 100% |
| XSS | citation/tin nhắn chứa HTML/`javascript:` | render văn bản, URL được lọc `https` |
| Quota/Rate | trần ngày, giờ, search/phút | 429 đúng, không gọi model |
| Phụ thuộc | giấy phép (không AGPL), `uv.lock`/`npm audit --omit=dev` mức High+ | báo cáo |
| Advisors hosted | `get_advisors` security/performance sau apply | 0 lint security; WARN performance giải trình |

**Độ nghiêm trọng.** *Critical:* rò dữ liệu giữa người dùng; truy cập/ghi không xác thực; ghi dữ liệu người dùng không có approval; lộ secret; SSRF vào mạng nội bộ; gửi dữ liệu học sinh tới bên thứ ba ngoài luồng đã duyệt. *High:* chặn lách approval có điều kiện; log nội dung nhạy cảm; thiếu RLS. *Medium/Low:* còn lại. `CRITICAL_SECURITY_FINDINGS = 0` là điều kiện cứng; High phải sửa hoặc owner chấp nhận bằng văn bản.

**Chi phí & độ trễ:** thu từ `usage.json`, `agent_runs`, `ingestion_runs`, đối chiếu đơn giá owner cung cấp và trần; ghi TTFT/toàn câu/analysis và p95; so với `07` §5.3.

## 9. Xác minh Hosted Supabase (INT-08)

Dự án: **`db-school-violence`, ref `xhlshihobyxrgfqrdafh`**. Chỉ Integration Agent. Chỉ sau khi `verify_phase23.py` xanh trên HEAD, cây sạch, và `.local/phase23-gate.json` khớp HEAD.

```powershell
# 9.1 Xác nhận định danh
# MCP school-violence-supabase: get_project_url  ==  https://xhlshihobyxrgfqrdafh.supabase.co
# push_hosted.py tự kiểm host API + DB theo PROJECT_REF (validate_hosted_target)
# 9.2 Lịch sử migration
# MCP list_migrations  → phải đúng 17 bản f0/f1 (đến 20261107140312_f1_account_deletion_guard) trước khi áp
git status --porcelain                                    # phải rỗng ngoài 3 file cấu hình cục bộ
# 9.3 Dry-run
uv run python scripts/db/push_hosted.py --dry-run         # liệt kê pending; so với:
git diff --name-only "$BASE..HEAD" -- supabase/migrations # phải khớp danh sách kb_ + ag_ (+ int_fix_)
# 9.4 Xung đột timestamp/thứ tự: mọi pending version > 20261107140312; không trùng version
# 9.5 Áp dụng forward-only
uv run python scripts/db/push_hosted.py --apply
# MCP list_migrations: có thêm đúng các bản kb_/ag_; dry-run lại → "no pending"
uv run python scripts/db/push_hosted.py --dry-run
# 9.6 Advisors
# MCP get_advisors type=security  → 0 lint;  type=performance → phân loại
# 9.7 Nạp corpus lên hosted (khóa Voyage; ngân sách)
uv run python scripts/db/publish_corpus.py --build .local/corpus/int-1 --apply     # tạo phiên bản, validate, publish; refuse nếu project ref lệch
# 9.8 Smoke API tổng hợp
uv run python scripts/smoke_hosted.py --phase 23
# 9.9 Smoke UI hosted (Claude in Chrome / cửa sổ tách biệt): đăng nhập user tổng hợp, tìm tri thức, hội thoại có citation, duyệt một mốc, đăng xuất, user B
# 9.10 Dọn dữ liệu
# xóa user Auth tổng hợp (Admin API) + object Storage; đếm bằng MCP execute_sql (SELECT) → 0 user smoke, 0 profile, 0 conversation, 0 case, 0 evidence, 0 proposal, 0 analysis, 0 roleplay
```

Quy tắc: không reset hosted; không DDL qua MCP; không `--include-all` trừ khi có lý do ghi báo cáo; không thay đổi cấu hình Auth/Storage/billing. Nếu thiếu kết nối/quyền/ngân sách ⇒ ghi `BLOCKED` chi tiết, **không** tuyên bố hosted VERIFIED, **không** merge.

`smoke_hosted.py --phase 23` (mở rộng, 1 file integrator): (1) readiness; (2) tạo user A, B bằng Admin API (`email_confirm=true`, `@example.test`); (3) A: `GET /v1/knowledge/search` ⇒ citation ⊂ corpus hosted; (4) A: hội thoại 1 lượt `gpt-6-luna` có tool tri thức (ngân sách `hosted-smoke`); (5) A: phân tích PNG tổng hợp 1 lần; (6) A: đề xuất + duyệt một mốc; (7) B: 404 trên mọi tài nguyên A; (8) dọn dẹp và in số đếm 0.

## 10. Điều kiện và thao tác merge tự động (INT-09)

**Điều kiện (tất cả):**

```text
PHASE_2 = VERIFIED        PHASE_3 = VERIFIED        G-INTEGRATION = VERIFIED
REQUIRED_CI = SUCCESS     CRITICAL_SECURITY_FINDINGS = 0
```

Các kiểm tra cụ thể:

```powershell
git push origin integration/phase-2-3
$SHA = (git rev-parse HEAD)
gh pr create --base mhiu05/feat-refactor --head integration/phase-2-3 `
  --title "Integrate Phase 2 (Knowledge Base) and Phase 3 (AI Companion)" `
  --body-file docs/implementation/reports/integration-report.md
$PR = (gh pr view integration/phase-2-3 --json number --jq .number)
gh pr view $PR --json headRefOid,mergeable,mergeStateStatus,reviewDecision,statusCheckRollup
```

| # | Kiểm | Điều kiện |
|---|---|---|
| 1 | SHA mới nhất của integration | `headRefOid == $SHA` và `$SHA` là SHA đã chạy `verify_phase23.py` + hosted |
| 2 | Required checks | `statusCheckRollup`: mọi job của workflow "Foundation" (`offline`, `integration`) `conclusion == SUCCESS` trên `$SHA` |
| 3 | Không xung đột | `mergeable == MERGEABLE`, `mergeStateStatus == CLEAN` |
| 4 | Không phê duyệt còn treo | `reviewDecision` rỗng/`APPROVED`; kiểm lại branch protection (`gh api …/protection`): hiện **không** bảo vệ (404, 2026-11-08); nếu có quy tắc bắt buộc review/check mà agent không thỏa ⇒ **dừng, báo owner, không bypass** |
| 5 | Target chưa tiến thêm | `git rev-parse origin/mhiu05/feat-refactor == $TIP` (đã hòa giải); nếu khác ⇒ quay lại INT-01 §3.3 và chạy lại gate bị ảnh hưởng |
| 6 | `main` không đổi | `origin/main == 8b329980…` |
| 7 | Cả hai feature SHA vẫn là tổ tiên | `merge-base --is-ancestor $P2 $SHA`, `$P3 $SHA` |

Merge (giữ lịch sử, gắn chặt vào SHA đã xác minh):

```powershell
gh pr merge $PR --merge --match-head-commit $SHA --subject "merge: integrate Phase 2 + Phase 3 ($SHA)"
git fetch origin
$MERGE = (git rev-parse origin/mhiu05/feat-refactor)
git merge-base --is-ancestor $SHA origin/mhiu05/feat-refactor   # exit 0
git branch -r --contains $P2 | Select-String "mhiu05/feat-refactor"
git branch -r --contains $P3 | Select-String "mhiu05/feat-refactor"
```

Không `--squash`, không `--rebase`, không `--delete-branch` (giữ `integration/phase-2-3` và hai nhánh feature làm bằng chứng). Nếu `gh pr merge` thất bại: không thử bỏ cờ an toàn; ghi nguyên nhân và dừng.

## 11. Kiểm tra sau merge (INT-10)

Làm trên **bản sao sạch của target** để chứng minh kết quả độc lập với nhánh feature:

```powershell
git worktree add C:\Users\minhh\orca\workspaces\MoodPrint\post-merge-verify origin/mhiu05/feat-refactor --detach
cd C:\Users\minhh\orca\workspaces\MoodPrint\post-merge-verify
git rev-parse HEAD                                  # == $MERGE
Copy-Item ..\mhiu05-feat-refactor\.env .env          # chỉ để chạy local; không in
$env:MOODPRINT_STACK_NAME="int"; $env:MOODPRINT_PORT_OFFSET="300"
uv sync --all-packages --all-extras --locked
uv run python scripts/dev/supabase_worktree.py start --lite
uv run python scripts/dev/supabase_worktree.py reset
uv run python scripts/dev/bootstrap_local_db.py --workdir .local/stacks/int
uv run python scripts/verify_phase23.py             # exit 0, receipt đúng $MERGE
gh run list --commit $MERGE --json name,conclusion,url   # CI của merge commit
```

Xác nhận thêm: (a) nội dung hợp nhất đủ — danh sách file của `feat/knowledge-base` và `feat/agent-companion` đều có trong cây (`git diff --stat $BASE $MERGE`); (b) hosted vẫn khớp `list_migrations` với repo (dry-run rỗng); (c) smoke hosted ngắn (health/ready + một tìm kiếm tri thức) nếu còn ngân sách; (d) số test không thấp hơn tổng baseline + hai feature.

## 12. Tag hoàn tất

Chỉ khi §11 xanh:

```powershell
git tag -a baseline/phase-2-3-verified $MERGE -m "Phase 2 (Knowledge Base) + Phase 3 (AI Companion) integrated and verified; verify_phase23.py exit 0 on $MERGE"
git push origin baseline/phase-2-3-verified
git rev-parse 'baseline/phase-2-3-verified^{commit}'        # == $MERGE
```

Không di chuyển hay xóa tag nào đã tồn tại (`baseline/phase-1-verified`, `baseline/phase-2-3-start*`). Ghi SHA đích vào báo cáo và vào mục "Hoàn tất" của `docs/implementation/reports/phase-2-report.md`/`phase-3-report.md` thông qua **báo cáo tích hợp** (không sửa file do feature sở hữu sau merge; thêm ghi chú vào `integration-report.md`).

## 13. Thất bại, khôi phục

| Tình huống | Hành động |
|---|---|
| Điều kiện §2 chưa đạt | Dừng; báo cáo `BLOCKED`/`NOT_VERIFIED` kèm chính xác mục thiếu; trả về feature agent (hoặc owner cho khóa/ngân sách) |
| Test đỏ ở integration | Sửa trong nhánh integration kèm test hồi quy có tập trung; hoặc trả về feature nếu là lỗi nghiệp vụ của phase; chạy lại từ bước bị ảnh hưởng |
| Xung đột không giải được | Dừng; đừng chọn bên; ghi cả hai phía; hỏi feature owner |
| Hosted áp dụng một phần/lỗi | **Không** reset. Ghi trạng thái (`list_migrations`); sửa tiến bằng migration mới; nếu không chắc ⇒ dừng và báo owner. Hosted chỉ chứa dữ liệu tổng hợp |
| Hosted xong nhưng merge không thực hiện được | Giữ nhánh integration; schema hosted cộng thêm không làm hỏng mã hiện hành (bảng/hàm mới); ghi lại và thử lại merge khi blocker được gỡ |
| CI đỏ trên PR | Chẩn đoán nguyên nhân gốc; sửa; không merge |
| Target tiến thêm | Merge target vào integration, chạy lại gate bị ảnh hưởng, cập nhật SHA, **tạo lại điều kiện §10** |
| Phát hiện hồi quy sau merge | Fix-forward bằng PR có review từ nhánh tách khỏi target; nếu nghiêm trọng và không sửa nhanh ⇒ PR revert merge (`git revert -m 1 $MERGE`), **không** viết lại lịch sử, ghi chú rằng muốn merge lại phải revert-the-revert; không gắn tag |
| Rò dữ liệu/Critical bảo mật phát hiện | Dừng mọi thao tác hosted/merge; báo owner; xử lý trước |

Trạng thái khôi phục được: nhánh `integration/phase-2-3`, tag `rc`, báo cáo từng bước, `.local/*gate*.json`, log trong `.local/verification/`.

## 14. Cấu trúc báo cáo cuối (`integration-report.md`)

1. **Kết luận:** PHASE_2/PHASE_3/G-INTEGRATION (VERIFIED/BLOCKED), SHA merge, tag.
2. **SHA đã dùng:** `$BASE`, `$P2`, `$P3`, `$TIP`, ba merge commit, `$SHA` PR, `$MERGE`.
3. **Preflight:** bảng §2.1 với bằng chứng và URL CI.
4. **Xung đột và quyết định** (bảng §4).
5. **Migration:** danh sách hợp nhất, kết quả hai thứ tự, đổi tên/`int_fix` nếu có.
6. **IT-01…IT-20:** bảng trạng thái, lệnh, kết quả, số lượng.
7. **Eval tích hợp:** Knowledge (so Phase 2) và Companion (so Phase 3), chi tiêu, độ trễ.
8. **Vertical slice:** 19 bước × (scripted, live ×3).
9. **Bảo mật:** bảng §8 và phát hiện.
10. **Hosted:** định danh, lịch sử, dry-run, apply, advisors (trước/sau), publish corpus, smoke API/UI, dọn dữ liệu (số đếm).
11. **CI/PR/Merge:** run URL, bảng §10, lệnh merge.
12. **Post-merge:** `verify_phase23.py` trên bản sao sạch, CI merge commit.
13. **Chi phí & độ trễ:** token/USD thực tế, p50/p95.
14. **Giới hạn đã biết & owner actions còn lại:** `00` §6 (chưa sẵn sàng học sinh thật), quyết định giấy phép, ngân sách, `main`.
15. **Thay đổi bất thường so với kế hoạch** và lý do.

## 15. Những điều tuyệt đối không làm

Merge vào `main`; merge feature branch trực tiếp vào target; force-push/rebase nhánh chia sẻ; sửa hay di chuyển tag baseline cũ; reset hosted; DDL hosted qua MCP; dùng database MoodPrint cũ; bỏ qua hook/CI; nới/xóa/skip test; thay mô hình khác `gpt-6-luna` hoặc nhà cung cấp khác; ghi secret vào repo/log/PR; tuyên bố hoàn tất khi còn P0 `BLOCKED`.
