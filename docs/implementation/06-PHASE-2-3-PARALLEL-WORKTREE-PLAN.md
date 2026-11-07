# 06 — Phase 2 / Phase 3 Parallel Worktree Plan

> 📐 PLANNED. **Không tạo branch hay worktree nào cho tới khi gate G2 đạt** (§8). Theo AD-19, agent được tạo worktree, push branch feature, mở PR, và integrator agent được merge vào `mhiu05/feat-refactor` khi gate đạt. Merge vào `main` vẫn do owner.

## 1. Mục tiêu

Hai coding agent làm cùng lúc, không sửa chung file, không đụng migration của nhau, mỗi bên tự test được, và hợp nhất bằng một nhánh integration có kiểm tra.

| | Phase 2 — Knowledge | Phase 3 — Companion |
|---|---|---|
| Branch | `feat/knowledge-ingestion-rag` | `feat/agent-companion` |
| Worktree đề xuất | `C:\Users\minhh\orca\workspaces\MoodPrint\feat-knowledge-ingestion-rag` | `C:\Users\minhh\orca\workspaces\MoodPrint\feat-agent-companion` |
| Rẽ từ | Tag `baseline/phase-1-verified` | Cùng tag |
| Knowledge | Adapter thật | `FixtureKnowledgeRetriever` |
| Migration scope | `kb` | `ag` |
| Báo cáo | `docs/implementation/reports/phase-2-report.md` | `docs/implementation/reports/phase-3-report.md` |

## 2. Quy trình

1. Phase 0, Phase 1 merge vào `mhiu05/feat-refactor`, mọi gate xanh.
2. Chuẩn bị scaffold cho cả hai phía (§3.3), chạy lại toàn bộ test.
3. Đặt tag annotated `baseline/phase-1-verified` trên commit đó, ghi SHA vào `phase-1-report.md`.
4. `git worktree add <path> -b feat/knowledge-ingestion-rag baseline/phase-1-verified`, tương tự cho Phase 3.
5. Mỗi worktree có `.env` riêng (copy tay, không link), local Supabase riêng (§6).
6. Mỗi agent chỉ sửa file thuộc quyền mình (§4). Pre-commit hook và CI chạy `scripts/check_ownership.py --phase 2|3`.
7. Thay đổi contract theo §5.
8. Mỗi branch tự xanh, viết báo cáo.
9. Tạo `integration/phase-2-3` từ tag baseline, merge Phase 2, rồi Phase 3, chạy integration test (§7).
10. Khi §7 xanh, integrator agent merge `integration/phase-2-3` vào `mhiu05/feat-refactor`, áp dụng migration `kb_*`, `ag_*` lên hosted theo AD-19, chạy smoke, rồi viết báo cáo. Owner quyết định khi nào vào `main`.

Không rebase branch đã chia sẻ. Cập nhật từ baseline chỉ bằng merge các compat change đã duyệt.

## 3. Đóng băng

### 3.1 Danh sách 🔒

| Đối tượng | File |
|---|---|
| Toàn bộ contract | `shared/src/moodprint_shared/contracts/**` |
| Fixture, contract test | `shared/src/moodprint_shared/testing/**` |
| JSON Schema đã xuất | `shared/contract-schemas/**` |
| Env loader | `shared/src/moodprint_shared/env.py`, `logging.py` |
| Migration `f0_*`, `f1_*` | `supabase/migrations/*_f0_*`, `*_f1_*` |
| Auth, UoW, error | `backend/app/core/**` |
| Service domain Phase 1 | `backend/app/modules/{profiles,incidents,evidence,plans,contacts,sharing,support,knowledge_state}/**` |
| Frontend ports, HTTP client | `frontend/src/services/ports.ts`, `services/http/client.ts`, `services/workspace.ts` |
| Streaming schema TS | `frontend/src/services/http/stream-events.ts` |

### 3.2 Kiểm tra

```bash
uv run python scripts/check_ownership.py --phase 2 --base baseline/phase-1-verified
```

Script đọc `docs/implementation/ownership.yaml`, so `git diff --name-only`, fail khi có file ngoài vùng của phase hoặc trong vùng đóng băng.

### 3.3 Scaffold trước khi rẽ nhánh

Tạo trong baseline, để hai branch chỉ **sửa** file của mình, không cùng **tạo** file chung:

| Scaffold | Chủ sau đó |
|---|---|
| `agent/src/moodprint_agent/knowledge/__init__.py` có `create_retriever()` trả fixture | Phase 2 |
| `backend/app/api/v1/knowledge.py` router rỗng, đã đăng ký trong `app/api/v1/__init__.py` | Phase 2 |
| `agent/ingestion/__init__.py`, `agent/tests/knowledge/`, `agent/evals/knowledge/` | Phase 2 |
| `frontend/src/services/composition/knowledge.ts` trả adapter local | Phase 2 |
| `agent/src/moodprint_agent/{tools,roleplay,evidence}/__init__.py` | Phase 3 |
| `frontend/src/services/composition/chat.ts`, `analysis.ts`, `roleplay.ts` trả mock | Phase 3 |
| `[project.optional-dependencies] knowledge = []` và `companion = []` trong `agent/pyproject.toml`, cách nhau bằng comment | Mỗi phase một mục |
| Class `KnowledgeConfig`, `AgentConfig`, `MemoryConfig` trong `config.py` | Phase 2: `KnowledgeConfig`. Phase 3: hai class còn lại |
| Khối `# --- knowledge ---`, `# --- agent ---` trong `.env.example` | Theo khối |
| `docs/implementation/ownership.yaml`, `scripts/check_ownership.py` | Integrator |

