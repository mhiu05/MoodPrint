# Execution ledger — Phase 0 / Phase 1

Source: approved plans 01, 02 and execution order 08. Initial HEAD: `1a3c81fca5d5c43bf910aa9ff5f971a4a669bab5`.

- Đã đọc đủ 9 tài liệu theo thứ tự 08,00,01,03,04,05,07,02,06.
- Bảo toàn `.claude/settings.local.json`, `.cursor/mcp.json`, `.mcp.json`, `.env.example`, các tài liệu owner cung cấp.
- Ruling: không sửa `.gitignore` theo chỉ dẫn trực tiếp của owner; cache/runtime artifacts không stage, chỉ stage đường dẫn cụ thể. Chi phí: `git status` có thể hiện thêm cache chưa track.
- Ruling: dùng linked worktree hiện có (giới hạn writable root), tạo nhánh `feat/phase-0-foundation`; không tạo worktree Phase 2/3. Chi phí: cần giữ riêng thay đổi MCP chưa commit.
- Pre-flight: AuthContext → UoW → services; shared DTOs → agent/runtime; SQL migrations → models; mọi interface theo tài liệu 04.
- Phase 1 chưa được phép bắt đầu trước G0.
- F0-01/02/09: shared workspace/contracts/settings/logging đã kiểm chứng; commit `cb3ed5a8`.
- F0-05/03.2: migrations, RLS/UoW và drift đã kiểm chứng; commit `6acd76fb`.
- F0-07/08.4: SDK runtime/session/context + ScriptedModel; commit `ca3958b9`, tests trong API integration commit.
- F0-03/04/06/07/08/10 local: API, memory, SSE, verification/CI; commit `3db6c7a7`.
- Final review: independent read-only reviewer tìm 4 Important issues; tất cả có regression RED→GREEN: dedupe memory deletion, cumulative approval usage, retrieval age/version, OpenAPI/pagination. Không có deferred minor được reviewer nêu.
- Final privacy regression: Uvicorn handler riêng bypass root redaction; RED→GREEN bằng handler routing về filtered root.
- Local full gate trên `3db6c7a7`: 140 offline +43 integration +84 pgTAP +54 frontend PASS. Frontend/.gitignore diff rỗng.
- Hosted READ-ONLY: Auth settings/JWKS/bucket đúng; dry-run liệt kê 10 pending migrations, exit0. Không apply/schema write/provision role.
- Ruling: giữ hosted apply chờ Dashboard proof theo F0-11.1/AD-19; browser extension đọc tab hiện có lỗi timeoutMs/CDP trước dispatch. Chi phí: G0/G1/G2 chưa đạt, Phase1 chưa bắt đầu.
- Owner đã đổi privileged dotenv key sang SUPABASE_DB_URL; giữ nguyên secret value, runtime credential chưa sinh khi prerequisite chưa đủ.
- Branch đã push; draft PR #46 https://github.com/mhiu05/MoodPrint/pull/46. CI run 42366869339 trên ab9d4397 success (offline +integration). Không merge/tag.
- Final cleanup local count-only: Auth users0, evidence objects0, SDK sessions0.