`composition.ts` chỉ import các file trong `composition/`, nên không ai cần sửa nó.

## 4. Ma trận sở hữu file

| Đường dẫn | Phase 2 | Phase 3 | Ghi chú |
|---|---|---|---|
| `agent/ingestion/**` | ✍ | | CLI offline |
| `agent/src/moodprint_agent/knowledge/**` | ✍ | | Gồm `create_retriever` |
| `agent/tests/knowledge/**`, `agent/evals/knowledge/**` | ✍ | | |
| `backend/app/modules/knowledge/**`, `api/v1/knowledge.py` | ✍ | | API tìm kiếm cho Knowledge Hub nếu cần |
| `supabase/migrations/*_kb_*.sql`, `supabase/tests/kb_*.sql` | ✍ | | Chỉ schema `knowledge` |
| `frontend/src/features/knowledge/**`, `services/composition/knowledge.ts`, `services/http/knowledge.ts` | ✍ | | |
| `KnowledgeConfig` trong `config.py`, khối knowledge của `.env.example`, `knowledge` extra | ✍ | | |
| `agent/src/moodprint_agent/{companion,runtime,events,budget,errors}.py`, `prompts/**` | | ✍ | |
| `agent/src/moodprint_agent/{tools,memory,roleplay,evidence}/**` | | ✍ | Memory thuộc Phase 3 sau Foundation |
| `agent/tests/**` (trừ `knowledge/`), `agent/evals/**` (trừ `knowledge/`) | | ✍ | |
| `backend/app/agent_gateway/**`, `modules/{conversations,memory}/**`, `api/v1/{conversations,memories}.py`, `jobs/**` | | ✍ | |
| `supabase/migrations/*_ag_*.sql`, `supabase/tests/ag_*.sql` | | ✍ | |
| `frontend/src/features/ai/**`, `services/composition/{chat,analysis,roleplay}.ts`, `services/http/{chat,analysis,roleplay}.ts` | | ✍ | |
| `AgentConfig`, `MemoryConfig`, khối agent của `.env.example`, `companion` extra | | ✍ | |
| `uv.lock`, `frontend/package-lock.json` | Tái tạo | Tái tạo | Không sửa tay. Xung đột: lấy một bên rồi `uv lock` / `npm install` |
| `backend/openapi.json`, `frontend/src/services/http/schema.gen.ts` | Tái tạo | Tái tạo | Sinh lại sau merge |
| §3.1 | 🔒 | 🔒 | Chỉ qua compat change |
| Mọi file khác | 🔒 | 🔒 | Hỏi integrator |

**Chỗ chạm duy nhất giữa hai phía:** Phase 3 gọi `create_retriever(cfg)`, Phase 2 sở hữu bên trong hàm đó. Signature thuộc contract 🔒.

## 5. Thay đổi contract

Khi một bên **bắt buộc** phải đổi vùng 🔒:

1. Dừng phần việc phụ thuộc. Không sửa vùng 🔒 trong feature branch.
2. Viết đề xuất `docs/implementation/compat/CC-NNN.md`: lý do, thay đổi, tương thích ngược ra sao, ảnh hưởng tới bên kia.
3. Integrator tạo branch `compat/CC-NNN` từ tag baseline, làm thay đổi theo kiểu **cộng thêm** (field optional, method mới, giá trị enum mới), có test.
4. Merge vào `mhiu05/feat-refactor`, đặt tag `baseline/phase-1-verified+ccNNN`.
5. **Cả hai** feature branch merge tag mới.
6. Không chấp nhận thay đổi phá vỡ khi hai branch còn mở. Nếu bắt buộc phải phá vỡ: đóng băng một branch, merge branch kia trước.

Ví dụ thay đổi cộng thêm được phép: thêm `KnowledgeFilters.formats: list[str] = []`. Không được phép: đổi tên `KnowledgeChunk.score`.

## 6. Database

### 6.1 Phân vùng đối tượng

| Phase | Được tạo | Không được |
|---|---|---|
| 2 | Schema `knowledge` và mọi thứ trong đó: `sources`, `documents`, `chunks` với `vector(1024)`, index HNSW, FTS, hàm tìm kiếm `SECURITY INVOKER` | Đụng `app`, `agent_store`, `public`, extension |
| 3 | Bảng mới trong `app` hoặc `agent_store`, ví dụ `memory_embeddings`, `roleplay_sessions`, `agent_evals` | `ALTER`, `DROP` bảng `f0`, `f1`; đụng `knowledge`; extension |

`vector` đã bật ở `f0`. Grant cho schema `knowledge`: `authenticated` chỉ `SELECT` nội dung đã duyệt, ghi chỉ bằng role ingestion (Phase 2 định nghĩa).

### 6.2 Thứ tự và tên

- Tên file dùng timestamp thật lúc tạo. Vì đối tượng không giao nhau, hai chuỗi `kb_*` và `ag_*` xen kẽ thời gian vẫn đúng.
- Integration test chạy migration theo **cả hai thứ tự** (`kb` trước rồi `ag`, và ngược lại) trên DB trống. Không qua thì phải sửa trước khi merge.
- Hosted dùng `db push --include-all` khi timestamp nằm trước migration đã áp dụng, chỉ integrator chạy.

### 6.3 Môi trường cô lập

| Môi trường | Ai dùng | Ghi |
|---|---|---|
| Local Supabase worktree Phase 2 | Agent Phase 2 | Tự do, `db reset` thoải mái |
| Local Supabase worktree Phase 3 | Agent Phase 3 | Tự do |
| Local Supabase `integration/phase-2-3` | Integrator | Merge test |
| Hosted `db-school-violence` | **Chỉ integrator agent** | Qua `push_hosted.py` sau khi §7 xanh. Agent Phase 2, Phase 3 không push lên hosted |

Port mỗi stack lấy theo kết luận S-04. Mặc định fallback: Phase 2 offset `+100`, Phase 3 offset `+200` cho cả DB, API, Studio, Inbucket.

Không agent nào giữ `DATABASE_URL` của hosted trong `.env` worktree. `UnsafeTestEnvironment` của F0-02.1 chặn trường hợp nhầm.

Chi phí API: Phase 2 cần `VOYAGE_API_KEY` để embed; Phase 3 chỉ cần `OPENAI_API_KEY` cho test `live_agent`. Mỗi phase có trần chi phí riêng do owner đặt (O-09).

## 7. Integration

Trên `integration/phase-2-3`:

| Test | Kiểm |
|---|---|
| `IT-01` | Migration hai thứ tự trên DB trống |
| `IT-02` | `KnowledgeRetrieverContract` pass với adapter thật |
| `IT-03` | Phase 3 tool `knowledge_search` với adapter thật trả citation có `source_id` tồn tại trong `knowledge.sources` |
| `IT-04` | Không kết quả: Companion nói không có nguồn, không sinh URL |
| `IT-05` | Timeout retriever: `run.failed` hoặc trả lời không citation, không treo |
| `IT-06` | Mọi test của hai branch, frontend `demo` và `real` |
| `IT-07` | pgTAP: RLS coverage cả `knowledge.*` và bảng `ag_*` |
| `IT-08` | `check_ownership.py` của từng branch so với baseline |
| `IT-09` | Eval knowledge và eval companion chạy lại với retriever thật bằng `gpt-6-luna`, so baseline. Integrator agent tự chấm rubric (AD-20) |

## 8. Gate G2 — sẵn sàng làm song song

Tất cả mục sau phải đạt. Integrator ghi bằng chứng vào `phase-1-report.md`.

| # | Tiêu chí | Cách kiểm |
|---|---|---|
| 1 | Phase 0, 1 đã merge vào một baseline, mọi test xanh | `verify_phase0.py`, `verify_phase1.py` exit 0 trên cùng commit |
| 2 | Contract đóng băng, snapshot schema được commit | `test_contract_snapshot` pass, `shared/contract-schemas/` sạch |
| 3 | Baseline DB `f0`, `f1` áp dụng được từ trống, và đã áp dụng hosted nếu owner yêu cầu | `db reset`, `list_migrations` |
| 4 | `AuthContext` ổn định | Không có thay đổi chưa merge |
| 5 | `KnowledgeRetrieverContract` pass với fixture | `pytest shared/tests` |
| 6 | Agent runtime chạy với `ScriptedModel` | `test_agent_stream.py` |
| 7 | Memory persist và retrieval chạy | `test_memory_*.py` |
| 8 | Tool context và approval contract ổn định, S-03 có kết luận | `test_agent_approval.py`, `spikes/S-03.md` |
| 9 | Mock/real adapter ổn định, composition tách file | `composition.test.ts`, `services/composition/` tồn tại |
| 10 | Ownership có tài liệu và được kiểm tự động | `ownership.yaml`, `check_ownership.py` có test |
| 11 | Scaffold §3.3 có mặt | Danh sách kiểm |
| 12 | S-04 cho phép hai stack | `spikes/S-04.md` |
| 13 | CI hoạt động | F0-10.2 |
| 14 | Chiến lược integration test (§7) được ghi vào `phase-1-report.md` | Integrator agent tự lập; owner có thể phản đối khi đọc báo cáo |

Nếu G2 không đạt, chỉ chạy **một** phase tại một thời điểm.
